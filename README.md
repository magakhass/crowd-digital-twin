# Privacy-Preserving Crowd Digital Twin

CSIT305 Emerging Technology Research and Innovation Project (UOWD).

A digital twin of a venue that estimates and forecasts crowd density from sparse,
count-only IoT sensors, and warns operators before a zone becomes dangerously crowded.
The venue and crowd are simulated in Unity; the sensors, twin and evaluation are in Python.

## Repository layout

| Folder | Contents |
| --- | --- |
| `shared/` | Message formats and MQTT topics shared by all components. Change only through a reviewed PR. |
| `ConcertVenue/` | Unity venue and three crowd scenarios with a zone density display |
| `sensors/` | Virtual sensor emulator, fault injector, trajectory replayer |
| `twin/` | Digital twin: ingestion, venue graph, estimator, forecasters, alerts, publisher |
| `experiments/` | Offline experiment runner, run configs, placement search |
| `evaluation/` | Metrics, PedPy validation checks, plots |
| `broker/` | Mosquitto configuration and topic access rules |
| `tests/` | Unit, integration and failure tests |
| `data/` | Downloaded and generated data (not committed; see `data/README.md`) |
| `docs/` | Architecture diagrams, development records, decisions, paper |

## Requirements

- Python 3.11+ (`pip install -r requirements.txt`)
- Eclipse Mosquitto (MQTT broker)

## Running

- **Live mode:** TODO
- **Offline mode:** TODO

## Unity venue

Setup, layout and integration notes: [docs/venue/README.md](docs/venue/README.md).
The shared venue JSON is the single source for zone geometry and alert thresholds.
Run `python3 evaluation/verify_layout.py` from the repository root to check the scene snapshot.
