"""Venue loader shared by the simulator, the sensors and the twin."""
import json
from pathlib import Path

import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

VENUES = Path(__file__).parent / "venues"


class Venue:
    def __init__(self, path=VENUES / "concert_venue_v1.json"):
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
