# Ground-truth trajectory file

One CSV file per run, written by the Unity logger (or the replayer for Jülich data).
Name: `{run_id}.csv`. Stored in `data/trajectories/` (not committed).

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | integer | Agent ID, unique within the run |
| `frame` | integer | Frame number, starting at 0 |
| `x` | float, metres | Unity X |
| `y` | float, metres | Unity **Z** (not Unity Y, which is elevation) |

- Frame rate: **TODO agree (proposal: 10 frames per second)**, written in the run's config file.
- Coordinates use the venue file's system (`shared/venues/`), so zone membership can be computed directly.
- This is the format PedPy reads, so the same file feeds validation and evaluation.
- Only agents inside the venue are logged; an agent's rows stop when it reaches the exit.
