"""Count-only sensor emulator (v2).

Sensors have a position and an effective range. Phones send probe bursts at random
times; tags advertise every second. A sensor reports, every 5 s, how many distinct
devices it heard in its last window. Detections for all candidate spots are computed
once per run; a placement is then just a subset of candidates.

Noise model (labelled assumptions are ours, the rest is sourced):
  phones: 85 % carry a detectable phone (ours); Poisson probe bursts at 0.0258 /s and
          90 % reception (ours), tuned so a person standing in range for 60 s is counted
          with p ~ 0.67, matching Determe et al. (2022). Window 60 s.
  tags:   80 % participation (ours); one advertisement per second (Kontakt.io default
          interval); 50 % reception per advertisement (ours). Window 10 s.
  both:   effective range 10 m after a signal-strength cut-off (~1 sensor / 400 m^2,
          Determe et al., 2022); 5 % of messages lost; sensors can be failed.
"""
from pathlib import Path

import numpy as np

from sensors import sketch
from shared.venue import Venue

DATA = Path(__file__).resolve().parents[1] / "data"
REPORT_EVERY = 5
MODES = {
    "phones": {"window": 60, "carry": 0.85, "rate": 0.0258, "receive": 0.9, "epoch": 60},
    "tags":   {"window": 10, "carry": 0.80, "rate": 1.0, "receive": 0.5, "epoch": 10 ** 6},
}
RANGE = 10.0

# candidate mounting spots (x, y): centre line plus the audience sides
CANDIDATES = [(-23, 0), (-15, 0), (-9, 0), (-3, 0), (3, 0), (9, 0), (15, 0), (21, 0), (26, 0), (29, 2.5),
              (33, 0), (38, 0), (-12, 8), (-12, -8), (0, 8), (0, -8), (12, 8), (12, -8), (22, 5), (22, -5)]
CAND_IDS = [f"C{i:02d}" for i in range(len(CANDIDATES))]


def load_seconds(run_id):
    t = np.loadtxt(DATA / "trajectories" / f"{run_id}.csv", delimiter=",", skiprows=1)
    t = t[t[:, 1] % 5 == 0]
    t[:, 1] //= 5
    return t  # id, second, x, y


def observe(run_id, mode, seed=0):
    """Which person each candidate spot would count in every report (cached)."""
    out = DATA / "sensors" / f"{run_id}_{mode}.npz"
    if out.exists():
        return dict(np.load(out))
    cfg, rng = MODES[mode], np.random.default_rng(seed)
    traj = load_seconds(run_id)
    pids = np.unique(traj[:, 0]).astype(int)
    pidx = {p: i for i, p in enumerate(pids)}
    carries = rng.random(len(pids)) < cfg["carry"]
    cand = np.array(CANDIDATES, float)
    last_heard = np.full((len(cand), len(pids)), -1e9)
    t_end = int(traj[:, 1].max())
    reports = np.arange(REPORT_EVERY, t_end + 1, REPORT_EVERY)
    seen = np.zeros((len(reports), len(cand), len(pids)), bool)
    by_sec = {s: traj[traj[:, 1] == s] for s in range(t_end + 1)}
    ri = 0
    for s in range(t_end + 1):
        rows = by_sec[s]
        if len(rows):
            who = np.array([pidx[int(p)] for p in rows[:, 0]])
            on = carries[who]
            who, xy = who[on], rows[on][:, 2:4]
            # bursts this second (phones: Poisson; tags: one advert)
            bursts = rng.poisson(cfg["rate"], len(who)) if mode == "phones" else np.ones(len(who), int)
            d = np.hypot(xy[:, 0][None] - cand[:, 0][:, None], xy[:, 1][None] - cand[:, 1][:, None])
            p_heard = 1 - (1 - cfg["receive"]) ** bursts[None, :]
            heard = (d <= RANGE) & (rng.random(d.shape) < p_heard)
            ci, pj = np.nonzero(heard)
            last_heard[ci, who[pj]] = s
        while ri < len(reports) and reports[ri] == s:
            seen[ri] = last_heard > s - cfg["window"]
            ri += 1
    res = {"reports": reports, "pids": pids, "seen": seen, "mode": np.array(mode)}
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **res)
    return res


def readings(obs, sensors, seed=0, dropout=0.05, failures=(), with_sketches=False):
    """What the twin receives for one placement.

    sensors: candidate indices. failures: (sensor position in list, t_from, t_to).
    Returns counts (reports x sensors, NaN = no message) and, for option B, the
    estimated overlap for every sensor pair (reports x pairs, NaN = missing).
    """
    rng = np.random.default_rng(seed)
    seen = obs["seen"][:, sensors, :]
    counts = seen.sum(2).astype(float)
    lost = rng.random(counts.shape) < dropout
    for k, a, b in failures:
        lost[(obs["reports"] >= a) & (obs["reports"] < b), k] = True
    counts[lost] = np.nan
    out = {"t": obs["reports"], "counts": counts, "lost": lost}
    if with_sketches:
        pairs = [(i, j) for i in range(len(sensors)) for j in range(i + 1, len(sensors))]
        ov = np.full((len(counts), len(pairs)), np.nan)
        epoch = MODES[str(obs["mode"])]["epoch"]
        cache = {}
        for r, t in enumerate(obs["reports"]):
            e = int(t // epoch)
            if e not in cache:  # salt shared by all sensors, rotated every epoch
                cache = {e: sketch.hash_positions(obs["pids"], salt=f"epoch{e}")}
            pos = cache[e]
            sks = [sketch.build(pos, seen[r, k]) for k in range(len(sensors))]
            for q, (i, j) in enumerate(pairs):
                if not (lost[r, i] or lost[r, j]):
                    ov[r, q] = sketch.overlap(sks[i], sks[j])
        out["pairs"], out["overlap"] = pairs, ov
    return out


def to_messages(run_id, obs, sensors, venue_id="concert_venue", **kw):
    """The same readings as schema-conformant messages (for the live pipeline / repo examples)."""
    r = readings(obs, sensors, **kw)
    mode = "personal_device" if str(obs["mode"]) == "phones" else "ble_tag"
    msgs = []
    for i, t in enumerate(r["t"]):
        for k, c in enumerate(sensors):
            if not np.isnan(r["counts"][i, k]):
                msgs.append({"topic": f"venue/{venue_id}/sensor/{CAND_IDS[c]}/count",
                             "payload": {"ts": float(t), "run_id": run_id, "venue_id": venue_id,
                                         "sensor_id": CAND_IDS[c], "zone_id": coverage_zone(c),
                                         "count": int(r["counts"][i, k]), "mode": mode, "seq": i}})
    return msgs


def coverage(venue=None):
    """Share of each zone's area inside each candidate's range (candidates x zones)."""
    from shapely.geometry import Point
    venue = venue or Venue()
    cov = np.zeros((len(CANDIDATES), len(venue.zone_ids)))
    for c, (x, y) in enumerate(CANDIDATES):
        disk = Point(x, y).buffer(RANGE, 64)
        for z, zid in enumerate(venue.zone_ids):
            cov[c, z] = venue.rects[zid].intersection(disk).area / venue.area[z]
    return cov


def coverage_zone(c, venue=None):
    venue = venue or Venue()
    return venue.zone_ids[int(np.argmax(coverage(venue)[c] * venue.area))]
