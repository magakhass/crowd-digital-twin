"""Zone flow model + ensemble Kalman filter + short-horizon forecast.

Process model: a zone-level version of the pedestrian cell transmission model of
Hanseler et al. (2014). Each zone holds standing and walking people. Walking people
move to neighbouring zones at the Weidmann (1993) walking speed, split by turning
fractions learned from calibration runs of the same event phase, and limited by the
link capacity (persons per metre per second x shared edge width) and by the space
left in the receiving zone. The event phase (people leaving after the show, or
arriving when the doors open) comes from the event schedule.

  egress   standing people in the audience start walking at an unknown release rate
  ingress  people come in at the entrance at an unknown arrival rate, and walking people
           in the audience stop at an unknown settle rate

The filter estimates these rates together with the zone counts, and a gate factor: the share
of the calibrated capacity the narrowest links (the gate) really pass. It starts at 1 and drops
when the counts in front of the gate keep rising faster than the model expects, e.g. when part
of the gate is blocked (state augmentation for parameters, Evensen 2009).

Observation model: every channel (a sensor count, or a sensor-pair overlap for
option B) is a learned non-negative combination of the window-mean occupancy and
the window inflow of each zone (twin/observation.py).
"""
import numpy as np

VF, KC, GAMMA = 1.34, 5.4, 1.913  # Weidmann (1993), as used by Hanseler et al. (2014)
W_MAX = 60


def weidmann(k):
    k = np.maximum(k, 1e-3)
    v = VF * (1 - np.exp(-GAMMA * (1 / k - 1 / KC)))
    return np.clip(v, 0.0, VF)


class ZoneModel:
    """Static description of the venue as the twin sees it (venue file), plus the learned turning fractions."""

    def __init__(self, venue, capacity, kmax=None, turning=None):
        self.venue = venue
        self.nz = len(venue.zone_ids)
        self.area = venue.area
        self.length = venue.bounds[:, 1] - venue.bounds[:, 0]
        # widths of shared edges; the extra last column is the way out of the venue
        self.width = np.zeros((self.nz, self.nz + 1))
        for a, b, w in venue.links:
            self.width[venue.idx[a], venue.idx[b]] = self.width[venue.idx[b], venue.idx[a]] = w
        for z, w in venue.exits():  # every way out of the venue
            self.width[venue.idx[z], self.nz] = w
        self.gate = self.width == self.width[self.width > 0].min()  # the narrowest links
        self.audience = np.array([venue.idx[z] for z in venue.audience])
        self.entry = venue.idx[venue.entry_zone]
        self.capacity = capacity  # persons per metre per second, calibrated
        # effective storage density per zone (a queue never fills a zone corner to corner), calibrated
        self.kmax = np.full(self.nz, 0.95 * KC) if kmax is None else np.asarray(kmax, float)
        if turning is None:  # default: everyone heads along the links towards the exit
            turning = np.zeros((self.nz, self.nz + 1))
            turning[self.width > 0] = 1.0
        turning = np.where(self.width > 0, turning, 0.0)
        self.turning = turning / np.maximum(turning.sum(1, keepdims=True), 1e-9)
        self.na = len(self.audience)

    def n_rates(self):
        return 2 * self.na + 2  # release per audience zone | settle per audience zone | arrivals | gate factor

    def step(self, standing, walking, rates, rng, noise=True, to_come=None):
        """Advance every ensemble member by 1 s. Arrays are (members, zones); rates (members, n_rates);
        to_come (members,) = people still expected at the entrance (tickets sold minus arrived)."""
        a, na = self.audience, self.na
        lam, sig, arr = rates[:, :na], rates[:, na:2 * na], rates[:, 2 * na]
        g = np.clip(rates[:, 2 * na + 1], 0.1, 1.5)
        if to_come is not None:
            arr = np.minimum(arr, to_come)
            to_come -= arr
        standing, walking = standing.copy(), walking.copy()
        release = np.minimum(standing[:, a], lam)
        settle = np.minimum(walking[:, a], sig * walking[:, a])
        standing[:, a] += settle - release
        walking[:, a] += release - settle
        walking[:, self.entry] += arr
        n = walking + standing
        v = weidmann(n / self.area)
        demand = walking * np.minimum(1.0, v / self.length)
        cap = self.capacity * self.width[None] * np.where(self.gate[None], g[:, None, None], 1.0)
        flow = np.minimum(demand[:, :, None] * self.turning[None], cap)
        # the receiving zone only takes what fits; incoming flows are cut back in proportion
        room = np.maximum(0.0, self.kmax * self.area - n)
        incoming = flow[:, :, :self.nz].sum(1)
        flow[:, :, :self.nz] *= np.where(incoming > room, room / np.maximum(incoming, 1e-9), 1.0)[:, None, :]
        if noise:
            flow = flow * np.clip(1 + 0.1 * rng.standard_normal(flow.shape[:2]), 0.5, 1.5)[:, :, None]
        out = flow.sum(2)
        flow *= np.minimum(1.0, walking / np.maximum(out, 1e-9))[:, :, None]
        inflow = flow[:, :, :self.nz].sum(1)
        walking = walking - flow.sum(2) + inflow
        return standing, np.maximum(walking, 0), inflow


class EnKF:
    """phase: dict with the prior standing crowd (mean, sd per audience zone) and, per rate,
    its starting mean and spread and how much it may drift per second (random walk)."""

    def __init__(self, model, phase, members=100, seed=0):
        self.m, self.k = model, members
        self.rng = np.random.default_rng(seed)
        nz = model.nz
        self.standing = np.zeros((members, nz))
        mu, sd = phase["standing"]
        self.standing[:, model.audience] = np.maximum(0, mu + sd * self.rng.standard_normal((members, model.na)))
        self.walking = np.zeros((members, nz))
        r0, rsd, self.walk = (np.asarray(phase[k], float) for k in ("rate_mean", "rate_sd", "rate_walk"))
        self.to_come = np.full(members, float(phase.get("tickets", 0)))
        self.inflate = 1.0  # > 1 while a risk zone has no working sensor: rates may drift faster
        self.rates = np.abs(r0 + rsd * self.rng.standard_normal((members, len(r0))))
        self.occ_hist = np.zeros((members, W_MAX, nz))
        self.in_hist = np.zeros((members, W_MAX, nz))
        self.t = 0

    @property
    def occ(self):
        return self.standing + self.walking

    def _drift(self, rates):
        return np.clip(rates + self.inflate * self.walk * self.rng.standard_normal(rates.shape), 0, 10)

    def predict(self):
        self.standing, self.walking, inflow = self.m.step(self.standing, self.walking, self.rates, self.rng,
                                                          to_come=self.to_come)
        self.rates = self._drift(self.rates)
        self.occ_hist = np.roll(self.occ_hist, -1, axis=1)
        self.in_hist = np.roll(self.in_hist, -1, axis=1)
        self.occ_hist[:, -1], self.in_hist[:, -1] = self.occ, inflow
        self.t += 1

    def update(self, y, obs_op, r_var):
        """Stochastic EnKF update with perturbed observations; y may contain NaN (missing)."""
        ok = ~np.isnan(y)
        if not ok.any():
            return
        hx = obs_op(self.occ_hist, self.in_hist)[:, ok]
        y, r_var = y[ok], r_var[ok]
        a, na, nz = self.m.audience, self.m.na, self.m.nz
        x = np.hstack([self.standing[:, a], self.walking, self.rates])
        xa, ha = x - x.mean(0), hx - hx.mean(0)
        c_xy = xa.T @ ha / (self.k - 1)
        c_yy = ha.T @ ha / (self.k - 1) + np.diag(r_var)
        gain = np.linalg.solve(c_yy, c_xy.T).T
        y_pert = y + np.sqrt(r_var) * self.rng.standard_normal((self.k, len(y)))
        x = x + (y_pert - hx) @ gain.T
        self.standing[:, a] = np.maximum(x[:, :na], 0)
        new_walk = np.maximum(x[:, na:na + nz], 0)
        # no zone holds more than its storage density: a correction past it is cut back from the walkers
        excess = np.maximum(self.standing + new_walk - self.m.kmax * self.m.area, 0)
        new_walk = np.maximum(new_walk - excess, 0)
        # keep the window history consistent with the corrected occupancy
        self.occ_hist[:, -1] += (self.standing + new_walk) - self.occ
        self.walking = new_walk
        self.rates = np.clip(x[:, na + nz:], 0, 10)

    def forecast(self, horizon, red, amber):
        """Share of members whose density reaches red / amber somewhere in the next `horizon` s."""
        s, w, r, c = self.standing.copy(), self.walking.copy(), self.rates.copy(), self.to_come.copy()
        peak = (s + w) / self.m.area
        for _ in range(horizon):
            s, w, _ = self.m.step(s, w, r, self.rng, to_come=c)
            r = self._drift(r)
            peak = np.maximum(peak, (s + w) / self.m.area)
        return (peak >= red).mean(0), (peak >= amber).mean(0)
