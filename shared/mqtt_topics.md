# MQTT topics

| Topic | Publisher | Readers | Content |
| --- | --- | --- | --- |
| `sim/{run}/truth` | Unity / replayer | sensor emulator, evaluator only | Ground-truth agent positions (restricted) |
| `venue/{venue}/sensor/{sensor}/count` | sensor emulator | twin | Count message (see `schemas/sensor_count.schema.json`) |
| `venue/{venue}/sensor/{sensor}/status` | sensor emulator (Last Will) | twin | online / offline |
| `twin/{venue}/state` | twin | dashboard, logger | Zone estimates and forecasts |
| `twin/{venue}/alerts` | twin | dashboard, logger | Amber / red alerts |

The twin must never be able to read `sim/#`. This is enforced in `broker/acl`.
