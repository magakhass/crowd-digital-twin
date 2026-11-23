"""Calibrate and freeze the twin's settings using calibration runs only (seeds 1-2).

capacity  bottleneck throughput, persons per metre per second (peak 30 s flow / 3 m)
kmax      effective storage density per zone (highest density seen, +5 %, at least 2); when arriving, the
          audience zones keep the amber level of 3 so arrivals can walk through a standing crowd
turning   share of the net flow out of each zone that goes to each neighbour (or out), per event phase
prior     egress: audience head count per audience zone at the start (mean, spread)
settle    ingress: share of walking people in each audience zone who stop there, per second
arrival   ingress: mean arrival rate at the entrance until everyone is in (mean, spread)
tickets   ingress: expected attendance (tickets sold); arrivals stop when it is reached
tau       forecast probability cut-off for alerts: highest detection rate with at most 0.5 false alarms
          per hour (half our target, as a margin), pooled over every sensing setup of the experiments (both modes, options A and B,
          all four placements with 4 sensors, all noise levels), so it does not rest on a handful of events.
          Other venues (venue 2) keep the concert venue's tau: the cut-off is part of the method, and venue 2's
          calibration runs have no red events to choose it on. Calibrate the concert venue first.
"""
import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from evaluation.metrics import score_run, summarise
from evaluation.truth import movements, truth
from shared.venue import ACTIVE, DEFAULT, ROOT, Venue
from twin import params
from twin.observation import CAL_RUNS, EGRESS_CAL, INGRESS_CAL


def turning(runs, venue):
    # net moves between each pair of zones, so people stepping back and forth over a zone edge
    # do not turn into flows in both directions
    moves = sum(movements(r, venue)[0] for r in runs)
    nz = moves.shape[0]
    net = moves.copy()
    net[:, :nz] = np.maximum(moves[:, :nz] - moves[:, :nz].T, 0)
    return (net / np.maximum(net.sum(1, keepdims=True), 1)).round(4)


def main(workers):
    print("venue:", ACTIVE)
    venue = Venue()
    aud = [venue.idx[z] for z in venue.audience]
    caps, peak, start = [], np.zeros(len(venue.zone_ids)), []
    for r in EGRESS_CAL:
        occ, inflow = truth(r)
        for z, w in venue.gate_behind():  # peak 30 s flow through each gate, per metre of gate
            flow30 = np.convolve(inflow[:, venue.idx[z]], np.ones(30), "valid") / 30
            if flow30.max() > 0.5 * w:
                caps.append(flow30.max() / w)
        start.append(occ[0, aud])
    settles, walking, arrivals, crowd = 0, 0, [], []
    for r in INGRESS_CAL:
        _, s, w = movements(r, venue)
        settles, walking = settles + s, walking + w
        occ, _ = truth(r)
        full = int(np.argmax(occ.sum(1) >= occ.sum(1).max()))
        crowd.append(occ.sum(1).max())
        arrivals.append(occ[full].sum() / full)  # mean arrival rate until everyone is in
    for r in CAL_RUNS:
        occ, _ = truth(r)
        peak = np.maximum(peak, (occ / venue.area).max(0))
    start = np.array(start)
    kmax = np.maximum(1.05 * peak, 2.0)
    # arriving: audience zones keep room to walk through a standing crowd (amber level)
    kmax_in = np.maximum(kmax, np.where(np.array(venue.kind) == "static", venue.amber, 0))
    params.save(capacity=float(np.mean(caps)), kmax={"egress": kmax.round(2).tolist(), "ingress": kmax_in.round(2).tolist()},
                prior_standing=[start.mean(0).round(1).tolist(), (start.std(0) + 0.15 * start.mean(0)).round(1).tolist()],
                turning={"egress": turning(EGRESS_CAL, venue).tolist(), "ingress": turning(INGRESS_CAL, venue).tolist()},
                settle=(settles[aud] / np.maximum(walking[aud], 1)).round(4).tolist(),
                arrival=[round(float(np.mean(arrivals)), 2), round(0.5 * float(np.mean(arrivals)), 2)],
                tickets=int(np.mean(crowd)))
    print("capacity", np.mean(caps), "p/m/s =", 60 * np.mean(caps), "p/m/min; kmax", kmax.round(2), kmax_in.round(2))

    if ACTIVE == DEFAULT:
        choose_tau(workers)
    else:
        src = ROOT / "data" / "results" / "params.json"
        tau = json.loads(src.read_text())["tau"]  # fails here if the concert venue isn't calibrated yet
        params.save(tau=tau, tau_from=DEFAULT)
        print("tau", tau, "taken from", DEFAULT)


TAUS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
FA_LIMIT = 0.5  # false alarms per hour on calibration runs: half our target, since test runs gave about twice as many


def setups():
    from sensors.emulator import NOISE_LEVELS
    return [(mode, option, strategy, noise) for mode in ("phones", "tags") for option in "AB"
            for strategy in ("bottleneck", "greedy_mi", "entrance_exit", "random") for noise in NOISE_LEVELS]


def _twin(job):
    from experiments.placement import place
    from twin.run_twin import run
    r, (mode, option, strategy, noise) = job
    seed = int(r[-2:])
    out = run(r, "twin", mode, place(strategy, 4, mode, seed, noise), sketches=option == "B", seed=seed, noise=noise)
    return r, out


def choose_tau(workers):
    from sensors import emulator
    from twin.run_twin import alert_onsets
    from experiments import caches
    caches.build(CAL_RUNS, emulator.NOISE_LEVELS, workers)  # in parallel, one file per job
    jobs = [(r, s) for s in setups() for r in CAL_RUNS]
    print(len(jobs), "twin runs,", workers, "workers")
    with ProcessPoolExecutor(workers) as ex:
        results = list(ex.map(_twin, jobs, chunksize=4))
    best = None
    for tau in TAUS:
        s = summarise([score_run(r, {**out, "red": alert_onsets(out["p_red"] >= tau, out["t"])}) for r, out in results])
        print(f"tau {tau}: pod {s['pod']:.2f}, fa/h {s['fa_per_hour']:.2f}, lead {s['median_lead_s']}")
        if s["fa_per_hour"] <= FA_LIMIT and (best is None or s["pod"] >= best[1]):
            best = (tau, s["pod"])
    tau = best[0] if best else TAUS[-1]
    params.save(tau=tau)
    print("frozen tau", tau)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    main(ap.parse_args().workers)
