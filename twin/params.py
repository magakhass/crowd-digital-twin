"""Twin settings frozen after calibration (data/results/params.json)."""
import json
from pathlib import Path

import numpy as np

from shared.venue import data_dir

FILE = data_dir() / "results" / "params.json"
DEFAULTS = {"capacity": 82 / 60, "tau": 0.5}
LAM_WALK = 0.15     # release rate drift per second over a third of the hall (egress, as with three audience zones)
SETTLE_WALK = 0.2   # settle rate drift, as a share of its calibrated value (ingress)
ARRIVAL_WALK = 0.1  # arrival rate drift per second, p/s (ingress)
GATE_SD, GATE_WALK = 0.05, 0.01  # gate factor: starting spread around 1 and drift per second


def params():
    p = dict(DEFAULTS)
    if FILE.exists():
        p.update(json.loads(FILE.read_text()))
    return p


def save(**kw):
    p = json.loads(FILE.read_text()) if FILE.exists() else {}
    p.update(kw)
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(p, indent=1))


def phase_settings(p, phase, na):
    """Prior crowd and rate settings for the EnKF in one event phase (see twin/model.py)."""
    zero = np.zeros(na)
    if phase == "egress":
        mu, sd = (np.array(v, float) for v in p["prior_standing"])
        k = np.sqrt(3 / na)  # smaller zones: per-zone drift scaled so the whole hall drifts as much as before
        return {"standing": (mu, sd),
                "rate_mean": np.r_[zero, zero, 0.0, 1.0], "rate_sd": np.r_[np.full(na, 0.1 * k), zero, 0.0, GATE_SD],
                "rate_walk": np.r_[np.full(na, LAM_WALK * k), zero, 0.0, GATE_WALK]}
    settle = np.array(p["settle"], float)
    a_mu, a_sd = p["arrival"]
    return {"standing": (zero, zero), "tickets": p["tickets"],  # doors just opened: the hall is empty
            "rate_mean": np.r_[zero, settle, a_mu, 1.0], "rate_sd": np.r_[zero, 0.3 * settle, a_sd, GATE_SD],
            "rate_walk": np.r_[zero, SETTLE_WALK * settle, ARRIVAL_WALK, GATE_WALK]}
