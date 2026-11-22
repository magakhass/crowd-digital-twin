"""Run one JuPedSim scenario and write ground truth.

Outputs (data/):
  trajectories/{run}.csv   id, frame, x, y at 5 frames per second
  truth/{run}.csv          per-second true head count in every zone
  trajectories/{run}.json  run settings and summary

Usage: python -m sim.run_sim surge 3
"""
import json
import sys
import time
from pathlib import Path

import jupedsim as jps
import numpy as np
from shapely.geometry import box

from shared.venue import Venue
from sim.scenarios import SCENARIOS, departures

DATA = Path(__file__).resolve().parents[1] / "data"
DT = 0.05
FPS = 5
# AVM parameters validated by Xu, Chraibi and Seyfried (2021), Table 3
AVM = dict(radius=0.18, strength_neighbor_repulsion=6.0, range_neighbor_repulsion=0.01,
           reaction_time=0.3, anticipation_time=0.75)
EXIT = box(41, -1.5, 42, 1.5)
BAR = box(-17, 10, -15, 12)  # where counterflow people are heading (Z02, north wall)


def run(name, seed):
    cfg = SCENARIOS[name]
    run_id = f"{name}-s{seed:02d}"
    venue = Venue()
    rng = np.random.default_rng(seed)

    # geometry: the twin's venue file is never changed, only the simulated world
    walkable = venue.walkable
    if "block" in cfg:
        x0, x1, y0, y1 = cfg["block"]
        walkable = walkable.difference(box(x0, y0, x1, y1))
    sim = jps.Simulation(model=jps.AnticipationVelocityModel(rng_seed=seed), geometry=walkable, dt=DT)
    # route through the middle of the bottleneck so nobody gets pinned on its corners
    exit_id = sim.add_exit_stage(EXIT)
    funnel_y = (-1.5 + cfg["block"][2]) / 2 if "block" in cfg else 0.0  # middle of the open part
    funnel = sim.add_waypoint_stage((29.0, funnel_y), 0.6 if "block" in cfg else 0.8)
    jd = jps.JourneyDescription([funnel, exit_id])
    jd.set_transition_for_stage(funnel, jps.Transition.create_fixed_transition(exit_id))
    out_journey = sim.add_journey(jd)
    time_gap = 0.6 if "inflow" in cfg else 0.5

    def speed():
        return float(np.clip(rng.normal(1.55, 0.18), 0.8, 2.2))

    # audience: standing still until their departure time
    audience = venue.rects["Z02"].union(venue.rects["Z03"]).union(venue.rects["Z04"])
    starts = jps.distribute_by_number(polygon=audience, number_of_agents=cfg["n"], distance_to_agents=0.6,
                                      distance_to_polygon=0.3, seed=seed)
    leave_at = departures(name, cfg["n"], rng)
    waiting = []
    for p, t in zip(starts, leave_at):
        aid = sim.add_agent(jps.AnticipationVelocityModelAgentParameters(
            position=p, journey_id=out_journey, stage_id=funnel, desired_speed=0.0, time_gap=time_gap, **AVM))
        waiting.append((t, aid, speed()))
    waiting.sort()

    # counterflow: people entering from the exit side and walking to the bar
    incoming = []
    if "inflow" in cfg:
        bar_id = sim.add_exit_stage(BAR)
        back = sim.add_waypoint_stage((31.0, 0.0), 1.0)
        jd = jps.JourneyDescription([back, bar_id])
        jd.set_transition_for_stage(back, jps.Transition.create_fixed_transition(bar_id))
        in_journey = sim.add_journey(jd)
        t0, t1 = cfg["inflow_window"]
        incoming = sorted(rng.uniform(t0, t1, cfg["inflow"]))

    rows, iteration, wi = [], 0, 0
    last_change, last_count = 0.0, -1
    t_end = float(leave_at.max()) + 600
    wall = time.time()
    while sim.elapsed_time() < t_end:
        t = sim.elapsed_time()
        while wi < len(waiting) and waiting[wi][0] <= t:
            _, aid, v = waiting[wi]
            sim.agent(aid).model.desired_speed = v
            wi += 1
        while incoming and incoming[0] <= t:
            try:
                sim.add_agent(jps.AnticipationVelocityModelAgentParameters(
                    position=(float(rng.uniform(37, 40.5)), float(rng.uniform(-5.5, 5.5))), journey_id=in_journey,
                    stage_id=back, desired_speed=speed(), time_gap=time_gap, **AVM))
                incoming.pop(0)
            except Exception:
                break  # spawn spot occupied, retry next step
        if iteration % int(1 / (DT * FPS)) == 0:
            frame = iteration // int(1 / (DT * FPS))
            rows += [(a.id, frame, a.position[0], a.position[1]) for a in sim.agents()]
        if wi == len(waiting) and not incoming and sim.agent_count() == 0:
            break
        # deadlock guard: nobody has left for 120 s after everyone has set off
        if sim.agent_count() != last_count:
            last_count, last_change = sim.agent_count(), t
        elif wi == len(waiting) and t - last_change > 120:
            break
        sim.iterate()
        iteration += 1

    traj = np.array(rows, float)
    (DATA / "trajectories").mkdir(parents=True, exist_ok=True)
    np.savetxt(DATA / "trajectories" / f"{run_id}.csv", traj, fmt=["%d", "%d", "%.3f", "%.3f"],
               delimiter=",", header="id,frame,x,y", comments="")

    # per-second truth counts per zone
    sec = traj[traj[:, 1] % FPS == 0]
    frames = np.unique(sec[:, 1]).astype(int)
    truth = np.zeros((frames.max() // FPS + 1, len(venue.zone_ids)), int)
    for f in frames:
        s = sec[sec[:, 1] == f]
        truth[f // FPS] = venue.counts(s[:, 2], s[:, 3])
    (DATA / "truth").mkdir(parents=True, exist_ok=True)
    np.savetxt(DATA / "truth" / f"{run_id}.csv", np.column_stack([np.arange(len(truth)), truth]), fmt="%d",
               delimiter=",", header="t," + ",".join(venue.zone_ids), comments="")

    meta = {"run_id": run_id, "scenario": name, "seed": seed, "model": "AnticipationVelocityModel",
            "avm": AVM, "time_gap": time_gap, "dt": DT, "fps": FPS, "n_audience": cfg["n"],
            "n_inflow": cfg.get("inflow", 0), "sim_seconds": round(sim.elapsed_time(), 1),
            "agents_left": sim.agent_count(), "wall_seconds": round(time.time() - wall, 1),
            "peak_density": {z: round(float(truth[:, i].max() / venue.area[i]), 2)
                             for i, z in enumerate(venue.zone_ids)}}
    (DATA / "trajectories" / f"{run_id}.json").write_text(json.dumps(meta, indent=1))
    return meta


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], int(sys.argv[2])), indent=1))
