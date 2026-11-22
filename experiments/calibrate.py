"""Calibrate and freeze the twin's settings using calibration runs only (seeds 1-2).

capacity  bottleneck throughput, persons per metre per second (peak 30 s flow / 3 m)
kmax      effective storage density per zone (highest density seen, +5 %)
prior     audience head count at the start (mean, spread)
tau       forecast probability cut-off for alerts: highest detection rate with
          at most 1 false alarm per hour, using the bottleneck placement with 4 sensors
"""
import numpy as np

from evaluation.metrics import score_run, summarise
from evaluation.truth import truth
from shared.venue import Venue
from twin import params
from twin.observation import CAL_RUNS


def main():
    venue = Venue()
    exit_zone = venue.idx[venue.links[-1][1]]
    caps, peak, start = [], np.zeros(len(venue.zone_ids)), []
    for r in CAL_RUNS:
        occ, inflow = truth(r)
        flow30 = np.convolve(inflow[:, exit_zone], np.ones(30), "valid") / 30
        if flow30.max() > 1.5:
            caps.append(flow30.max() / 3.0)
        peak = np.maximum(peak, (occ / venue.area).max(0))
        start.append(occ[0, [venue.idx[z] for z in ("Z02", "Z03", "Z04")]])
    start = np.array(start)
    kmax = np.maximum(1.05 * peak, 2.0)
    params.save(capacity=float(np.mean(caps)), kmax=kmax.round(2).tolist(),
                prior_standing=[start.mean(0).round(1).tolist(), (start.std(0) + 0.15 * start.mean(0)).round(1).tolist()])
    print("capacity", np.mean(caps), "p/m/s =", 60 * np.mean(caps), "p/m/min; kmax", kmax.round(2))

    from twin.run_twin import run
    from experiments.placement import place
    best = None
    for tau in (0.3, 0.5, 0.7, 0.9):
        scores = [score_run(r, run(r, "twin", "phones", place("bottleneck", 4, "phones"), tau=tau)) for r in CAL_RUNS]
        s = summarise(scores)
        print(f"tau {tau}: pod {s['pod']:.2f}, fa/h {s['fa_per_hour']:.2f}, lead {s['median_lead_s']}")
        if s["fa_per_hour"] <= 1 and (best is None or s["pod"] >= best[1]):
            best = (tau, s["pod"])
    tau = best[0] if best else 0.9
    params.save(tau=tau)
    print("frozen tau", tau)


if __name__ == "__main__":
    main()
