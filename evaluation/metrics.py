"""Warning metrics against ground truth (Section 10 of our plan).

An event is truth density >= red for at least 10 s in one zone. A red alert in that
zone counts as a hit if it fires before the event starts (lead >= 0) and no more than
5 min early. A red alert with no event starting within HORIZON + 30 s, and not during
an event, is a false alarm.
"""
import numpy as np

from evaluation.truth import events, truth
from shared.venue import Venue

MAX_LEAD = 300


def score_run(run_id, out, horizon=120):
    venue = Venue()
    occ, _ = truth(run_id)
    dens = occ / venue.area
    evs = events(dens, venue.red)
    hits, leads, late = 0, [], 0
    used = set()
    for z, t0, t1 in evs:
        cand = [t for zz, t in out["red"] if zz == z and t0 - MAX_LEAD <= t <= t1]
        early = [t for t in cand if t <= t0]
        if early:
            hits += 1
            leads.append(t0 - min(early))
        elif cand:
            late += 1
        used.update((z, t) for t in cand)
    fa = 0
    for z, t in out["red"]:
        if (z, t) in used:
            continue
        if not any(zz == z and t - 5 <= t0 <= t + horizon + 30 for zz, t0, _ in evs):
            fa += 1
    # nowcast error on report times, sensed and unsensed zones separately
    ti = out["t"].astype(int)
    err = (out["est"] - dens[ti]) ** 2
    busy = occ[ti].sum(1) > 0
    rm = lambda m: float(np.sqrt(err[busy][:, m].mean())) if m.any() else np.nan
    return {"events": len(evs), "hits": hits, "late": late, "leads": leads, "false_alarms": fa,
            "hours": len(occ) / 3600, "rmse_sensed": rm(out["sensed"]), "rmse_unsensed": rm(~out["sensed"])}


def summarise(scores):
    ev = sum(s["events"] for s in scores)
    leads = [l for s in scores for l in s["leads"]]
    hours = sum(s["hours"] for s in scores)
    def mean(k):
        v = [s[k] for s in scores if not np.isnan(s[k])]
        return float(np.mean(v)) if v else np.nan
    return {"events": ev, "pod": sum(s["hits"] for s in scores) / ev if ev else np.nan,
            "late": sum(s["late"] for s in scores), "median_lead_s": float(np.median(leads)) if leads else np.nan,
            "fa_per_hour": sum(s["false_alarms"] for s in scores) / hours,
            "rmse_sensed": mean("rmse_sensed"), "rmse_unsensed": mean("rmse_unsensed"), "runs": len(scores)}
