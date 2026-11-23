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
from shapely.geometry import Point, box
from shapely.ops import unary_union

from shared.venue import Venue, data_dir
from sim.behaviour import AVM, COUNTERFLOW_EXTRA, DT, TIME_GAP, Crowd, desired_speed
from sim.scenarios import SCENARIOS, arrivals, departures

DATA = data_dir()
FPS = 5
ORDER_NOISE = 8.0    # m: people nearer the exit tend to leave first, this much randomness on top (our assumption)
MOUTH_CLEAR = 4.0        # m: arrivals do not pick a spot this close to where they come in (our assumption)


def place(area, n, seed, tries=5):
    # random start spots; at 1500 people the packing occasionally comes up a couple short,
    # so try the next placement seed (earlier runs got theirs on the first try, so they don't change)
    for k in range(tries):
        try:
            return jps.distribute_by_number(polygon=area, number_of_agents=n, distance_to_agents=0.6,
                                            distance_to_polygon=0.3, seed=seed + 1000 * k)
        except jps.distributions.AgentNumberError:
            if k == tries - 1:
                raise


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
    # exits, gates (the open part, if blocked), entrance and bar, all from the venue file
    gates = []
    for k, gate in enumerate(venue.gates):
        area = venue.exit_areas[venue.exit_ids.index(gate["exit"]) if "exit" in gate else 0]
        lo, hi = gate["y_min"], (cfg["block"][2] if "block" in cfg and k == 0 else gate["y_max"])
        jamb_x = venue.bounds[venue.idx[gate["zone"]]][0]
        corners = [tuple(c) for c in gate["approach_corners"]] + [(jamb_x, lo), (jamb_x, hi)]  # corners people walk round
        gates.append((sim.add_exit_stage(area), gate["x"], lo, hi, corners))
    gate, ent = venue.gate, venue.entrance
    gate_x = gate["x"]
    bar_id = sim.add_exit_stage(venue.poi["bar"]) if "inflow" in cfg else None
    entrance = (ent["opens_at"]["x"], ent["opens_at"]["y"])  # where the entrance opens into the hall
    cp = ent.get("checkpoint")  # ticket check people pass before walking to their spot
    door = (cp["x_from"], cp["x_to"], (cp["y_min"] + cp["y_max"]) / 2, (cp["y_max"] - cp["y_min"]) / 2) if cp else None
    crowd = Crowd(sim, walkable, gates, rng, DT, bar_id, mouth=(*entrance, ent["opens_at"]["half_width"]), door=door)
    time_gap = TIME_GAP + (COUNTERFLOW_EXTRA if "inflow" in cfg else 0.0)

    def speed():
        return desired_speed(rng)

    audience = unary_union([venue.rects[z] for z in venue.audience])
    ingress = cfg.get("movement") == "ingress"
    if ingress:
        audience = audience.difference(Point(entrance).buffer(MOUTH_CLEAR))  # nobody chooses to stand in the doorway
    spots = place(audience, cfg["n"], seed)
    waiting, coming = [], []
    if ingress:
        # arrivals: earlier ones take spots further from the entrance, with noise
        come_at = arrivals(name, cfg["n"], rng)
        far = np.hypot(np.array(spots)[:, 0] - entrance[0], np.array(spots)[:, 1] - entrance[1])
        order = np.argsort(-(far + rng.normal(0, ORDER_NOISE, cfg["n"])))
        coming = [(float(t), spots[i]) for t, i in zip(come_at, order)]
        steer = sim.add_direct_steering_stage()
        to_spot = sim.add_journey(jps.JourneyDescription([steer]))
        leave_at = come_at
    else:
        # audience: standing still until their departure time; everyone uses the nearest gate, and
        # the earliest departure times go to people nearer it, with noise
        leave_at = np.sort(departures(name, cfg["n"], rng))
        xy = np.array(spots)
        dist = np.array([np.hypot(xy[:, 0] - g["x"], xy[:, 1] - (g["y_min"] + g["y_max"]) / 2) for g in venue.gates])
        nearest = dist.argmin(0)
        near = dist.min(0) + rng.normal(0, ORDER_NOISE, cfg["n"])
        leave_at = leave_at[np.argsort(np.argsort(near))]
        for p, t, g in zip(spots, leave_at, nearest):
            j, st = crowd.lane(int(g))
            aid = sim.add_agent(jps.AnticipationVelocityModelAgentParameters(
                position=p, journey_id=j, stage_id=st, desired_speed=0.0, time_gap=time_gap, **AVM))
            crowd.gate_of[aid] = int(g)
            waiting.append((t, aid, speed()))
        waiting.sort()

    # counterflow: people entering from the exit side and walking to the bar
    incoming = []
    if "inflow" in cfg:
        back = sim.add_waypoint_stage((gate_x + 2.0, (gate["y_min"] + gate["y_max"]) / 2), 1.0)  # just past the gate
        jd = jps.JourneyDescription([back, bar_id])
        jd.set_transition_for_stage(back, jps.Transition.create_fixed_transition(bar_id))
        in_journey = sim.add_journey(jd)
        out = venue.poi["outside_exit"]
        t0, t1 = cfg["inflow_window"]
        incoming = sorted(rng.uniform(t0, t1, cfg["inflow"]))

    rows, iteration, wi = [], 0, 0
    last_change, last_count = 0.0, -1
    t_end = float(leave_at.max()) + (300 if ingress else 600)
    wall = time.time()
    while sim.elapsed_time() < t_end:
        t = sim.elapsed_time()
        while wi < len(waiting) and waiting[wi][0] <= t:
            _, aid, v = waiting[wi]
            sim.agent(aid).model.desired_speed = v
            crowd.start(aid)
            wi += 1
        while coming and coming[0][0] <= t:
            # come in through the entrance at a free spot across Z01; if none is free they wait outside
            sp = ent["spawn"]
            pos = (float(rng.uniform(sp["x_min"], sp["x_max"])), float(rng.uniform(sp["y_min"], sp["y_max"])))
            if any(True for _ in sim.agents_in_range(pos, 0.45)):
                break
            aid = sim.add_agent(jps.AnticipationVelocityModelAgentParameters(
                position=pos, journey_id=to_spot, stage_id=steer, desired_speed=speed(), time_gap=time_gap, **AVM))
            crowd.arrive(aid, coming.pop(0)[1])
        while incoming and incoming[0] <= t:
            try:
                aid = sim.add_agent(jps.AnticipationVelocityModelAgentParameters(
                    position=(float(rng.uniform(out.bounds[0], out.bounds[2])), float(rng.uniform(out.bounds[1], out.bounds[3]))),
                    journey_id=in_journey,
                    stage_id=back, desired_speed=speed(), time_gap=time_gap, **AVM))
                crowd.start(aid, inbound=True)
                incoming.pop(0)
            except Exception:
                break  # spawn spot occupied, retry next step
        if iteration % int(1 / (DT * FPS)) == 0:
            frame = iteration // int(1 / (DT * FPS))
            rows += [(a.id, frame, a.position[0], a.position[1]) for a in sim.agents()]
        crowd.unjam(iteration, t)
        if wi == len(waiting) and not incoming and not coming and sim.agent_count() == 0:
            break
        if ingress and not coming and not crowd.moving:
            break  # everyone has come in and is standing
        # deadlock guard: nobody has left for 120 s after everyone has set off
        if sim.agent_count() != last_count:
            last_count, last_change = sim.agent_count(), t
        elif wi == len(waiting) and not ingress and t - last_change > 120:
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
            "agents_left": len(crowd.moving) + len(coming) if ingress else sim.agent_count(), "wall_seconds": round(time.time() - wall, 1),
            "settled": crowd.settled, "lanes": len(crowd.lanes), "order_noise_m": ORDER_NOISE, "unjam_events": crowd.unjams,
            "peak_density": {z: round(float(truth[:, i].max() / venue.area[i]), 2)
                             for i, z in enumerate(venue.zone_ids)}}
    (DATA / "trajectories" / f"{run_id}.json").write_text(json.dumps(meta, indent=1))
    return meta


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], int(sys.argv[2])), indent=1))
