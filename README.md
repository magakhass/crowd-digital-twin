# Privacy-Preserving Crowd Digital Twin

CSIT305 Emerging Technology Research and Innovation Project (UOWD).

A digital twin of a venue that estimates and forecasts crowd density from sparse,
count-only IoT sensors, and warns operators before a zone becomes dangerously crowded.
The crowd is simulated in JuPedSim; the sensors, twin and evaluation are in Python.

## How it fits together

1. **Simulator** (`sim/`): JuPedSim runs end-of-show egress scenarios on the venue and writes ground truth.
2. **Sensors** (`sensors/`): count-only Wi-Fi (phones) or BLE-tag sensors with a position and a 10 m range,
   at three noise levels (low/medium/high: packet reception, range wobble, lost messages).
   Option A sends a count; option B also sends privacy-preserving sketches (Kamp et al., 2013).
3. **Twin** (`twin/`): zone flow model + ensemble Kalman filter, 2-minute forecast, amber/red alerts.
   It sees only sensor messages and the venue file, never the ground truth.
4. **Experiments** (`experiments/`): calibration on seeds 1–2, then a sweep over sensing mode,
   noise level, option A/B, placement strategy and sensor budget on seeds 3–8.
5. **Evaluation** (`evaluation/`): detection rate, false alarms per hour, lead time, density RMSE, realism checks.

## Repository layout

| Folder | Contents |
| --- | --- |
| `shared/` | Venue file, loader, message formats and MQTT topics. Change only through a reviewed PR. |
| `sim/` | `scenarios.py` (scenario definitions), `behaviour.py` (walking settings, gate routing, gridlock breaker), `run_sim.py` (one run), `run_all.py` (batch), `validate_julich.py` (test against Jülich experiments) |
| `sensors/` | `emulator.py` (detections, readings, messages), `sketch.py` (linear-counting sketches) |
| `twin/` | `model.py` (flow model, EnKF, forecast), `observation.py` (learned observation model), `run_twin.py` (twin and baselines), `params.py` (frozen settings) |
| `experiments/` | `calibrate.py`, `placement.py` (incl. greedy mutual information, Liebig et al., 2013), `run_experiments.py` |
| `evaluation/` | `truth.py`, `metrics.py`, `realism.py` (PedPy), `report.py` (tables, figures), `fig_venue.py`, `verify_layout.py` |
| `live/` | Live mode over MQTT: `publisher.py` (sensors), `twin_service.py`, `logger.py` (latency), `demo.py` (all three) |
| `broker/` | Mosquitto configuration and topic access rules (live mode) |
| `tests/` | Tests |
| `data/` | Generated data (not committed) and paper results (committed); see `data/README.md` |
| `docs/` | Architecture, decisions, evidence log, archived Unity prototype |

## Setup

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

## Reproduce the results

Run from the repository root (each step reuses the previous step's files):

    python -m sim.run_all                        # 68 JuPedSim runs (seeds 1-2 calibration, 3-12 test)
    python -m experiments.calibrate              # freezes data/results/params.json
    python -m experiments.run_experiments core   # normal, gradual, surge; 3 noise levels, 2-8 sensors (7,270 jobs)
    python -m experiments.run_experiments heldout  # counterflow, blockage; medium noise
    python -m experiments.run_experiments movements  # ingress; medium noise
    python -m evaluation.realism                 # PedPy flow and speed-density checks
    python -m evaluation.report                  # tables and figures in data/results/

The batch scripts (simulations, calibration, experiments) use all cores but one; set `--workers N` to change that.

Watch a run in the browser (people, sensors, twin estimate and alerts):

    python -m evaluation.replay surge-s05 --mode tags --noise high --strategy bottleneck --budget 4

This writes `data/replays/<run>_<setup>.html` (about 10 MB, ignored by git).
One run on its own: `python -m sim.run_sim surge 3`.
Scenarios: five egress scenarios (normal, gradual, surge; held out: counterflow, blockage) and
ingress (people arriving through Z01). The twin takes the event phase (egress or ingress) from
the event schedule and uses the flow settings it learned for that phase.
`sim.run_all` only runs what is missing in `data/truth/`; to simulate everything again, empty
`data/trajectories/`, `data/truth/` and `data/sensors/` first.

## Venue 2 (festival hall)

Everything above runs on the concert venue by default. For the festival hall (two exits, an
entry checkpoint) set the venue first; its data goes to `data/venues/festival_hall_v2/`:

    $env:CROWDTWIN_VENUE="festival_hall_v2"     # PowerShell (bash: export CROWDTWIN_VENUE=festival_hall_v2)
    python -m sim.run_all --workers 15
    python -m experiments.calibrate --workers 15          # after the concert venue's: venue 2 keeps its tau
    python -m experiments.run_experiments small --workers 15  # every scenario, medium noise, 4 sensors
    python -m evaluation.report                           # summary_small_*.csv, fig_timeseries.png
    Remove-Item Env:CROWDTWIN_VENUE             # back to the concert venue

No zone in venue 2 reaches red, so it is scored on amber warnings (detection, lead time, false
alarms), red false alarms and density error (evidence log D23, D24).

Layout: `docs/festival_hall_v2_layout.png`. Runs where under 95 % of the crowd got out are replaced
by the next seed (evidence log D22).

## Simulator check against Jülich experiments

Download the HERMES 2009 bottleneck runs (doi 10.34735/ped.2009.6) into `data/julich/hermes/` and the
crowdqueue 2018 runs (doi 10.34735/ped.2018.1) into `data/julich/crowdqueue/`, each with its
`metadata.json` from the archive (the folder is ignored by git). Then:

    python -m sim.validate_julich check     # writes data/results/avm_check_summary.csv

## Live mode (MQTT)

The same twin (`twin.run_twin.Twin`) running on messages over a Mosquitto broker. Each sensor is
its own MQTT client (retained status, Last Will); the twin service subscribes to the sensor
topics, runs one report at a time on the event clock and publishes state and alerts; a logger
records the end-to-end latency. Topics and message formats: `shared/mqtt_topics.md`.

Start a broker first (`broker/README.md`; if Windows blocks Mosquitto, `python -m live.broker`), then in a second terminal:

    python -m live.demo --run gradual-s04 --mode tags --placement bottleneck --budget 4 --speed 10
    python -m live.demo --run surge-s05 --mode phones --sketches --fail --speed 10   # option B + failure test

Add `--dashboard` to open the operator dashboard in the browser (http://localhost:8050): venue map
coloured by the twin's estimate or the true density, the simulated crowd, sensors and their status,
the 2-minute risk per zone, alerts, a timeline of the selected zone, and latency. The true density
comes from the restricted `sim/` topic (the dashboard listens as the evaluator; the twin never sees
it). When the run ends the session is saved as `data/results/dashboard_{run}.html`, which replays
in any browser with no Python or broker, as a backup for the symposium.

To make recordings of several runs in one go (it starts the broker and the dashboard itself):

    python -m live.record gradual-s04 counterflow-s06 ingress-s03 surge-s05:fail

`:fail` adds the sensor-failure test to that run. `--speed 1` is real time (about 10 minutes per run). Output: `data/results/live_latency.csv`
(per report: sensors in, twin compute time, end-to-end latency) and `live_latency_alerts.csv`.
With the same seed the live alerts are identical to the offline run's. The three parts can also
be started on their own (`live.twin_service`, `live.publisher`, `live.logger`, each with `--help`).

## Checks

    python evaluation/verify_layout.py
    python -m pytest -q tests
