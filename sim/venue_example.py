"""Quick check of a venue file: is it valid, and does a crowd get out of it in JuPedSim?

Builds the walkable area from the zone rectangles, puts people on the standing (static)
zones, sends them all to the exit and saves a picture every minute with each zone coloured
by its density. This is a sanity check for a new venue, not our full simulator (sim/run_sim.py
adds departure profiles, gate lanes and the gridlock breaker).

Usage: python -m sim.venue_example shared/venues/concert_venue_v1.json --people 1200 --seconds 600
Pictures and a density table go to data/venue_check/<venue_id>/.
"""
import argparse
import json
from pathlib import Path

import jupedsim as jps
import matplotlib
import numpy as np
from shapely.geometry import Point, box
from shapely.ops import unary_union

from sim.behaviour import AVM, DT, TIME_GAP, desired_speed

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data" / "venue_check"


def check(v):
    """The rules the rest of our code relies on; returns a list of problems (empty = fine)."""
    problems, zones = [], v["zones"]
    ids = [z["id"] for z in zones]
    if len(set(ids)) != len(ids):
        problems.append("zone ids are not unique")
    for z in zones:
        w, h = z["x_max"] - z["x_min"], z["y_max"] - z["y_min"]
        if w <= 0 or h <= 0:
            problems.append(f"{z['id']}: x_max/y_max must be larger than x_min/y_min")
        if abs(w * h - z["area_m2"]) > 1e-6:
            problems.append(f"{z['id']}: area_m2 is {z['area_m2']}, rectangle is {w * h}")
        if not 0 < z["amber_persons_m2"] < z["red_persons_m2"]:
            problems.append(f"{z['id']}: need 0 < amber < red")
        if z["type"] not in ("static", "dynamic"):
            problems.append(f"{z['id']}: type must be static (standing) or dynamic (walking)")
    rects = [box(z["x_min"], z["y_min"], z["x_max"], z["y_max"]) for z in zones]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if rects[i].intersection(rects[j]).area > 0:
                problems.append(f"{ids[i]} and {ids[j]} overlap")
    by_id = dict(zip(ids, rects))
    for link in v["links"]:
        edge = by_id[link["from"]].intersection(by_id[link["to"]]).length
        if not 0 < link["width_m"] <= edge + 1e-6:
            problems.append(f"link {link['from']}-{link['to']}: width {link['width_m']} m but shared edge {edge:.1f} m")
    walk = unary_union(rects)
    if walk.geom_type != "Polygon":
        problems.append("zones do not form one connected area")
    for key in ("spawn_points", "exit_points"):
        for p in v.get(key, []):
            if not walk.contains(Point(p["x"], p["y"])):
                problems.append(f"{key} {p['id']} is outside the zones")
    for c in v.get("sensor_candidates", []):
        if not walk.buffer(1.0).contains(Point(c["x"], c["y"])):
            problems.append(f"sensor spot {c['id']} is not on or next to the walkable area")
    # simulation details: exits, gates, entrances, places of interest, presets and risk zones
    for key in ("exit_areas", "points_of_interest"):
        for a in v.get(key, []):
            if box(a["x_min"], a["y_min"], a["x_max"], a["y_max"]).intersection(walk).area <= 0:
                problems.append(f"{key} {a['id']} is outside the zones")
    for g in v.get("gates", []):
        if g["zone"] not in ids:
            problems.append(f"gate {g['id']}: zone {g['zone']} does not exist")
    for e in v.get("entrances", []):
        sp = e["spawn"]
        if not walk.contains(box(sp["x_min"], sp["y_min"], sp["x_max"], sp["y_max"])):
            problems.append(f"entrance {e['id']}: spawn area is not fully inside the zones")
    cands = {c["id"] for c in v.get("sensor_candidates", [])}
    for name, spots in v.get("placement_presets", {}).items():
        if not set(spots) <= cands:
            problems.append(f"placement preset {name} uses unknown sensor spots {sorted(set(spots) - cands)}")
    for z in v.get("risk_zones", []):
        if z not in ids:
            problems.append(f"risk zone {z} does not exist")
    return problems


def simulate(v, people, seconds, seed=1):
    zones = v["zones"]
    rects = {z["id"]: box(z["x_min"], z["y_min"], z["x_max"], z["y_max"]) for z in zones}
    walk = unary_union(list(rects.values()))
    rng = np.random.default_rng(seed)
    sim = jps.Simulation(model=jps.AnticipationVelocityModel(rng_seed=seed), geometry=walk, dt=DT)

    # exit: a 1 m square around the exit point, inside the walkable area
    e = v["exit_points"][0]
    exit_id = sim.add_exit_stage(box(e["x"] - 0.5, e["y"] - 0.5, e["x"] + 0.5, e["y"] + 0.5).intersection(walk))
    journey = sim.add_journey(jps.JourneyDescription([exit_id]))

    # everyone starts on the standing zones, at least 0.6 m apart, and leaves within the first 5 minutes
    standing = unary_union([rects[z["id"]] for z in zones if z["type"] == "static"])
    spots = jps.distribute_by_number(polygon=standing, number_of_agents=people, distance_to_agents=0.6,
                                     distance_to_polygon=0.3, seed=seed)
    leave = rng.uniform(0, 300, people)
    agents = [sim.add_agent(jps.AnticipationVelocityModelAgentParameters(
        position=p, journey_id=journey, stage_id=exit_id, desired_speed=0.0, time_gap=TIME_GAP, **AVM)) for p in spots]

    counts, frames = [], {}
    while sim.elapsed_time() < seconds and sim.agent_count():
        t = sim.elapsed_time()
        for k in np.nonzero((leave <= t) & (leave > t - DT))[0]:
            sim.agent(agents[k]).model.desired_speed = desired_speed(rng)
        sim.iterate()
        if sim.iteration_count() % int(1 / DT) == 0:  # once a second: people per zone
            xy = np.array([a.position for a in sim.agents()]).reshape(-1, 2)
            counts.append([((xy[:, 0] >= z["x_min"]) & (xy[:, 0] < z["x_max"]) & (xy[:, 1] >= z["y_min"])
                            & (xy[:, 1] < z["y_max"])).sum() for z in zones])
            if int(sim.elapsed_time()) % 60 == 0:
                frames[int(sim.elapsed_time())] = xy
    return np.array(counts), frames


def draw(v, counts, frames, out):
    areas = np.array([z["area_m2"] for z in v["zones"]])
    red = np.array([z["red_persons_m2"] for z in v["zones"]])
    for t, xy in frames.items():
        fig, ax = plt.subplots(figsize=(10, 5))
        dens = counts[min(t, len(counts)) - 1] / areas
        for z, d, r in zip(v["zones"], dens, red):
            ax.add_patch(plt.Rectangle((z["x_min"], z["y_min"]), z["x_max"] - z["x_min"], z["y_max"] - z["y_min"],
                                       fc=plt.cm.YlOrRd(min(d / r, 1.0)), ec="k", lw=0.6))
            ax.text(z["x_min"] + 0.3, z["y_max"] - 0.3, f"{z['id']}\n{d:.1f}", va="top", fontsize=6)
        if len(xy):
            ax.scatter(xy[:, 0], xy[:, 1], s=1.5, c="#2f6fd6")
        for c in v.get("sensor_candidates", []):
            ax.plot(c["x"], c["y"], "s", color="#7b3fe4", ms=4)
        ax.set_aspect("equal")
        ax.autoscale()
        ax.set_title(f"{v['venue_id']}: t = {t} s, {len(xy)} people (zone fill: density / red level)")
        fig.savefig(out / f"t{t:04d}.png", dpi=120, bbox_inches="tight")
        plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("venue")
    ap.add_argument("--people", type=int, default=1000)
    ap.add_argument("--seconds", type=int, default=600)
    a = ap.parse_args()
    v = json.loads(Path(a.venue).read_text())
    problems = check(v)
    for p in problems:
        print("PROBLEM:", p)
    if problems:
        return
    print("venue file OK:", len(v["zones"]), "zones,", len(v["links"]), "links")
    out = OUT / v["venue_id"]
    out.mkdir(parents=True, exist_ok=True)
    counts, frames = simulate(v, a.people, a.seconds)
    draw(v, counts, frames, out)
    peak = (counts / np.array([z["area_m2"] for z in v["zones"]])).max(0)
    lines = ["zone,peak_density,amber,red"] + [f"{z['id']},{p:.2f},{z['amber_persons_m2']},{z['red_persons_m2']}"
                                                 for z, p in zip(v["zones"], peak)]
    (out / "peak_density.csv").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"{len(frames)} pictures and peak_density.csv in {out}")


if __name__ == "__main__":
    main()
