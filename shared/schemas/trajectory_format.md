# Ground-truth trajectory file

One CSV file per run, written by `sim/run_sim.py` (or a converter for Jülich data).
Name: `{run_id}.csv` in `data/trajectories/` (not committed), with `{run_id}.json` holding the run settings.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | integer | Agent ID, unique within the run |
| `frame` | integer | Frame number, starting at 0 |
| `x` | float, metres | venue x |
| `y` | float, metres | venue y |

- Frame rate: **5 frames per second** (JuPedSim step 0.05 s, every 4th step written).
- Coordinates use the venue file's system, so zone membership can be computed directly.
- This is the format PedPy reads (`pedpy.TrajectoryData(data=df, frame_rate=5.0)`).
- An agent's rows stop when it reaches the exit.

`data/truth/{run_id}.csv` holds the per-second true head count per zone, derived from the trajectories.
