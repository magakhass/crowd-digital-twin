"""Twin settings frozen after calibration (data/results/params.json)."""
import json
from pathlib import Path

import numpy as np

FILE = Path(__file__).resolve().parents[1] / "data" / "results" / "params.json"
DEFAULTS = {"capacity": 82 / 60, "prior_standing": [[280, 280, 280], [80, 80, 80]], "tau": 0.5}


def params():
    p = dict(DEFAULTS)
    if FILE.exists():
        p.update(json.loads(FILE.read_text()))
    p["prior_standing"] = tuple(np.array(v, float) for v in p["prior_standing"])
    return p


def save(**kw):
    p = json.loads(FILE.read_text()) if FILE.exists() else {}
    p.update(kw)
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(p, indent=1))
