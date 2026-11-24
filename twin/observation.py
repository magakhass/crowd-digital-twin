"""Observation model, learned from calibration runs only.

For each channel we fit count ~ a . mean_occupancy(window) + b . inflow(window)
with non-negative least squares, like Determe et al. (2022) fit their extrapolation
factor against a reference count. This absorbs the detection rate, the coverage of
each zone and the window effect (people passing count too). The twin never reads
the emulator settings.
"""
import os
import sys
from functools import lru_cache

import numpy as np
from scipy.optimize import nnls

from evaluation.truth import truth
from sensors import emulator
from shared.venue import data_dir
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


def saved_fit(mode, noise):
    return data_dir() / "results" / "observation" / f"{mode}_{noise}.npz"


@lru_cache(maxsize=None)
def fitted(mode, noise="medium"):
    f = saved_fit(mode, noise)
    if f.exists():  # saved with the results, so the twin runs without the calibration trajectories
        z = np.load(f)
        return z["coef"], z["var"], [tuple(int(v) for v in p) for p in z["pairs"]]
    X, Y, P, pairs = calibration_set(mode, noise)
    coef, var = [], []
    for target in np.hstack([Y, P]).T:
        c, _ = nnls(X, target)
        coef.append(c)
        var.append(max(2.0, float(np.mean((X @ c - target) ** 2))))
    coef, var = np.array(coef), np.array(var)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f"{f.stem}.{os.getpid()}.tmp.npz")  # parallel workers: write then rename
    np.savez(tmp, coef=coef, var=var, pairs=np.array(pairs))
    os.replace(tmp, f)
    return coef, var, pairs


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


if __name__ == "__main__":  # save the fits for the active venue: python -m twin.observation [noise ...]
    for noise in sys.argv[1:] or emulator.NOISE_LEVELS:
        for mode in emulator.MODES:
            fitted(mode, noise)
            print("saved", saved_fit(mode, noise))
