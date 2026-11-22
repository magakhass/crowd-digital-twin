"""Scenario definitions: who is in the venue, when they leave, and what is different.

All scenarios are end-of-show egress on concert_venue_v1. People stand in the
audience zones until their departure time, then walk to the exit through the
3 m bottleneck (Z06). Departure profiles set how fast demand builds up.
"""
import numpy as np

CALIBRATION_SEEDS = [1, 2]
TEST_SEEDS = [3, 4, 5, 6, 7, 8]


def departures(name, n, rng):
    # departure times (s) for n people
    if name == "normal":          # slow trickle, well below bottleneck capacity
        return rng.uniform(0, 600, n)
    if name in ("gradual", "blockage"):  # demand ramps up linearly over 300 s, peaking above capacity
        return 300 * np.sqrt(rng.uniform(0, 1, n))
    if name in ("surge", "counterflow"):  # 20 % leave early, the rest when the show ends at 300 s
        early = rng.uniform(0, 300, int(0.2 * n))
        late = 300 + rng.exponential(10, n - len(early))
        return np.concatenate([early, late])
    raise ValueError(name)


SCENARIOS = {
    # name: crowd size, held-out?, extra settings
    "normal":      {"n": 600, "held_out": False},
    "gradual":     {"n": 1300, "held_out": False},
    "surge":       {"n": 1200, "held_out": False},
    # held out: never used for calibration or tuning
    "counterflow": {"n": 1100, "held_out": True, "inflow": 60, "inflow_window": (230, 300)},
    "blockage":    {"n": 1100, "held_out": True, "block": (28.0, 30.0, 0.0, 1.5)},  # half of Z06 blocked
}


def seeds_for(name):
    return TEST_SEEDS if SCENARIOS[name]["held_out"] else CALIBRATION_SEEDS + TEST_SEEDS
