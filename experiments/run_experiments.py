"""Full experiment sweep on the test runs (seeds 3-8), with settings frozen by calibrate.py.

Main grid: sensing mode (phones/tags) x option (A counts / B counts + sketches)
x placement (4 strategies) x budget (2, 4, 6) on normal, gradual and surge.
Baselines: full observability, sensor-only and trend.
Held-out: counterflow and blockage, twin with every placement at budget 4.
Failure test: surge, bottleneck placement, budget 4; sensors covering the
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
from shared.venue import Venue
from sim.scenarios import SCENARIOS, TEST_SEEDS
from twin.run_twin import run

OUT = Path(__file__).resolve().parents[1] / "data" / "results"
CORE = ["normal", "gradual", "surge"]
HELD_OUT = ["counterflow", "blockage"]
STRATEGIES = ["random", "entrance_exit", "bottleneck", "greedy_mi"]


def failure_window(run_id, sensors):
    venue = Venue()
    occ, _ = truth(run_id)
    evs = events(occ / venue.area, venue.red)
    if not evs:
        return ()
    t0 = min(e[1] for e in evs)
    cov = emulator.coverage()
    hot = [venue.idx[z] for z in ("Z05", "Z08", "Z06")]
    return tuple((k, t0 - 90, 10 ** 6) for k, c in enumerate(sensors) if cov[c, hot].max() >= 0.25)


def jobs(scenarios):
    for sc, seed in itertools.product(scenarios, TEST_SEEDS):
        r = f"{sc}-s{seed:02d}"
        yield dict(run=r, scenario=sc, group="baseline", method="full", mode="-", option="-", strategy="-", budget=0)
        for mode, strat, budget in itertools.product(("phones", "tags"), STRATEGIES, (2, 4, 6)):
            if sc in HELD_OUT and budget != 4:
                continue
            base = dict(run=r, scenario=sc, mode=mode, strategy=strat, budget=budget)
            yield dict(base, group="main", method="twin", option="A")
            yield dict(base, group="main", method="twin", option="B")
            yield dict(base, group="baseline", method="sensor", option="A")
            yield dict(base, group="baseline", method="trend", option="A")
        if sc == "surge":
            for mode, opt in itertools.product(("phones", "tags"), "AB"):
                yield dict(run=r, scenario=sc, group="failure", method="twin", mode=mode, option=opt,
                           strategy="bottleneck", budget=4)


def do(job):
    seed = int(job["run"][-2:])
    sensors = [] if job["method"] == "full" else place(job["strategy"], job["budget"], job["mode"], seed)
    fail = failure_window(job["run"], sensors) if job["group"] == "failure" else ()
    out = run(job["run"], job["method"], job["mode"] if job["mode"] != "-" else "phones", sensors,
              sketches=job["option"] == "B", failures=fail, seed=seed)
    s = score_run(job["run"], out)
    return dict(job, sensors=" ".join(emulator.CAND_IDS[c] for c in sensors), events=s["events"], hits=s["hits"],
                late=s["late"], leads=" ".join(str(int(l)) for l in s["leads"]), false_alarms=s["false_alarms"],
                hours=round(s["hours"], 4), rmse_sensed=s["rmse_sensed"], rmse_unsensed=s["rmse_unsensed"],
                failed=len(fail))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("which", nargs="?", default="core", choices=["core", "heldout"])
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()
    which = args.which
    scenarios = CORE if which == "core" else HELD_OUT
    OUT.mkdir(parents=True, exist_ok=True)
    todo = list(jobs(scenarios))
    # build the per-run caches once, before the workers start, so no two processes write the same file
    for sc, seed in itertools.product(scenarios, TEST_SEEDS):
        rid = f"{sc}-s{seed:02d}"
        truth(rid)
        for mode in ("phones", "tags"):
            emulator.observe(rid, mode)
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
