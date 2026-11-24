"""Sensor side of live mode: replays the emulated readings of one recorded run over MQTT.

Each sensor is its own MQTT client with a Last Will, like a real device. Every report
(5 s of event time, sped up by --speed) each working sensor publishes one count message;
with --sketches it adds its linear-counting sketch (option B). --fail switches off the
sensors watching the risk zones 90 s before the first red event, as in the failure test,
by dropping their connection so the broker sends their Last Will.

For the dashboard (evaluator view) it also publishes the true zone densities and crowd positions every
second on the restricted sim/{run}/truth topic as the simulator; the broker's ACL keeps the twin from reading it.

  python -m live.publisher --run gradual-s04 --mode tags --placement bottleneck --budget 4 --speed 10
"""
import argparse
import json
import threading
import time

import numpy as np

from evaluation.truth import truth
from experiments.placement import place
from experiments.run_experiments import failure_window
from live.common import broker_args, connect, count_topic, pack_sketch, send, status_topic
from sensors import emulator, sketch
from shared.venue import Venue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--mode", choices=["phones", "tags"], default="tags")
    ap.add_argument("--noise", default="medium")
    ap.add_argument("--placement", default="bottleneck")
    ap.add_argument("--budget", type=int, default=4)
    ap.add_argument("--sketches", action="store_true")
    ap.add_argument("--fail", action="store_true")
    ap.add_argument("--speed", type=float, default=10.0, help="event seconds per wall second")
    ap.add_argument("--seed", type=int, default=None, help="default: the run's own seed, as in the experiments")
    ap.add_argument("--no-wait", action="store_true", help="start without waiting for the twin to be online")
    ap.add_argument("--sim-user", default=None, help="broker user for the truth topic (ACL config: simulator)")
    ap.add_argument("--sim-password", default=None)
    broker_args(ap)
    args = ap.parse_args()
    if args.seed is None:  # same sensor noise and ensemble as the experiment row for this run
        args.seed = int(args.run[-2:])

    venue = Venue()
    sensors = place(args.placement, args.budget, args.mode, args.seed, args.noise)
    ids = [emulator.CAND_IDS[c] for c in sensors]
    fail = failure_window(args.run, sensors) if args.fail else ()
    obs = emulator.observe(args.run, args.mode, args.noise)
    rd = emulator.readings(obs, sensors, seed=args.seed, failures=fail)  # same draws as the offline run
    mode = "personal_device" if args.mode == "phones" else "ble_tag"
    zone = {c: emulator.coverage_zone(c, venue) for c in sensors}
    print("sensors:", ",".join(ids), flush=True)

    if not args.no_wait:  # the event starts once the twin is listening
        ready = threading.Event()
        w = connect(args, "sensor-wait")
        w.on_message = lambda c, u, m: ready.set() if json.loads(m.payload)["status"] == "online" else None
        w.subscribe(f"twin/{venue.id}/status", qos=1)
        print("waiting for the twin...", flush=True)
        # (a retained "online" left by a twin that is still running counts as ready)
        ready.wait()
        w.disconnect()
        w.loop_stop()

    # one client per sensor, retained online status, Last Will offline
    clients = [connect(args, f"sensor-{s}", (status_topic(venue.id, s), {"sensor_id": s, "status": "offline"}))
               for s in ids]
    for c, s in zip(clients, ids):
        send(c, status_topic(venue.id, s), {"sensor_id": s, "status": "online", "ts": 0.0}, retain=True, qos=1)
    dead = [False] * len(ids)

    ender = connect(args, "event-schedule")
    # ground truth for the dashboard only: zone densities and positions (person id, decimetres) every second;
    # the sensors still report every 5 s, so the twin sees exactly what it saw before
    occ, _ = truth(args.run)
    secs = range(0, int(rd["t"][-1]) + 1)
    traj = emulator.load_seconds(args.run)
    at = {int(t): g[:, [0, 2, 3]] for t, g in ((t, traj[traj[:, 1] == t]) for t in secs)}  # id, x, y
    report_at = {int(t): i for i, t in enumerate(rd["t"])}
    sim = connect(args, "simulator", user=args.sim_user, password=args.sim_password)
    epoch, pos = emulator.MODES[args.mode]["epoch"], None
    start = time.time()
    for sec in secs:
        time.sleep(max(0.0, start + sec / args.speed - time.time()))  # keep event time
        ti = min(sec, len(occ) - 1)
        send(sim, f"sim/{args.run}/truth", {"ts": float(sec), "venue_id": venue.id, "failure_test": bool(fail),
                                             "zones": {z: round(float(occ[ti, j] / venue.area[j]), 3)
                                                       for j, z in enumerate(venue.zone_ids)},
                                             "id": at.get(sec, np.zeros((0, 3)))[:, 0].astype(int).tolist(),
                                             "xy": np.round(at.get(sec, np.zeros((0, 3)))[:, 1:] * 10).astype(int).tolist()})
        if sec not in report_at:
            continue
        i = report_at[sec]
        t = rd["t"][i]
        if args.sketches and (pos is None or int(t // epoch) != pos[0]):
            pos = (int(t // epoch), sketch.hash_positions(obs["pids"], salt=f"epoch{int(t // epoch)}"))
        for k, (c, s) in enumerate(zip(clients, ids)):
            if dead[k]:
                continue
            if any(k == j and a <= t for j, a, _ in fail):  # device dies: connection drops, broker sends the Will
                c.loop_stop()
                c.socket().close()
                dead[k] = True
                print(f"t={t:.0f}s {s} went offline", flush=True)
                continue
            if rd["lost"][i, k]:  # message lost on the way
                continue
            msg = {"ts": float(t), "sent_at": time.time(), "run_id": args.run, "venue_id": venue.id,
                   "sensor_id": s, "zone_id": zone[sensors[k]], "count": int(rd["counts"][i, k]),
                   "mode": mode, "seq": i}
            if args.sketches:
                msg["sketch"] = pack_sketch(sketch.build(pos[1], obs["seen"][i, sensors[k]]))
            send(c, count_topic(venue.id, s), msg)
    # the event is over (in a venue this comes from the event schedule), sent straight after the
    # last report so the twin doesn't step on past the end and take the silence for dead sensors
    send(ender, f"venue/{venue.id}/event", {"status": "ended", "ts": float(rd["t"][-1])}, qos=1).wait_for_publish()
    ender.disconnect()
    sim.disconnect()
    sim.loop_stop()
    ender.loop_stop()
    time.sleep(0.5)
    for k, (c, s) in enumerate(zip(clients, ids)):
        if not dead[k]:  # orderly shutdown: say so ourselves (the Will is only for crashes)
            send(c, status_topic(venue.id, s), {"sensor_id": s, "status": "offline", "ts": float(rd["t"][-1])},
                 retain=True, qos=1).wait_for_publish()
            c.disconnect()
            c.loop_stop()
    print(f"done: {len(rd['t'])} reports in {time.time() - start:.1f} s", flush=True)


if __name__ == "__main__":
    main()
