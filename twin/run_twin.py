"""Run the twin (or a baseline) over one recorded run, offline. The twin itself is the Twin
class below, which takes one report at a time, so the live service (live/twin_service.py)
runs exactly the same code on messages arriving over MQTT.

Methods:
  twin      EnKF + zone flow model + forecast (option A or B sensing)
  full      same twin fed the true zone counts (best case)
  sensor    current sensor readings only, no model, no forecast
  trend     sensor-only densities extrapolated in a straight line (Still's fill predictor)
"""
import numpy as np
from scipy.optimize import nnls

from evaluation.truth import truth
from sensors import emulator
from shared.venue import Venue
from twin.model import EnKF, ZoneModel
from twin.observation import FullObservation, ObservationModel
from twin.params import params, phase_settings
from sim.scenarios import SCENARIOS

HORIZON = 120  # forecast horizon, s
CONFIRM = 2    # consecutive reports above the cut-off before an alert fires
OFFLINE = 2    # missing reports in a row before a sensor counts as offline
COVERS = 0.25  # share of a zone inside a sensor's range for it to count as watching the zone
BLIND_DRIFT = 3.0  # rates may drift this many times faster while a risk zone is unwatched (our assumption)


class Twin:
    """Zone flow model + EnKF + forecast, fed one report at a time.

    phase: event phase from the schedule (egress / ingress). sensors: installed candidate spots.
    obs_op: observation model for those sensors. Sensor health is tracked unless health=False
    (full observability has no sensors to lose)."""

    def __init__(self, phase, sensors, obs_op, seed=0, p=None, health=True):
        self.venue = venue = Venue()
        p = p or params()
        kmax = p.get("kmax")
        kmax = kmax[phase] if isinstance(kmax, dict) else kmax
        model = ZoneModel(venue, p["capacity"], kmax, np.array(p["turning"][phase]) if "turning" in p else None)
        self.f = EnKF(model, phase_settings(p, phase, model.na), seed=seed)
        self.obs_op, self.n_s, self.health = obs_op, len(sensors), health and len(sensors) > 0
        # sensor health: which risk zones still have a working sensor watching them
        self.risk = [venue.idx[z] for z in venue.risk_zones]
        self.watch = (emulator.coverage()[list(sensors)][:, self.risk] >= COVERS if len(sensors)
                      else np.zeros((0, len(self.risk)), bool))
        self.missing, self.was_watched = np.zeros(len(sensors), int), self.watch.any(0)

    def advance(self, t):
        while self.f.t < t:
            self.f.predict()

    def report(self, t, y):
        """Process the report at time t (y: counts, then pair overlaps; NaN = missing).
        Returns the density estimate, P(red) and P(amber) per zone, and the risk zones that just went blind."""
        self.advance(t)
        blind = []
        if self.health:
            self.missing = np.where(np.isnan(y[:self.n_s]), self.missing + 1, 0)
            watched = (self.watch & (self.missing < OFFLINE)[:, None]).any(0)
            blind = [int(self.risk[z]) for z in np.nonzero(self.was_watched & ~watched)[0]]  # lost its last sensor
            self.was_watched = watched
            self.f.inflate = BLIND_DRIFT if (self.watch.any(0) & ~watched).any() else 1.0
        self.f.update(y, self.obs_op, self.obs_op.var)
        est = self.f.occ.mean(0) / self.venue.area
        p_red, p_amb = self.f.forecast(HORIZON, self.venue.red, self.venue.amber)
        return est, p_red, p_amb, blind


class Onsets:
    """Alert onsets as reports come in (same rule as alert_onsets)."""

    def __init__(self, nz):
        self.run, self.active = np.zeros(nz, int), np.zeros(nz, bool)

    def step(self, flag):
        self.run = np.where(flag, self.run + 1, 0)
        start = (self.run >= CONFIRM) & ~self.active
        self.active = np.where(flag, self.active | start, False)
        return [int(z) for z in np.nonzero(start)[0]]


def alert_onsets(flag, t):
    """Rising edges of an alert that has to hold for CONFIRM reports."""
    on, run, active = [], np.zeros(flag.shape[1], int), np.zeros(flag.shape[1], bool)
    for i in range(len(t)):
        run = np.where(flag[i], run + 1, 0)
        start = (run >= CONFIRM) & ~active
        on += [(int(z), float(t[i])) for z in np.nonzero(start)[0]]
        active = np.where(flag[i], active | start, False)
    return on


def run(run_id, method, mode="phones", sensors=(), sketches=False, tau=None, failures=(), seed=0, noise="medium"):
    venue = Venue()
    p = params()
    tau = p["tau"] if tau is None else tau
    occ, inflow = truth(run_id)
    t_end = len(occ) - 1
    nz = len(venue.zone_ids)

    if method == "full":
        reports = np.arange(5, t_end + 1, 5)
        obs_op = FullObservation(nz)
        ys = [occ[t] for t in reports]
    else:
        obs = emulator.observe(run_id, mode, noise)
        rd = emulator.readings(obs, list(sensors), seed=seed, failures=failures, with_sketches=sketches)
        reports = rd["t"][rd["t"] <= t_end]
        obs_op = ObservationModel(mode, list(sensors), sketches, noise)
        ys = [obs_op.stack(rd, i) for i in range(len(reports))]

    est = np.zeros((len(reports), nz))
    blind = []  # (zone, time) when a risk zone loses its last working sensor
    p_red = np.zeros((len(reports), nz))
    p_amb = np.zeros((len(reports), nz))

    if method in ("twin", "full"):
        phase = SCENARIOS[run_id.rsplit("-", 1)[0]].get("movement", "egress")  # from the event schedule
        tw = Twin(phase, sensors if method == "twin" else [], obs_op, seed=seed, p=p)
        for ri, t in enumerate(reports):
            est[ri], p_red[ri], p_amb[ri], lost = tw.report(t, ys[ri])
            blind += [(z, float(t)) for z in lost]
        red_flag, amb_flag = p_red >= tau, p_amb >= tau
    else:
        # static inversion of the occupancy part of the observation model
        a = obs_op.coef[:len(sensors), :nz]
        kmax = p.get("kmax", 0.95 * 5.4)
        kmax = np.max(list(kmax.values()), axis=0) if isinstance(kmax, dict) else np.asarray(kmax)
        for i, y in enumerate(ys):
            y = y[:len(sensors)]
            ok = ~np.isnan(y)
            if ok.any():
                n, _ = nnls(a[ok], y[ok])
                # a zone a sensor barely sees can get any count from the inversion; cap it at the
                # highest density seen in calibration
                est[i] = np.minimum(n / venue.area, kmax)
            elif i:
                est[i] = est[i - 1]
        if method == "sensor":
            red_flag, amb_flag = est >= venue.red, est >= venue.amber
        else:  # trend: slope over the last 30 s, projected HORIZON s ahead
            k = 6
            proj = est.copy()
            for i in range(k, len(est)):
                slope = (est[i] - est[i - k]) / (reports[i] - reports[i - k])
                proj[i] = est[i] + np.maximum(slope, 0) * HORIZON
            red_flag, amb_flag = proj >= venue.red, proj >= venue.amber

    sensed = np.ones(nz, bool) if method == "full" else coverage_mask(sensors)
    return {"t": reports, "est": est, "p_red": p_red, "p_amber": p_amb, "red": alert_onsets(red_flag, reports), "blind": blind,
            "amber": alert_onsets(amb_flag, reports), "sensed": sensed}


def coverage_mask(sensors, threshold=0.25):
    cov = emulator.coverage()
    return (cov[list(sensors)] >= threshold).any(0) if len(sensors) else np.zeros(cov.shape[1], bool)
