"""Twin side of live mode: subscribes to the sensor topics, runs the twin per report and
publishes the zone state and alerts. It never sees the simulation (the broker ACL keeps
sim/# from it); it only knows the venue, the installed sensors and the event phase.

Reports are processed in order on the event clock (started by the first message, running at
--speed): a report goes in once every online sensor has sent it, once a later one arrives, or
--deadline wall seconds after it was due, whichever comes first. A missing sensor is NaN, so
the twin keeps stepping (and raises blind alerts) even when every sensor has gone quiet.

  python -m live.twin_service --sensors C06,C07,C08,C09 --mode tags --phase egress
"""
import argparse
import json
import queue
import threading
import time

import numpy as np

from live.common import broker_args, connect, count_topic, send, status_topic, unpack_sketch
from sensors import emulator, sketch
from shared.venue import Venue
from twin.observation import ObservationModel
from twin.params import params
from twin.run_twin import HORIZON, Onsets, Twin

REPORT_EVERY = emulator.REPORT_EVERY


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sensors", required=True, help="installed sensor ids, e.g. C06,C07,C08,C09")
    ap.add_argument("--mode", choices=["phones", "tags"], default="tags")
    ap.add_argument("--noise", default="medium", help="noise level the observation model was fitted for")
    ap.add_argument("--phase", choices=["egress", "ingress"], default="egress")
    ap.add_argument("--sketches", action="store_true")
    ap.add_argument("--tau", type=float, default=None)
    ap.add_argument("--speed", type=float, default=1.0, help="event seconds per wall second (1 = real time)")
    ap.add_argument("--deadline", type=float, default=None, help="wall seconds to wait for late sensors "
                    "(default 80 %% of a report interval, at most 2 s)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quiet-after", type=float, default=600.0, help="give up after this many idle wall seconds")
    broker_args(ap)
    args = ap.parse_args()

    venue, p = Venue(), params()
    tau = p["tau"] if args.tau is None else args.tau
    ids = args.sensors.split(",")
    sensors = [emulator.CAND_IDS.index(s) for s in ids]  # order as installed (the publisher prints it)
    obs_op = ObservationModel(args.mode, sensors, args.sketches, args.noise)
    tw = Twin(args.phase, sensors, obs_op, seed=args.seed, p=p)
    red_on, amb_on = Onsets(len(venue.zone_ids)), Onsets(len(venue.zone_ids))
    print(f"twin ready: {','.join(ids)} {args.mode} {args.phase} tau={tau}", flush=True)

    deadline = args.deadline if args.deadline is not None else min(2.0, 0.8 * REPORT_EVERY / args.speed)
    inbox = queue.Queue()

    ours = f"venue/{venue.id}/"

    def on_message(c, u, m):
        if m.topic.startswith(ours):  # some brokers (amqtt) redeliver a client's own last message on reconnect
            inbox.put((time.time(), m.topic, json.loads(m.payload)))

    c = connect(args, "twin", (f"twin/{venue.id}/status", {"status": "offline"}))
    c.on_message = on_message
    c.subscribe([(count_topic(venue.id), 0), (status_topic(venue.id), 1), (f"venue/{venue.id}/event", 1)])
    time.sleep(0.5)
    send(c, f"twin/{venue.id}/status", {"status": "online", "sensors": ids, "tau": tau, "phase": args.phase,
                                        "mode": args.mode, "horizon_s": HORIZON}, retain=True, qos=1)  # sensors may start

    online = {s: True for s in ids}
    pending = {}   # seq -> {sensor: payload}
    done = -1      # last processed seq; report seq is at event time (seq + 1) * REPORT_EVERY
    clock = None   # (wall time, event time) of the first message
    end = None     # last report of the event, once the venue announces the end
    last_msg = time.time()

    def due(seq):  # wall time by which report seq should be in
        return clock[0] + ((seq + 1) * REPORT_EVERY - clock[1]) / args.speed + deadline

    def process(seq):
        nonlocal done
        got = pending.pop(seq, {})
        t = float((seq + 1) * REPORT_EVERY)
        t0 = time.time()
        y = np.full(len(ids), np.nan)
        for k, s in enumerate(ids):
            if s in got:
                y[k] = got[s]["count"]
        if args.sketches:
            sks = {s: unpack_sketch(m["sketch"]) for s, m in got.items() if "sketch" in m}
            ov = [sketch.overlap(sks[ids[i]], sks[ids[j]]) if ids[i] in sks and ids[j] in sks else np.nan
                  for i, j in obs_op.pairs]
            y = np.concatenate([y, ov])
        est, p_red, p_amb, lost = tw.report(t, y)
        compute = time.time() - t0
        alerts = [("blind", z) for z in lost]
        alerts += [("red", z) for z in red_on.step(p_red >= tau)] + [("amber", z) for z in amb_on.step(p_amb >= tau)]
        sent = max((m["sent_at"] for m in got.values()), default=None)  # None: nothing came in
        unwatched = [venue.zone_ids[tw.risk[k]] for k in np.nonzero(tw.watch.any(0) & ~tw.was_watched)[0]] if tw.health else []
        state = {"ts": t, "seq": seq, "sensors_in": sorted(got), "last_sent_at": sent, "blind": unwatched,
                 "compute_ms": round(1000 * compute, 2), "published_at": time.time(),
                 "zones": {z: {"density": round(float(est[i]), 3), "p_red": round(float(p_red[i]), 3),
                               "p_amber": round(float(p_amb[i]), 3)} for i, z in enumerate(venue.zone_ids)}}
        send(c, f"twin/{venue.id}/state", state)
        for level, z in alerts:
            a = {"ts": t, "zone_id": venue.zone_ids[z], "level": level, "last_sent_at": sent,
                 "p": None if level == "blind" else round(float((p_red if level == "red" else p_amb)[z]), 3),
                 "published_at": time.time()}
            send(c, f"twin/{venue.id}/alerts", a, qos=1)
            print(f"t={t:.0f}s {level.upper()} {venue.zone_ids[z]}", flush=True)
        done = seq

    while (end is None or done < end) and time.time() - last_msg < args.quiet_after:
        try:
            now, topic, msg = inbox.get(timeout=0.02)
            last_msg = now
            if topic.endswith("/event"):
                if msg["status"] == "ended":
                    end = int(round(msg["ts"] / REPORT_EVERY)) - 1
            elif topic.endswith("/status"):
                if msg["sensor_id"] in online:
                    online[msg["sensor_id"]] = msg["status"] == "online"
            elif msg["sensor_id"] in online and msg["seq"] > done:
                online[msg["sensor_id"]] = True
                clock = clock or (now, msg["ts"])
                pending.setdefault(msg["seq"], {})[msg["sensor_id"]] = msg
        except queue.Empty:
            pass
        # next report in order: complete, overtaken by a later one, or past its deadline
        while clock and (end is None or done < end):
            seq = done + 1
            got = pending.get(seq, {})
            complete = got and all(s in got for s in ids if online[s])
            if complete or any(k > seq for k in pending) or time.time() > due(seq):
                process(seq)
            else:
                break
    send(c, f"twin/{venue.id}/status", {"status": "offline"}, retain=True, qos=1).wait_for_publish()
    c.disconnect()
    c.loop_stop()
    print(f"twin stopped after {done + 1} reports", flush=True)


if __name__ == "__main__":
    main()
