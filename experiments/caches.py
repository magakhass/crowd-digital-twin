"""Build the per-run caches (true zone counts, sensor detections) in parallel before the
experiments start. Every job writes its own file, so workers never write the same one."""
import itertools
from concurrent.futures import ProcessPoolExecutor

from evaluation.truth import truth
from sensors import emulator


def _one(job):
    rid, mode, noise = job
    if mode is None:
        truth(rid)
    else:
        emulator.observe(rid, mode, noise)
    return rid


def build(runs, levels, workers):
    jobs = [(r, None, None) for r in runs]
    jobs += [(r, m, n) for r in runs for m, n in itertools.product(("phones", "tags"), levels)]
    with ProcessPoolExecutor(workers) as pool:
        for i, _ in enumerate(pool.map(_one, jobs)):
            if (i + 1) % 20 == 0 or i + 1 == len(jobs):
                print(f"caches {i + 1}/{len(jobs)}", flush=True)
