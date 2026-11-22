"""Realism checks on the simulated crowd with PedPy.

1. Specific flow through the bottleneck vs the 82 persons/m/min guidance value (Still).
2. Median speed by density in the approach zone (a queue, so speeds are set by the
   bottleneck, not by free walking; a full fundamental-diagram check needs the Jülich data).
Writes data/results/realism.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pedpy


DATA = Path(__file__).resolve().parents[1] / "data"
RUNS = [f"{s}-s{k:02d}" for s in ("gradual", "surge") for k in range(3, 9)]


def check(run_id):
    df = pd.read_csv(DATA / "trajectories" / f"{run_id}.csv")
    traj = pedpy.TrajectoryData(data=df, frame_rate=5.0)
    line = pedpy.MeasurementLine([(29.0, -1.5), (29.0, 1.5)])
    nt, _ = pedpy.compute_n_t(traj_data=traj, measurement_line=line)
    t = nt["time"].to_numpy()
    n = nt["cumulative_pedestrians"].to_numpy()
    # peak 30 s specific flow, persons per metre per minute
    k = np.searchsorted(t, t + 30)
    ok = k < len(t)
    peak = float(((n[k[ok]] - n[ok]) / 30).max() / 3.0 * 60)
    # density and speed in the approach zone (Z05)
    area = pedpy.MeasurementArea([(18, -6), (24, -6), (24, 6), (18, 6)])
    dens = pedpy.compute_classic_density(traj_data=traj, measurement_area=area)
    speed = pedpy.compute_individual_speed(traj_data=traj, frame_step=5,
                                           speed_calculation=pedpy.SpeedCalculation.BORDER_SINGLE_SIDED)
    mean_v = pedpy.compute_mean_speed_per_frame(traj_data=traj, measurement_area=area, individual_speed=speed)
    fd = dens.merge(mean_v, on="frame").dropna()
    return peak, fd


if __name__ == "__main__":
    rows, fds = [], []
    for r in RUNS:
        peak, fd = check(r)
        rows.append({"run": r, "peak_specific_flow_p_m_min": round(peak, 1)})
        fds.append(fd)
    out = pd.DataFrame(rows)
    out.to_csv(DATA / "results" / "realism.csv", index=False)
    print(out.describe())
    fd = pd.concat(fds)
    fd = fd[fd["density"] > 0.2]
    bins = np.arange(0, 6, 0.5)
    g = fd.groupby(pd.cut(fd["density"], bins), observed=True)["speed"].median()
    print(g)
