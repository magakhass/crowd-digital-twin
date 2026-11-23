"""Scenario definitions: who is in the venue, when they move, and what is different.

Egress scenarios (normal ... blockage): people stand in the audience zones until their
departure time, then walk to the exit through the 3 m bottleneck (Z06). Departure
profiles set how fast demand builds up.
Ingress: the venue starts empty; people come in through the entrance (Z01) when the
doors open and walk to a standing spot in the audience zones.
"""
import json

import numpy as np

from shared.venue import ACTIVE, data_dir

CALIBRATION_SEEDS = [1, 2]
TEST_SEEDS = list(range(3, 13))  # 10 test seeds (was 3-8)
VALID_SHARE = 0.95  # a run counts only if at least this share of the crowd gets out (or in); set 23 Nov,
                    # before any twin results: the simulator occasionally gridlocks (velocity-model clogging)


def departures(name, n, rng):
    # departure times (s) for n people
    if name == "normal":          # slow trickle, well below bottleneck capacity
        return rng.uniform(0, 600, n)
    if name in ("gradual", "blockage"):  # demand ramps up linearly, peaking above capacity
        return SCENARIOS[name].get("ramp", 300) * np.sqrt(rng.uniform(0, 1, n))
    if name in ("surge", "counterflow"):  # 20 % leave early, the rest when the show ends at 300 s
        early = rng.uniform(0, 300, int(0.2 * n))
        late = 300 + rng.exponential(10, n - len(early))
        return np.concatenate([early, late])
    raise ValueError(name)


def arrivals(name, n, rng):
    # arrival times (s) at the entrance: a share already waiting when the doors open comes in first,
    # the rest arrive steadily (our assumption)
    cfg = SCENARIOS[name]
    share, rush, until = cfg["rush_share"], cfg["rush_s"], cfg["arrive_until"]
    k = int(share * n)
    return np.sort(np.concatenate([rng.uniform(0, rush, k), rng.uniform(rush, until, n - k)]))


CONCERT = {
    # name: crowd size, held-out?, extra settings
    "normal":      {"n": 600, "held_out": False},
    "gradual":     {"n": 1500, "held_out": False, "ramp": 240},  # was 1300 over 300 s; see evidence log D6
    "surge":       {"n": 1200, "held_out": False},
    # held out: never used for calibration or tuning
    "counterflow": {"n": 1300, "held_out": True, "inflow": 60, "inflow_window": (230, 300)},  # was 1100
    "blockage":    {"n": 1100, "held_out": True, "block": (28.0, 30.0, 0.0, 1.5)},  # half of Z06 blocked
    # other movements (the twin does not model them yet, so experiments skip them)
    "ingress":     {"n": 1200, "held_out": False, "movement": "ingress",
                    "rush_share": 0.4, "rush_s": 120, "arrive_until": 900},
}
# festival hall (venue 2): two exits, and a ticket checkpoint people queue for on the way in
FESTIVAL = {
    "normal":  {"n": 800, "held_out": False},
    "gradual": {"n": 1500, "held_out": False, "ramp": 240},
    "surge":   {"n": 1500, "held_out": False},
    # doors open with a big crowd outside: 70 % arrive in the first 150 s (7 people/s, over twice
    # the ~3/s the checkpoint passes), so a queue builds in Z01 (our assumption)
    "ingress": {"n": 1500, "held_out": False, "movement": "ingress",
                "rush_share": 0.7, "rush_s": 150, "arrive_until": 900},
}
SCENARIOS = {"concert_venue_v1": CONCERT, "festival_hall_v2": FESTIVAL}[ACTIVE]
EGRESS = [n for n, c in SCENARIOS.items() if c.get("movement", "egress") == "egress"]


def valid(run_id):
    """True / False once the run exists, None before."""
    meta = data_dir() / "trajectories" / f"{run_id}.json"
    if not meta.exists():
        return None
    m = json.loads(meta.read_text())
    return m["agents_left"] <= (1 - VALID_SHARE) * m["n_audience"]


def test_seeds(name):
    # the 10 test seeds, with any run that broke the validity rule replaced by the next seed
    seeds, s = [], TEST_SEEDS[0]
    while len(seeds) < len(TEST_SEEDS):
        if valid(f"{name}-s{s:02d}") is not False:
            seeds.append(s)
        s += 1
    return seeds


def seeds_for(name):
    return test_seeds(name) if SCENARIOS[name]["held_out"] else CALIBRATION_SEEDS + test_seeds(name)
