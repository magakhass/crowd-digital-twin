"""Sensor placement strategies over the candidate spots in the venue file.

greedy_mi follows Liebig, Xu and May (2013): pick spots one at a time to maximise
mutual information about the readings at the spots left unsensed, using only the
covariance of readings from calibration runs (Krause-style greedy criterion).
"""
from functools import lru_cache

import numpy as np

from sensors import emulator
from shared.venue import Venue
from twin.observation import CAL_RUNS

# hand-picked orders from the venue file: flow boundaries first (exit apron, entrance, ...) and
# around the bottleneck front and approach
ENTRANCE_EXIT = Venue().presets["entrance_exit"]
BOTTLENECK = Venue().presets["bottleneck"]


def random_spots(budget, seed):
    return sorted(np.random.default_rng(1000 + seed).choice(len(emulator.CANDIDATES), budget, replace=False).tolist())


@lru_cache(maxsize=None)
def _covariance(mode, noise):
    rows = [emulator.observe(r, mode, noise)["seen"].sum(2) for r in CAL_RUNS]
    x = np.vstack(rows).astype(float)
    return np.cov(x.T) + 1e-3 * np.eye(x.shape[1])


def _cond_var(cov, y, given):
    if not given:
        return cov[y, y]
    g = list(given)
    s = cov[np.ix_(g, g)]
    c = cov[y, g]
    return cov[y, y] - c @ np.linalg.solve(s, c)


@lru_cache(maxsize=None)
def greedy_mi(budget, mode, noise="medium"):
    cov = _covariance(mode, noise)
    n = cov.shape[0]
    chosen = []
    for _ in range(budget):
        best, best_gain = None, -np.inf
        for y in range(n):
            if y in chosen:
                continue
            rest = [v for v in range(n) if v != y and v not in chosen]
            gain = 0.5 * np.log(_cond_var(cov, y, chosen) / _cond_var(cov, y, rest))
            if gain > best_gain:
                best, best_gain = y, gain
        chosen.append(best)
    return tuple(sorted(chosen))


def place(strategy, budget, mode, seed=0, noise="medium"):
    if strategy == "random":
        return random_spots(budget, seed)
    if strategy == "entrance_exit":
        return sorted(ENTRANCE_EXIT[:budget])
    if strategy == "bottleneck":
        return sorted(BOTTLENECK[:budget])
    if strategy == "greedy_mi":
        return list(greedy_mi(budget, mode, noise))
    raise ValueError(strategy)
