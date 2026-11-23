"""Per-second ground truth from trajectories: zone occupancy and zone inflow."""
from pathlib import Path

import numpy as np

from shared.venue import Venue, data_dir

DATA = data_dir()


def truth(run_id, venue=None):
    out = DATA / "truth" / f"{run_id}_full.npz"
    src = DATA / "trajectories" / f"{run_id}.csv"
    venue = venue or Venue()
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:  # rebuilt when the run is simulated again
        d = np.load(out)
        if "zones" in d.files and list(d["zones"]) == venue.zone_ids:  # ...or when the venue zones change
            return d["occ"], d["inflow"]
    t, sec, zone = _seconds(run_id, venue)
    n_t, n_z = sec.max() + 1, len(venue.zone_ids)
    occ = np.zeros((n_t, n_z))
    np.add.at(occ, (sec[zone >= 0], zone[zone >= 0]), 1)
    # inflow: people whose zone this second differs from their zone a second ago
    inflow = np.zeros((n_t, n_z))
    order = np.lexsort((sec, t[:, 0]))
    pid, s, z = t[order, 0], sec[order], zone[order]
    moved = (pid[1:] == pid[:-1]) & (s[1:] == s[:-1] + 1) & (z[1:] != z[:-1]) & (z[1:] >= 0)
    np.add.at(inflow, (s[1:][moved], z[1:][moved]), 1)
    np.savez_compressed(out, occ=occ, inflow=inflow, zones=np.array(venue.zone_ids))
    return occ, inflow


def _seconds(run_id, venue):
    t = np.loadtxt(DATA / "trajectories" / f"{run_id}.csv", delimiter=",", skiprows=1)
    t = t[t[:, 1] % 5 == 0]
    sec = (t[:, 1] // 5).astype(int)
    return t, sec, venue.zone_index(t[:, 2], t[:, 3])


def movements(run_id, venue=None, still=0.1):
    """For the twin's calibration: zone-to-zone moves per second (zones x zones+1, the last
    column = left the venue from that zone), settles per zone (people who stop walking for
    good) and walking person-seconds per zone."""
    venue = venue or Venue()
    t, sec, zone = _seconds(run_id, venue)
    nz = len(venue.zone_ids)
    moves, settles, walking = np.zeros((nz, nz + 1)), np.zeros(nz), np.zeros(nz)
    order = np.lexsort((sec, t[:, 0]))
    pid, s, z, xy = t[order, 0], sec[order], zone[order], t[order][:, 2:4]
    same = (pid[1:] == pid[:-1]) & (s[1:] == s[:-1] + 1)
    step = np.hypot(*(xy[1:] - xy[:-1]).T)
    ok = same & (z[1:] >= 0) & (z[:-1] >= 0)
    np.add.at(moves, (z[:-1][ok & (z[1:] != z[:-1])], z[1:][ok & (z[1:] != z[:-1])]), 1)
    last = np.r_[~same, True]  # last record of each person
    gone = last & (s < s.max()) & (z >= 0)  # left before the end of the run
    np.add.at(moves, (z[gone], nz), 1)
    walk = np.r_[same & (step >= still), False]
    np.add.at(walking, z[walk & (z >= 0)], 1)
    # settles: the last time each person was walking, if they then stood until the end
    for p in np.unique(pid):
        i = np.nonzero(pid == p)[0]
        w = np.nonzero(walk[i])[0]
        if len(w) and not gone[i[-1]] and w[-1] < len(i) - 10 and z[i[w[-1] + 1]] >= 0:
            settles[z[i[w[-1] + 1]]] += 1
    return moves, settles, walking


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
