# MQTT topics

| Topic | Publisher | Readers | Content |
| --- | --- | --- | --- |
| `sim/{run}/truth` | simulator (the live publisher, as the `simulator` user) | evaluator / dashboard only | True zone densities and crowd positions (person id, decimetres) every second; restricted: the twin can't read it |
| `venue/{venue}/sensor/{sensor}/count` | each sensor | twin | Count message, every 5 s (`schemas/sensor_count.schema.json`); option B adds `sketch` |
| `venue/{venue}/sensor/{sensor}/status` | each sensor (retained; `offline` is its Last Will) | twin | online / offline (`schemas/sensor_status.schema.json`) |
| `venue/{venue}/event` | event schedule | twin | `{"status": "ended", "ts": ...}` when the event is over |
| `twin/{venue}/status` | twin (retained; Last Will offline) | sensors, dashboard, logger | online / offline, with the installed sensors, tau, phase and horizon; the sensors start once it is online |
| `twin/{venue}/state` | twin | dashboard, logger | Zone density estimates and forecasts per report, and the risk zones that are blind right now (`schemas/twin_state.schema.json`) |
| `twin/{venue}/alerts` | twin (QoS 1) | dashboard, logger | Amber / red / blind alerts (`schemas/twin_alert.schema.json`) |

The twin must never be able to read `sim/#`. This is enforced in `broker/acl`.
The experiments run offline with the same twin code (`twin.run_twin.Twin`); the broker is only needed for live mode (`live/`).
