"""Shared bits for live mode: broker connection, sketch encoding, topics."""
import argparse
import base64
import json

import numpy as np
import paho.mqtt.client as mqtt

from sensors.sketch import M, R


def broker_args(ap: argparse.ArgumentParser):
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--user", default=None, help="broker user (only with the ACL config)")
    ap.add_argument("--password", default=None)


def connect(args, client_id, will=None, user=None, password=None):
    # will: (topic, payload dict) published by the broker if this client drops without saying goodbye
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if user or args.user:
        c.username_pw_set(user or args.user, password if user else args.password)
    if will:
        c.will_set(will[0], json.dumps(will[1]), qos=1, retain=True)
    c.connect(args.host, args.port, keepalive=10)
    c.loop_start()
    return c


def send(c, topic, payload, retain=False, qos=0):
    return c.publish(topic, json.dumps(payload), qos=qos, retain=retain)


def pack_sketch(sk):
    return base64.b64encode(np.packbits(sk).tobytes()).decode()


def unpack_sketch(s):
    return np.unpackbits(np.frombuffer(base64.b64decode(s), np.uint8))[:R * M].reshape(R, M).astype(bool)


def count_topic(venue, sensor="+"):
    return f"venue/{venue}/sensor/{sensor}/count"


def status_topic(venue, sensor="+"):
    return f"venue/{venue}/sensor/{sensor}/status"
