"""Run every scenario x seed that is missing, in parallel.

Usage: python -m sim.run_all [--workers N]   (default: all cores but one)
"""
import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sim.run_sim import DATA, run
from sim.scenarios import SCENARIOS, seeds_for


def job(args):
    m = run(*args)
    return f"{m['run_id']}: {m['sim_seconds']} s, left {m['agents_left']}, wall {m['wall_seconds']} s, peaks {m['peak_density']}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()
    todo = [(n, s) for n in SCENARIOS for s in seeds_for(n)
            if not (DATA / "truth" / f"{n}-s{s:02d}.csv").exists()]
    print(f"{len(todo)} runs to do, {args.workers} workers", flush=True)
    with ProcessPoolExecutor(args.workers) as pool:
        for line in pool.map(job, todo):
            print(line, flush=True)
