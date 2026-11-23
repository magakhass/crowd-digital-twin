"""Full experiment sweep on the test runs (seeds 3-8), with settings frozen by calibrate.py.

Main grid: sensing mode (phones/tags) x noise level (low/medium/high) x option
(A counts / B counts + sketches) x placement (4 strategies) x budget (2, 4, 6, 8)
on normal, gradual and surge.
Baselines: full observability, sensor-only and trend (sensor-based ones at every noise level).
Held-out: counterflow and blockage, twin with every placement at budget 4, medium noise.
Failure test: surge, bottleneck placement, budget 4, medium noise; sensors covering the
bottleneck zones go offline 90 s before the first red event.
Results: data/results/runs_core.csv and runs_heldout.csv, one row per run.
Usage: python -m experiments.run_experiments core | heldout [--workers N]   (default: all cores but one)
"""
import argparse
import csv
import itertools
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from evaluation.metrics import score_run, summarise
from evaluation.truth import events, truth
from experiments.placement import place
from sensors import emulator
from sensors.emulator import NOISE_LEVELS
from shared.venue import ACTIVE, Venue, data_dir
from sim.scenarios import SCENARIOS, test_seeds
from twin.run_twin import run

OUT = data_dir() / "results"
CORE = ["normal", "gradual", "surge"]
HELD_OUT = ["counterflow", "blockage"]
MOVEMENTS = ["ingress"]  # other event phases: medium noise and 4 sensors only, like the held-out set
# "small": every scenario of the active venue at medium noise and 4 sensors (used for venue 2)
STRATEGIES = ["random", "entrance_exit", "bottleneck", "greedy_mi"]
BUDGETS = (2, 4, 6, 8)


def failure_window(run_id, sensors):
    venue = Venue()
    occ, _ = truth(run_id)
    evs = events(occ / venue.area, venue.red)
    if not evs:
        return ()
    t0 = min(e[1] for e in evs)
    cov = emulator.coverage()
    hot = [venue.idx[z] for z in venue.risk_zones]
    return tuple((k, t0 - 90, 10 ** 6) for k, c in enumerate(sensors) if cov[c, hot].max() >= 0.25)


def jobs(scenarios, small=False):
    for sc, seed in ((sc, k) for sc in scenarios for k in test_seeds(sc)):
        r = f"{sc}-s{seed:02d}"
        yield dict(run=r, scenario=sc, group="baseline", method="full", mode="-", noise="-", option="-", strategy="-", budget=0)
        levels = ["medium"] if small else NOISE_LEVELS
        for mode, noise, strat, budget in itertools.product(("phones", "tags"), levels, STRATEGIES, BUDGETS):
            if small and budget != 4:
                continue
            base = dict(run=r, scenario=sc, mode=mode, noise=noise, strategy=strat, budget=budget)
            yield dict(base, group="main", method="twin", option="A")
            yield dict(base, group="main", method="twin", option="B")
            if budget == 4:  # baselines are for comparison, so one sensor count is enough
                yield dict(base, group="baseline", method="sensor", option="A")
                yield dict(base, group="baseline", method="trend", option="A")
        if sc == "surge" and not small:
            for mode, opt in itertools.product(("phones", "tags"), "AB"):
                yield dict(run=r, scenario=sc, group="failure", method="twin", mode=mode, noise="medium", option=opt,
                           strategy="bottleneck", budget=4)


def do(job):
    seed = int(job["run"][-2:])
    noise = job["noise"] if job["noise"] != "-" else "medium"
    sensors = [] if job["method"] == "full" else place(job["strategy"], job["budget"], job["mode"], seed, noise)
    fail = failure_window(job["run"], sensors) if job["group"] == "failure" else ()
    out = run(job["run"], job["method"], job["mode"] if job["mode"] != "-" else "phones", sensors,
              sketches=job["option"] == "B", failures=fail, seed=seed, noise=noise)
    s = score_run(job["run"], out)
    # coverage-loss alerts: seconds from the first one to the first event (positive = before it)
    first_ev = min((t0 for _, t0, _ in events(truth(job["run"])[0] / Venue().area, Venue().red)), default=None)
    blind_lead = first_ev - min(t for _, t in out["blind"]) if out.get("blind") and first_ev is not None else np.nan
    return dict(job, sensors=" ".join(emulator.CAND_IDS[c] for c in sensors), events=s["events"], hits=s["hits"],
                late=s["late"], leads=" ".join(str(int(l)) for l in s["leads"]), false_alarms=s["false_alarms"],
                hours=round(s["hours"], 4), rmse_sensed=s["rmse_sensed"], rmse_unsensed=s["rmse_unsensed"],
                alerts=s["alerts"], mae_sensed=s["mae_sensed"], mae_unsensed=s["mae_unsensed"],
                amber_events=s["amber_events"], amber_hits=s["amber_hits"], amber_late=s["amber_late"],
                amber_false_alarms=s["amber_false_alarms"], amber_leads=" ".join(str(int(l)) for l in s["amber_leads"]),
                failed=len(fail), blind_alerts=len(out.get("blind", [])), blind_lead=blind_lead)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("which", nargs="?", default="core", choices=["core", "heldout", "movements", "small"])
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()
    which = args.which
    scenarios = {"core": CORE, "heldout": HELD_OUT, "movements": MOVEMENTS, "small": list(SCENARIOS)}[which]
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"venue: {ACTIVE}", flush=True)
    todo = list(jobs(scenarios, small=which != "core"))
    # build the per-run caches first, in parallel (one file per job, so no two processes write the same one)
    from experiments import caches
    from twin.observation import CAL_RUNS
    levels = NOISE_LEVELS if which == "core" else ["medium"]
    caches.build(CAL_RUNS + [f"{sc}-s{seed:02d}" for sc in scenarios for seed in test_seeds(sc)], levels, args.workers)
    print(f"{len(todo)} jobs, {args.workers} workers", flush=True)
    rows = []
    with ProcessPoolExecutor(args.workers) as pool:
        for i, row in enumerate(pool.map(do, todo, chunksize=4)):
            rows.append(row)
            if i % 50 == 0:
                print(f"{i}/{len(todo)}", flush=True)
    with open(OUT / f"runs_{which}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("done", len(rows))
