"""Zone flow model + ensemble Kalman filter + short-horizon forecast.

Process model: a zone-level version of the pedestrian cell transmission model of
Hanseler et al. (2014). Each zone holds standing and walking people. Walking people
move to the next zone downstream at the Weidmann (1993) walking speed, limited by
the link capacity (persons per metre per second x width) and by the space left in
the receiving zone. Standing people in the audience start walking at an unknown
release rate, which the filter estimates.

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
    """Static description of the venue as the twin sees it (venue file only)."""

    def __init__(self, venue, capacity, kmax=None):
        self.venue = venue
        self.nz = len(venue.zone_ids)
        self.area = venue.area
        self.length = venue.bounds[:, 1] - venue.bounds[:, 0]
        # egress chain from the venue links; the last zone empties through a 3 m exit
        self.next = -np.ones(self.nz, int)
        self.width = np.zeros(self.nz)
        for a, b, w in venue.links:
            self.next[venue.idx[a]], self.width[venue.idx[a]] = venue.idx[b], w
        last = venue.idx[venue.links[-1][1]]
        self.width[last] = 3.0
        self.audience = np.array([i for i, k in enumerate(venue.kind) if k == "static"])
        self.capacity = capacity  # persons per metre per second, calibrated
        # effective storage density per zone (a queue never fills a zone corner to corner), calibrated
        self.kmax = np.full(self.nz, 0.95 * KC) if kmax is None else np.asarray(kmax, float)

    def step(self, standing, walking, lam, rng, noise=True):
        """Advance every ensemble member by 1 s. Arrays are (members, zones)."""
        m = walking.shape[0]
        n = walking + standing
        release = np.zeros_like(walking)
        release[:, self.audience] = np.minimum(standing[:, self.audience], lam)
        standing = standing - release
        walking = walking + release
        v = weidmann(n / self.area)
        demand = walking * np.minimum(1.0, v / self.length)
        cap = self.capacity * self.width
        flow = np.minimum(demand, cap)
        has_next = self.next >= 0
        room = np.full_like(walking, np.inf)
        nxt = self.next[has_next]
        room[:, has_next] = np.maximum(0.0, self.kmax[nxt] * self.area[nxt] - n[:, nxt])
        flow = np.minimum(flow, room)
        if noise:
            flow = flow * np.clip(1 + 0.1 * rng.standard_normal((m, self.nz)), 0.5, 1.5)
            flow = np.minimum(flow, walking)
        inflow = np.zeros_like(walking)
        walking = walking - flow
        for z in np.nonzero(has_next)[0]:
            walking[:, self.next[z]] += flow[:, z]
            inflow[:, self.next[z]] += flow[:, z]
        return standing, np.maximum(walking, 0), inflow


class EnKF:
    def __init__(self, model, prior_standing, members=100, lam_sd=0.15, seed=0):
        self.m, self.k = model, members
        self.rng = np.random.default_rng(seed)
        nz = model.nz
        self.standing = np.zeros((members, nz))
        mu, sd = prior_standing
        self.standing[:, model.audience] = np.maximum(0, mu + sd * self.rng.standard_normal((members, len(mu))))
        self.walking = np.zeros((members, nz))
        self.lam = np.abs(0.1 * self.rng.standard_normal((members, len(model.audience))))
        self.lam_sd = lam_sd
        self.occ_hist = np.zeros((members, W_MAX, nz))
        self.in_hist = np.zeros((members, W_MAX, nz))
        self.t = 0

    @property
    def occ(self):
        return self.standing + self.walking

    def predict(self):
        self.standing, self.walking, inflow = self.m.step(self.standing, self.walking, self.lam, self.rng)
        self.lam = np.clip(self.lam + self.lam_sd * self.rng.standard_normal(self.lam.shape), 0, 10)
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
        x = np.hstack([self.standing[:, self.m.audience], self.walking, self.lam])
        xa, ha = x - x.mean(0), hx - hx.mean(0)
        c_xy = xa.T @ ha / (self.k - 1)
        c_yy = ha.T @ ha / (self.k - 1) + np.diag(r_var)
        gain = np.linalg.solve(c_yy, c_xy.T).T
        y_pert = y + np.sqrt(r_var) * self.rng.standard_normal((self.k, len(y)))
        x = x + (y_pert - hx) @ gain.T
        na = len(self.m.audience)
        self.standing[:, self.m.audience] = np.maximum(x[:, :na], 0)
        new_walk = np.maximum(x[:, na:na + self.m.nz], 0)
        # keep the window history consistent with the corrected occupancy
        self.occ_hist[:, -1] += (self.standing + new_walk) - self.occ
        self.walking = new_walk
        self.lam = np.clip(x[:, na + self.m.nz:], 0, 10)

    def forecast(self, horizon, red, amber):
        """Share of members whose density reaches red / amber somewhere in the next `horizon` s."""
        s, w, lam = self.standing.copy(), self.walking.copy(), self.lam.copy()
        peak = (s + w) / self.m.area
        for _ in range(horizon):
            s, w, _ = self.m.step(s, w, lam, self.rng)
            lam = np.clip(lam + self.lam_sd * self.rng.standard_normal(lam.shape), 0, 10)
            peak = np.maximum(peak, (s + w) / self.m.area)
        return (peak >= red).mean(0), (peak >= amber).mean(0)
