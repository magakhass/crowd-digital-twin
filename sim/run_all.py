"""Run every scenario x seed that is missing, in parallel.

Usage: python -m sim.run_all [--workers N]   (default: all cores but one)
Venue 2: set CROWDTWIN_VENUE=festival_hall_v2 first (PowerShell: $env:CROWDTWIN_VENUE="festival_hall_v2").
A failed run would stop the batch from finishing, so it is reported and the rest carry on.
"""
import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sim.run_sim import DATA, run
from shared.venue import ACTIVE
from sim.scenarios import SCENARIOS, VALID_SHARE, seeds_for, valid


def job(args):
    try:
        m = run(*args)
    except Exception as e:  # one failed run shouldn't stop the rest; finished runs are skipped next time
        return f"{args[0]}-s{args[1]:02d}: FAILED ({type(e).__name__}: {e})"
    return f"{m['run_id']}: {m['sim_seconds']} s, left {m['agents_left']}, wall {m['wall_seconds']} s, peaks {m['peak_density']}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()
    print(f"venue: {ACTIVE}", flush=True)
    failed = set()
    while True:  # again if a run broke the validity rule and needs a replacement seed
        todo = [(n, s) for n in SCENARIOS for s in seeds_for(n)
                if not (DATA / "truth" / f"{n}-s{s:02d}.csv").exists() and (n, s) not in failed]
        if not todo:
            break
        print(f"{len(todo)} runs to do, {args.workers} workers", flush=True)
        with ProcessPoolExecutor(args.workers) as pool:
            for args_, line in zip(todo, pool.map(job, todo)):
                print(line, flush=True)
                if "FAILED" in line:
                    failed.add(args_)
    bad = [f"{n}-s{s:02d}" for n in SCENARIOS for s in range(1, 40) if valid(f"{n}-s{s:02d}") is False]
    if bad:
        print(f"not used (under {VALID_SHARE:.0%} of the crowd got out): {', '.join(bad)}", flush=True)
