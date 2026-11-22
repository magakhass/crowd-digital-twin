"""Run the twin (or a baseline) over one recorded run, offline.

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
from twin.observation import FullObservation, ObservationModel, fitted
from twin.params import params

HORIZON = 120  # forecast horizon, s
CONFIRM = 2    # consecutive reports above the cut-off before an alert fires


def alert_onsets(flag, t):
    """Rising edges of an alert that has to hold for CONFIRM reports."""
    on, run, active = [], np.zeros(flag.shape[1], int), np.zeros(flag.shape[1], bool)
    for i in range(len(t)):
        run = np.where(flag[i], run + 1, 0)
        start = (run >= CONFIRM) & ~active
        on += [(int(z), float(t[i])) for z in np.nonzero(start)[0]]
        active = np.where(flag[i], active | start, False)
    return on


def run(run_id, method, mode="phones", sensors=(), sketches=False, tau=None, failures=(), seed=0):
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
        obs = emulator.observe(run_id, mode)
        rd = emulator.readings(obs, list(sensors), seed=seed, failures=failures, with_sketches=sketches)
        reports = rd["t"][rd["t"] <= t_end]
        obs_op = ObservationModel(mode, list(sensors), sketches)
        ys = [obs_op.stack(rd, i) for i in range(len(reports))]

    est = np.zeros((len(reports), nz))
    p_red = np.zeros((len(reports), nz))
    p_amb = np.zeros((len(reports), nz))

    if method in ("twin", "full"):
        f = EnKF(ZoneModel(venue, p["capacity"], p.get("kmax")), p["prior_standing"], seed=seed)
        ri = 0
        for t in range(1, t_end + 1):
            f.predict()
            if ri < len(reports) and reports[ri] == t:
                f.update(ys[ri], obs_op, obs_op.var)
                est[ri] = f.occ.mean(0) / venue.area
                p_red[ri], p_amb[ri] = f.forecast(HORIZON, venue.red, venue.amber)
                ri += 1
        red_flag, amb_flag = p_red >= tau, p_amb >= tau
    else:
        # static inversion of the occupancy part of the observation model
        a = obs_op.coef[:len(sensors), :nz]
        for i, y in enumerate(ys):
            y = y[:len(sensors)]
            ok = ~np.isnan(y)
            if ok.any():
                n, _ = nnls(a[ok], y[ok])
                est[i] = n / venue.area
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
    return {"t": reports, "est": est, "p_red": p_red, "red": alert_onsets(red_flag, reports),
            "amber": alert_onsets(amb_flag, reports), "sensed": sensed}


def coverage_mask(sensors, threshold=0.25):
    cov = emulator.coverage()
    return (cov[list(sensors)] >= threshold).any(0) if len(sensors) else np.zeros(cov.shape[1], bool)
