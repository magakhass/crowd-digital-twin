# Privacy-Preserving Crowd Digital Twin

CSIT305 Emerging Technology Research and Innovation Project (UOWD).

A digital twin of a venue that estimates and forecasts crowd density from sparse,
count-only IoT sensors, and warns operators before a zone becomes dangerously crowded.
The crowd is simulated in JuPedSim; the sensors, twin and evaluation are in Python.

## How it fits together

1. **Simulator** (`sim/`): JuPedSim runs end-of-show egress scenarios on the venue and writes ground truth.
2. **Sensors** (`sensors/`): count-only Wi-Fi (phones) or BLE-tag sensors with a position and a 10 m range.
   Option A sends a count; option B also sends privacy-preserving sketches (Kamp et al., 2013).
3. **Twin** (`twin/`): zone flow model + ensemble Kalman filter, 2-minute forecast, amber/red alerts.
   It sees only sensor messages and the venue file, never the ground truth.
4. **Experiments** (`experiments/`): calibration on seeds 1–2, then a sweep over sensing mode,
   option A/B, placement strategy and sensor budget on seeds 3–8.
5. **Evaluation** (`evaluation/`): detection rate, false alarms per hour, lead time, density RMSE, realism checks.

## Repository layout

| Folder | Contents |
| --- | --- |
| `shared/` | Venue file, loader, message formats and MQTT topics. Change only through a reviewed PR. |
| `sim/` | `scenarios.py` (scenario definitions), `run_sim.py` (one run), `run_all.py` (batch) |
| `sensors/` | `emulator.py` (detections, readings, messages), `sketch.py` (linear-counting sketches) |
| `twin/` | `model.py` (flow model, EnKF, forecast), `observation.py` (learned observation model), `run_twin.py` (twin and baselines), `params.py` (frozen settings) |
| `experiments/` | `calibrate.py`, `placement.py` (incl. greedy mutual information, Liebig et al., 2013), `run_experiments.py` |
| `evaluation/` | `truth.py`, `metrics.py`, `realism.py` (PedPy), `report.py` (tables, figures), `fig_venue.py`, `verify_layout.py` |
| `broker/` | Mosquitto configuration and topic access rules (live mode) |
| `tests/` | Tests |
| `data/` | Generated data (not committed) and paper results (committed); see `data/README.md` |
| `docs/` | Architecture, decisions, evidence log, archived Unity prototype |

## Setup

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

## Reproduce the results

Run from the repository root (each step reuses the previous step's files):

    python -m sim.run_all                        # 36 JuPedSim runs, ~1 h on 2 cores
    python -m experiments.calibrate              # freezes data/results/params.json
    python -m experiments.run_experiments core   # normal, gradual, surge
    python -m experiments.run_experiments heldout  # counterflow, blockage
    python -m evaluation.realism                 # PedPy flow and speed-density checks
    python -m evaluation.report                  # tables and figures in data/results/

One run on its own: `python -m sim.run_sim surge 3`.

## Live mode

Not part of the paper results. The sensor emulator can write schema-conformant messages
(`sensors.emulator.to_messages`) for replay through the broker; see `broker/README.md`.

## Checks

    python evaluation/verify_layout.py
    python -m pytest -q tests
