# Live messages match the schemas, and sketches survive the trip.
import json
from pathlib import Path

import jsonschema
import numpy as np

from live.common import pack_sketch, unpack_sketch
from sensors import sketch

SCHEMAS = Path(__file__).resolve().parents[2] / "shared" / "schemas"


def schema(name):
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text())


def test_sketch_roundtrip():
    pos = sketch.hash_positions(np.arange(300), salt="t")
    sk = sketch.build(pos, np.random.default_rng(0).random(300) < 0.4)
    assert (unpack_sketch(pack_sketch(sk)) == sk).all()


def test_messages_match_schemas():
    sk = pack_sketch(np.zeros((sketch.R, sketch.M), bool))
    count = {"ts": 5.0, "sent_at": 1.7e9, "run_id": "gradual-s04", "venue_id": "concert_venue", "sensor_id": "C08",
             "zone_id": "Z05", "count": 12, "mode": "ble_tag", "seq": 0, "sketch": sk}
    jsonschema.validate(count, schema("sensor_count"))
    jsonschema.validate({"sensor_id": "C08", "status": "offline"}, schema("sensor_status"))
    state = {"ts": 5.0, "seq": 0, "sensors_in": ["C08"], "last_sent_at": None, "blind": ["Z05"], "compute_ms": 25.0, "published_at": 1.7e9,
             "zones": {"Z05": {"density": 1.2, "p_red": 0.1, "p_amber": 0.4}}}
    jsonschema.validate(state, schema("twin_state"))
    jsonschema.validate({"ts": 5.0, "zone_id": "Z05", "level": "blind", "p": None, "last_sent_at": None,
                         "published_at": 1.7e9}, schema("twin_alert"))
