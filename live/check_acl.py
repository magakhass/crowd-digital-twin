"""Checks the information firewall on a broker running broker/acl (Mosquitto, e.g. the Docker one).

Publishes a test truth message as the simulator and a test count as a sensor, then checks who receives what:
the twin must get the count but never the truth, the evaluator gets both, and clients without a login are refused.

  python -m live.check_acl --host localhost --password <password>
"""
import argparse
import json
import sys
import time

import paho.mqtt.client as mqtt

VENUE = "acl_check"


def client(args, user, password, inbox=None, topics=()):
    result = {}
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"acl-check-{user or 'anonymous'}")
    if user:
        c.username_pw_set(user, password)

    def on_connect(c, u, flags, rc, props):
        result["rc"] = rc
        if not rc.is_failure:
            for t in topics:
                c.subscribe(t, qos=1)

    def on_message(c, u, m):
        if inbox is not None:
            inbox.append(m.topic)

    c.on_connect, c.on_message = on_connect, on_message
    c.connect(args.host, args.port, keepalive=10)
    c.loop_start()
    for _ in range(50):  # wait for CONNACK
        if "rc" in result:
            break
        time.sleep(0.1)
    return c, result.get("rc")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--password", required=True)
    args = ap.parse_args()
    pw = args.password
    truth, count = f"sim/{VENUE}-s01/truth", f"venue/{VENUE}/sensor/S01/count"

    twin_in, eval_in = [], []
    twin, rc1 = client(args, "twin", pw, twin_in, ["sim/#", "venue/#"])
    ev, rc2 = client(args, "evaluator", pw, eval_in, ["sim/#", "venue/#"])
    sim, rc3 = client(args, "simulator", pw)
    sensor, rc4 = client(args, "sensor_emulator", pw)
    if any(rc is None or rc.is_failure for rc in (rc1, rc2, rc3, rc4)):
        print("FAIL  login refused for a component user: check the password (MQTT_PASSWORD)")
        return 1
    time.sleep(1)  # subscriptions in place
    sim.publish(truth, json.dumps({"venue_id": VENUE, "check": True}), qos=1).wait_for_publish(5)
    sensor.publish(count, json.dumps({"sensor_id": "S01", "count": 1}), qos=1).wait_for_publish(5)
    sensor.publish("sim/forged/truth", json.dumps({"forged": True}), qos=1).wait_for_publish(5)  # not allowed to write sim/
    time.sleep(1.5)
    anon, anon_rc = client(args, None, None)

    checks = [
        ("twin receives sensor counts", count in twin_in),
        ("twin never receives ground truth (sim/#)", not any(t.startswith("sim/") for t in twin_in)),
        ("evaluator receives ground truth", truth in eval_in),
        ("sensor cannot publish fake ground truth", "sim/forged/truth" not in eval_in),
        ("client without a login is refused", anon_rc is not None and anon_rc.is_failure),
    ]
    for c in (twin, ev, sim, sensor, anon):
        c.loop_stop()
        c.disconnect()
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
