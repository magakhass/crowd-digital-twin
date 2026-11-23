"""Test our simulator against Jülich bottleneck experiments (HERMES 2009 and crowdqueue 2018).

We rebuild each experiment in JuPedSim: same room and bottleneck, the same routing and gridlock
breaker as in our venue (sim/behaviour.py), and compare the flow through the bottleneck and the
density just in front of it with the recordings. Coordinates are turned so that people walk in +x,
like in the venue. Our walking settings come from Xu et al. (2021); these runs only test them.
The grid mode shows that changing time gap and radius does not close the flow gap.

Data (Jülich pedestrian dynamics data archive), not in git:
  data/julich/hermes/ao-{width}-400.txt + metadata.json   HERMES 2009 bottleneck, cm, 16 fps (doi 10.34735/ped.2009.6)
  data/julich/crowdqueue/{run}.txt + metadata.json        crowdqueue 2018 entrance gate, m, 25 fps (doi 10.34735/ped.2018.1)

Usage: python -m sim.validate_julich recorded   flow and density measured in the recordings
       python -m sim.validate_julich check      our settings on all runs, 3 seeds -> data/results/avm_check*.csv
       python -m sim.validate_julich grid       time gap x radius sweep on the HERMES widths -> data/results/avm_grid.csv
"""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from collections import namedtuple
from pathlib import Path

import jupedsim as jps
import numpy as np
import pandas as pd
from shapely import affinity, wkt
from shapely.geometry import box

from sim.behaviour import AVM, DT, TIME_GAP, Crowd, desired_speed

DATA = Path(__file__).resolve().parents[1] / "data"
P = namedtuple("P", "t x y")
FRONT = 2.0  # m: depth of the area in front of the bottleneck where density is measured

# HERMES widths 2.4/3.6/4.4/5.0 m (grid) and 3.0 m, like our gate
CAL = [f"ao-{w}-400" for w in (240, 360, 440, 500)]
TEST = ["ao-300-400"]
# crowdqueue, 0.5 m gate: low-motivation runs to test, high-motivation (pushing) to show the gap;
# 010/080/200 have uncorrected trajectories, 020 is the only "h+" run
CQ_LOW = ["040_c_56_h-", "060_c_45_h-", "100_c_12_h-", "120_c_12_h-", "160_q_56_h-", "180_q_12_h-",
          "240_q_23_h-", "260_q_45_h-", "280_c_34_h-"]
CQ_HIGH = ["030_c_56_h0", "050_c_45_h0", "070_c_23_h0", "090_c_12_h0", "110_c_12_h0", "150_q_56_h0",
           "170_q_12_h0", "190_q_34_h0", "230_q_23_h0", "250_q_45_h0", "270_c_34_h0"]


def setup(run):
    """Turned geometry, gate and recorded trajectories of one run."""
    hermes = run.startswith("ao-")
    folder = DATA / "julich" / ("hermes" if hermes else "crowdqueue")
    meta = json.loads((folder / "metadata.json").read_text())
    info = next(r for r in meta["experiment"]["run"] if r["run_name"] == run)
    room = wkt.loads(info["wkt_geometry"])
    d = pd.read_csv(folder / f"{run}.txt", sep=r"\s+", comment="#", header=None, names=["id", "frame", "x", "y", "z"])
    if hermes:
        d[["x", "y"]] /= 100
        d["t"] = d["frame"] / 16
        walls = [h.bounds for h in room.interiors]
        x0 = max(b[2] for b in walls if b[2] < 1.5)  # inner ends of the two walls
        x1 = min(b[0] for b in walls if b[0] > 0.5)
        xc = (x0 + x1) / 2
        # close the gaps beside the walls so the opening is the only way through
        room = box(*room.exterior.bounds).difference(box(-6, -0.5, x0, 0.5)).difference(box(x1, -0.5, 6, 0.5))
        half, entry, gate_x, corner_y = (x1 - x0) / 2, -0.5, 0.0, (x1 - x0) / 2
        side = 1.0
    else:
        d["t"] = d["frame"] / 25
        xc, half, entry, gate_x, corner_y = 0.0, 0.25, 0.0, 0.6, 0.4
        side = min(1.0, float(info["parameter"]["corridor_width"]) / 2)
    # turn: walking direction -y becomes +x, gate centred on y = 0
    room = affinity.translate(room, xoff=-xc)
    room = affinity.affine_transform(room, [0, -1, 1, 0, 0, 0])
    d["x"], d["y"] = -d["y"], d["x"] - xc
    b = room.bounds
    return {"room": room, "half": half, "entry": entry, "gate_x": gate_x, "side": side, "hermes": hermes,
            "corners": [(entry, corner_y), (entry, -corner_y)], "exit": box(min(gate_x + 4, b[2] - 0.5), b[1], b[2], b[3]).intersection(room),  # leave up to 4 m past the gate
            "rec": d[["id", "t", "x", "y"]]}


def measure(d, s):
    """Flow (p/s and p/m/s) over the middle 80 % of passages, and density in front of the gate meanwhile."""
    d = d.sort_values(["id", "t"])
    px = d.groupby("id")["x"].shift()
    cross = d[(px < s["gate_x"]) & (d["x"] >= s["gate_x"])]
    t = np.sort(cross.groupby("id")["t"].min().to_numpy())  # first passage of each person
    if len(t) < 10:
        return {"flow": 0.0, "spec_flow": 0.0, "density": np.nan, "passed": len(t)}
    a, b = int(0.1 * len(t)), int(0.9 * len(t))
    flow = (b - a) / (t[b] - t[a])
    side = s["side"]
    during = d[(d["t"] >= t[a]) & (d["t"] <= t[b])]
    inside = during[(during["x"] >= s["entry"] - FRONT) & (during["x"] < s["entry"]) & (during["y"].abs() <= side)]
    dens = inside.groupby("t").size().reindex(np.unique(during["t"]), fill_value=0)
    return {"flow": round(float(flow), 3), "spec_flow": round(float(flow / (2 * s["half"])), 3),
            "density": round(float(dens.median() / (FRONT * 2 * side)), 3), "passed": len(t)}


def simulate(run, time_gap, radius, seed=1, s=None, breaker=True, **avm):
    s = s or setup(run)
    # HERMES: the cameras miss part of the waiting crowd, so we place everyone in front of the bottleneck;
    # crowdqueue: everyone is visible at the start, so we use their recorded starting spots
    start = "waiting" if s["hermes"] else "seen"
    if not s["hermes"]:
        avm.setdefault("wall_buffer_distance", 0.05)  # 0.5 m gate: an agent plus the default 0.1 m buffer would not fit
    rng = np.random.default_rng(seed)
    sim = jps.Simulation(model=jps.AnticipationVelocityModel(rng_seed=seed), geometry=s["room"], dt=DT)
    exit_id = sim.add_exit_stage(s["exit"])
    crowd = Crowd(sim, s["room"], [(exit_id, s["gate_x"], -s["half"], s["half"], s["corners"])], rng, DT)
    params = {**{k: v for k, v in AVM.items() if k != "radius"}, **avm}

    if start == "seen":
        # people appear where the cameras first saw them (or as soon as that spot is free)
        first = s["rec"].sort_values("t").groupby("id").first().sort_values("t")
        todo = [P(*r) for r in first[["t", "x", "y"]].itertuples(index=False)]
    else:
        # everyone waits in front of the bottleneck and sets off within the first second, like on the command
        b = s["room"].bounds
        area = box(b[0] + 0.3, b[1] + 0.3, s["entry"] - 0.6, b[3] - 0.5).intersection(s["room"])
        pos = jps.distribute_by_number(polygon=area, number_of_agents=s["rec"]["id"].nunique(), distance_to_agents=0.4,
                                       distance_to_polygon=0.25, seed=seed)
        todo = [P(float(rng.uniform(0, 1)), x, y) for x, y in pos]
    rows, it, t_stop = [], 0, s["rec"]["t"].max() + 120
    while (todo or sim.agent_count()) and sim.elapsed_time() < t_stop:
        t = sim.elapsed_time()
        left = []
        for p in todo:
            if p.t > t or any(True for _ in sim.agents_in_range((p.x, p.y), 2 * radius)):
                left.append(p)  # not yet seen, or the spot is still taken
                continue
            j, st = crowd.lane()
            try:
                aid = sim.add_agent(jps.AnticipationVelocityModelAgentParameters(
                    position=(p.x, p.y), journey_id=j, stage_id=st, radius=radius, time_gap=time_gap,
                    desired_speed=desired_speed(rng), **params))
                crowd.start(aid)
            except Exception:
                left.append(p)
        todo = left
        if breaker:
            crowd.unjam(it, t)
        sim.iterate()
        it += 1
        if it % 5 == 0:
            rows += [(a.id, sim.elapsed_time(), *a.position) for a in sim.agents()]
    return pd.DataFrame(rows, columns=["id", "t", "x", "y"]), sim.agent_count() + len(todo)


def one(job):
    run, tg, r, seed = job
    s = setup(run)
    d, stuck = simulate(run, tg, r, seed, s)
    return {"run": run, "time_gap": tg, "radius": r, "seed": seed, "left_over": stuck, **measure(d, s)}


def recorded(runs):
    out = {}
    for run in runs:
        s = setup(run)
        out[run] = measure(s["rec"], s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["grid", "check", "recorded"])
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--time-gap", type=float)
    ap.add_argument("--radius", type=float)
    a = ap.parse_args()
    (DATA / "results").mkdir(parents=True, exist_ok=True)

    if a.what == "recorded":
        print(pd.DataFrame(recorded(CAL + TEST + CQ_LOW + CQ_HIGH)).T.to_string())
        return
    if a.what == "grid":
        runs = CAL
        jobs = [(run, tg, r, 1) for run, tg, r in product(CAL, [0.2, 0.25, 0.3, 0.4], [0.15, 0.165, 0.18])]
    else:
        runs = CAL + TEST + CQ_LOW + CQ_HIGH
        tg, r = a.time_gap or TIME_GAP, a.radius or AVM["radius"]
        jobs = [(run, tg, r, s) for run in runs for s in (1, 2, 3)]
    rec = recorded(runs)
    with ProcessPoolExecutor(a.workers) as ex:
        df = pd.DataFrame(list(ex.map(one, jobs)))
    for k in ("flow", "spec_flow", "density"):
        df[k + "_rec"] = df["run"].map(lambda r: rec[r][k])
    df.to_csv(DATA / "results" / f"avm_{a.what}.csv", index=False)
    if a.what == "grid":
        # mean relative error of specific flow and density, equally weighted
        df["err"] = ((df["spec_flow"] / df["spec_flow_rec"] - 1).abs() + (df["density"] / df["density_rec"] - 1).abs()) / 2
        print(df.groupby(["time_gap", "radius"])["err"].mean().sort_values().head(8).round(3).to_string())
        print(df.pivot_table(index=["time_gap", "radius"], columns="run", values=["spec_flow", "density"]).round(2).to_string())
    else:
        df["set"] = np.where(df["run"].str.startswith("ao-"), df["run"],
                             np.where(df["run"].isin(CQ_LOW), "crowdqueue low motivation", "crowdqueue high motivation"))
        cols = ["flow", "flow_rec", "spec_flow", "spec_flow_rec", "density", "density_rec", "left_over"]
        out = df.groupby("set")[cols].mean().round(2)
        out.to_csv(DATA / "results" / "avm_check_summary.csv")
        print(out.to_string())


if __name__ == "__main__":
    main()
