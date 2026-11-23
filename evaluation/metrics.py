"""Warning metrics against ground truth (Section 10 of our plan).

An event is truth density >= red for at least 10 s in one zone. A red alert in that
zone counts as a hit if it fires before the event starts (lead >= 0) and no more than
5 min early. A red alert with no event starting within HORIZON + 30 s, and not during
an event, is a false alarm. Amber alerts are scored the same way against amber events.
The false-alarm ratio is false alarms over all red alerts; MAE and RMSE are the density
errors at report times.
"""
import numpy as np

from evaluation.truth import events, truth
from shared.venue import Venue

MAX_LEAD = 300


def _score(evs, alerts, horizon):
    hits, leads, late, used = 0, [], 0, set()
    for z, t0, t1 in evs:
        cand = [t for zz, t in alerts if zz == z and t0 - MAX_LEAD <= t <= t1]
        early = [t for t in cand if t <= t0]
        if early:
            hits += 1
            leads.append(t0 - min(early))
        elif cand:
            late += 1
        used.update((z, t) for t in cand)
    fa = sum(1 for z, t in alerts if (z, t) not in used
             and not any(zz == z and t - 5 <= t0 <= t + horizon + 30 for zz, t0, _ in evs))
    return hits, leads, late, fa


def score_run(run_id, out, horizon=120):
    venue = Venue()
    occ, _ = truth(run_id)
    dens = occ / venue.area
    evs = events(dens, venue.red)
    hits, leads, late, fa = _score(evs, out["red"], horizon)
    amber = _score(events(dens, venue.amber), out.get("amber", []), horizon)
    # nowcast error on report times, sensed and unsensed zones separately
    ti = out["t"].astype(int)
    diff = out["est"] - dens[ti]
    busy = occ[ti].sum(1) > 0
    rm = lambda m: float(np.sqrt((diff[busy][:, m] ** 2).mean())) if m.any() else np.nan
    ma = lambda m: float(np.abs(diff[busy][:, m]).mean()) if m.any() else np.nan
    return {"events": len(evs), "hits": hits, "late": late, "leads": leads, "false_alarms": fa,
            "alerts": len(out["red"]), "hours": len(occ) / 3600,
            "rmse_sensed": rm(out["sensed"]), "rmse_unsensed": rm(~out["sensed"]),
            "mae_sensed": ma(out["sensed"]), "mae_unsensed": ma(~out["sensed"]),
            "amber_events": len(events(dens, venue.amber)), "amber_hits": amber[0], "amber_late": amber[2],
            "amber_false_alarms": amber[3], "amber_leads": amber[1]}


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
            "rmse_sensed": mean("rmse_sensed"), "rmse_unsensed": mean("rmse_unsensed"), "runs": len(scores),
            "far": sum(s["false_alarms"] for s in scores) / max(1, sum(s["alerts"] for s in scores)),
            "mae_sensed": mean("mae_sensed"), "mae_unsensed": mean("mae_unsensed")}
