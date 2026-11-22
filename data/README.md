# Data

Generated data is not committed; it is reproducible from the seeds.

- `trajectories/`: JuPedSim ground truth, `{run}.csv` (id, frame, x, y at 5 fps) and `{run}.json` (settings, peaks)
- `truth/`: per-second zone head counts and inflows derived from the trajectories
- `sensors/`: cached detections for every candidate sensor spot (`{run}_{phones|tags}.npz`)
- `results/`: calibrated settings (`params.json`), experiment rows (`runs_*.csv`), summaries and figures (committed)

Regenerate everything with the commands in the top-level README.

## Jülich pedestrian data archive

Real trajectories and DXF geometry: http://ped.fz-juelich.de/da
Download into `data/julich/` (ignored by git). Check each dataset's licence and terms of use,
and cite Boltes et al. (2018).
