"""Venue loader shared by the simulator, the sensors and the twin.

The active venue comes from the CROWDTWIN_VENUE environment variable (default: the concert
venue). Each venue keeps its own generated data: data/ for the concert venue (as before),
data/venues/{venue}/ for any other.
"""
import json
import os
from pathlib import Path

import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

VENUES = Path(__file__).parent / "venues"
DEFAULT = "concert_venue_v1"
ACTIVE = os.environ.get("CROWDTWIN_VENUE", DEFAULT)
ROOT = Path(__file__).resolve().parents[1]


def data_dir():
    return ROOT / "data" if ACTIVE == DEFAULT else ROOT / "data" / "venues" / ACTIVE


class Venue:
    def __init__(self, path=None):
        path = path or VENUES / f"{ACTIVE}.json"
        self.raw = json.loads(Path(path).read_text())
        self.id = self.raw["venue_id"]
        self.zones = self.raw["zones"]
        self.zone_ids = [z["id"] for z in self.zones]
        self.idx = {z: i for i, z in enumerate(self.zone_ids)}
        self.bounds = np.array([[z["x_min"], z["x_max"], z["y_min"], z["y_max"]] for z in self.zones], float)
        self.area = np.array([z["area_m2"] for z in self.zones], float)
        self.amber = np.array([z["amber_persons_m2"] for z in self.zones], float)
        self.red = np.array([z["red_persons_m2"] for z in self.zones], float)
        self.kind = [z["type"] for z in self.zones]
        self.links = [(l["from"], l["to"], l["width_m"]) for l in self.raw["links"]]
        self.rects = {z: box(b[0], b[2], b[1], b[3]) for z, b in zip(self.zone_ids, self.bounds)}
        self.walkable = unary_union(list(self.rects.values()))
        self.audience = [z for z, k in zip(self.zone_ids, self.kind) if k == "static"]
        self.entry_zone = self.zone_of(self.raw["spawn_points"][0])
        self.exit_zone = self.zone_of(self.raw["exit_points"][0])
        # simulation and sensing details (absent in older venue files)
        r = self.raw
        self.exit_areas = [box(e["x_min"], e["y_min"], e["x_max"], e["y_max"]) for e in r.get("exit_areas", [])]
        self.gates = r.get("gates", [])
        self.gate = self.gates[0] if self.gates else None
        self.exit_ids = [e["id"] for e in r.get("exit_areas", [])]
        self.entrance = r["entrances"][0] if r.get("entrances") else None
        self.poi = {q["id"]: box(q["x_min"], q["y_min"], q["x_max"], q["y_max"]) for q in r.get("points_of_interest", [])}
        self.candidates = [(c["x"], c["y"]) for c in r.get("sensor_candidates", [])]
        self.candidate_ids = [c["id"] for c in r.get("sensor_candidates", [])]
        self.presets = {k: [self.candidate_ids.index(c) for c in v] for k, v in r.get("placement_presets", {}).items()}
        self.risk_zones = r.get("risk_zones", [])

    def exits(self):
        """(zone, width) of every exit area; older files: a 3 m exit in the exit point's zone."""
        if not self.exit_areas:
            return [(self.exit_zone, 3.0)]
        return [(self.zone_of({"x": e.centroid.x, "y": e.centroid.y}), e.bounds[3] - e.bounds[1]) for e in self.exit_areas]

    def gate_behind(self):
        """(zone just past the gate, gate width) for every gate: where we measure the gate flow."""
        out = []
        for k, g in enumerate(self.gates):
            area = self.exit_areas[self.exit_ids.index(g["exit"]) if "exit" in g else 0]
            out.append((self.zone_of({"x": area.centroid.x, "y": area.centroid.y}), g["y_max"] - g["y_min"]))
        return out

    def zone_of(self, point):
        return self.zone_ids[int(self.zone_index(point["x"], point["y"]))]

    def zone_index(self, x, y):
        # half-open membership rule; -1 = outside every zone
        x, y = np.asarray(x, float), np.asarray(y, float)
        out = np.full(x.shape, -1, int)
        for i, (x0, x1, y0, y1) in enumerate(self.bounds):
            m = (x >= x0) & (x < x1) & (y >= y0) & (y < y1) & (out < 0)
            out[m] = i
        return out

    def counts(self, x, y):
        zi = self.zone_index(x, y)
        return np.bincount(zi[zi >= 0], minlength=len(self.zone_ids))
