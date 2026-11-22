"""Per-second ground truth from trajectories: zone occupancy and zone inflow."""
from pathlib import Path

import numpy as np

from shared.venue import Venue

DATA = Path(__file__).resolve().parents[1] / "data"


def truth(run_id, venue=None):
    out = DATA / "truth" / f"{run_id}_full.npz"
    if out.exists():
        d = np.load(out)
        return d["occ"], d["inflow"]
    venue = venue or Venue()
    t = np.loadtxt(DATA / "trajectories" / f"{run_id}.csv", delimiter=",", skiprows=1)
    t = t[t[:, 1] % 5 == 0]
    sec = (t[:, 1] // 5).astype(int)
    zone = venue.zone_index(t[:, 2], t[:, 3])
    n_t, n_z = sec.max() + 1, len(venue.zone_ids)
    occ = np.zeros((n_t, n_z))
    np.add.at(occ, (sec[zone >= 0], zone[zone >= 0]), 1)
    # inflow: people whose zone this second differs from their zone a second ago
    inflow = np.zeros((n_t, n_z))
    order = np.lexsort((sec, t[:, 0]))
    pid, s, z = t[order, 0], sec[order], zone[order]
    moved = (pid[1:] == pid[:-1]) & (s[1:] == s[:-1] + 1) & (z[1:] != z[:-1]) & (z[1:] >= 0)
    np.add.at(inflow, (s[1:][moved], z[1:][moved]), 1)
    np.savez_compressed(out, occ=occ, inflow=inflow)
    return occ, inflow


def events(density, red, min_len=10):
    """Critical events: truth density at or above red for at least min_len seconds."""
    ev = []
    for z in range(density.shape[1]):
        above = density[:, z] >= red[z]
        t = 0
        while t < len(above):
            if above[t]:
                e = t
                while e < len(above) and above[e]:
                    e += 1
                if e - t >= min_len:
                    ev.append((z, t, e))
                t = e
            else:
                t += 1
    return ev
