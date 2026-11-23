"""Observation model, learned from calibration runs only.

For each channel we fit count ~ a . mean_occupancy(window) + b . inflow(window)
with non-negative least squares, like Determe et al. (2022) fit their extrapolation
factor against a reference count. This absorbs the detection rate, the coverage of
each zone and the window effect (people passing count too). The twin never reads
the emulator settings.
"""
from functools import lru_cache

import numpy as np
from scipy.optimize import nnls

from evaluation.truth import truth
from sensors import emulator
from sim.scenarios import CALIBRATION_SEEDS

EGRESS_CAL = [f"{s}-s{k:02d}" for s in ("normal", "gradual", "surge") for k in CALIBRATION_SEEDS]
INGRESS_CAL = [f"ingress-s{k:02d}" for k in CALIBRATION_SEEDS]
CAL_RUNS = EGRESS_CAL + INGRESS_CAL  # the sensors serve the whole event, so both phases


def features(occ, inflow, t, window):
    lo = max(0, t - window + 1)
    return np.concatenate([occ[lo:t + 1].mean(0), inflow[lo:t + 1].sum(0)])


@lru_cache(maxsize=None)
def calibration_set(mode, noise="medium"):
    """Features, single-sensor counts and pair overlaps from all calibration runs, at one noise level."""
    window = emulator.MODES[mode]["window"]
    X, Y, P = [], [], []
    n_c = len(emulator.CANDIDATES)
    pairs = [(i, j) for i in range(n_c) for j in range(i + 1, n_c)]
    for run in CAL_RUNS:
        occ, inflow = truth(run)
        obs = emulator.observe(run, mode, noise)
        r = emulator.readings(obs, list(range(n_c)), dropout=0.0, with_sketches=True)
        for i, t in enumerate(obs["reports"]):
            if t >= len(occ):
                break
            X.append(features(occ, inflow, t, window))
            Y.append(r["counts"][i])
            P.append(r["overlap"][i])
    return np.array(X), np.array(Y), np.array(P), pairs


@lru_cache(maxsize=None)
def fitted(mode, noise="medium"):
    X, Y, P, pairs = calibration_set(mode, noise)
    coef, var = [], []
    for target in np.hstack([Y, P]).T:
        c, _ = nnls(X, target)
        coef.append(c)
        var.append(max(2.0, float(np.mean((X @ c - target) ** 2))))
    return np.array(coef), np.array(var), pairs


class ObservationModel:
    """Channels for one placement: one per sensor, plus one per sensor pair under option B."""

    def __init__(self, mode, sensors, sketches=False, noise="medium"):
        coef, var, pairs = fitted(mode, noise)
        n_c = len(emulator.CANDIDATES)
        rows = list(sensors)
        self.pairs = []
        if sketches:
            for i in range(len(sensors)):
                for j in range(i + 1, len(sensors)):
                    a, b = sorted((sensors[i], sensors[j]))
                    rows.append(n_c + pairs.index((a, b)))
                    self.pairs.append((i, j))
        self.coef, self.var = coef[rows], var[rows]
        self.window = emulator.MODES[mode]["window"]
        self.nz = coef.shape[1] // 2

    def __call__(self, occ_hist, in_hist):
        w = self.window
        f = np.concatenate([occ_hist[:, -w:].mean(1), in_hist[:, -w:].sum(1)], axis=1)
        return f @ self.coef.T

    def stack(self, readings, i):
        y = [readings["counts"][i]]
        if self.pairs:
            y.append(readings["overlap"][i])
        return np.concatenate(y)


class FullObservation:
    """Full-observability baseline: the true zone counts, every report."""

    def __init__(self, nz):
        self.nz, self.window = nz, 1
        self.var = np.full(nz, 1.0)


    def __call__(self, occ_hist, in_hist):
        return occ_hist[:, -1]
