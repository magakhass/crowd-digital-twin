# Privacy-Preserving Crowd Digital Twin

CSIT305 Emerging Technology Research and Innovation Project (UOWD).

A digital twin of a venue that estimates and forecasts crowd density from sparse,
count-only IoT sensors, and warns operators before a zone becomes dangerously crowded.
The venue and crowd are simulated in Unity; the sensors, twin and evaluation are in Python.

## Repository layout

| Folder | Contents |
| --- | --- |
| `shared/` | Message formats and MQTT topics shared by all components. Change only through a reviewed PR. |
| `unity/` | Unity project: venue, crowd, ground-truth logger, dashboard |
| `sensors/` | Virtual sensor emulator, fault injector, trajectory replayer |
| `twin/` | Digital twin: ingestion, venue graph, estimator, forecasters, alerts, publisher |
| `experiments/` | Offline experiment runner, run configs, placement search |
| `evaluation/` | Metrics, PedPy validation checks, plots |
| `broker/` | Mosquitto configuration and topic access rules |
| `tests/` | Unit, integration and failure tests |
| `data/` | Downloaded and generated data (not committed; see `data/README.md`) |
| `docs/` | Architecture diagrams, evidence log, AI-use log, decisions, paper |

## Requirements

- Python 3.11+ (`pip install -r requirements.txt`)
- Eclipse Mosquitto (MQTT broker)

## Running

- **Live mode:** TODO
- **Offline mode:** TODO
