"""Latency figure for live mode: share of reports handled within x ms, split into reports
where every sensor came in and reports that had to wait for a lost message.

  python -m evaluation.fig_latency [data/results/live_latency.csv]
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shared.venue import data_dir

OUT = data_dir() / "results"


def main(path):
    d = pd.read_csv(path)
    full = d["sensors_in"] == d["sensors_in"].max()
    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    for mask, label, colour in [(full, "all sensors in", "#2a6fb0"), (~full, "a message lost", "#c0504d")]:
        x = np.sort(d.loc[mask, "e2e_ms"].to_numpy())
        if len(x):
            ax.step(x, np.arange(1, len(x) + 1) / len(x), where="post", color=colour, label=f"{label} (n={len(x)})")
    ax.axvline(d["compute_ms"].median(), color="grey", ls=":", lw=1, label="twin compute (median)")
    ax.set_xscale("log")
    ax.set_xlabel("sensor message to twin state (ms)")
    ax.set_ylabel("share of reports")
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "fig_latency.png", dpi=200)
    print(d.groupby(full.map({True: "all in", False: "lost msg"}))[["e2e_ms", "compute_ms"]]
          .describe(percentiles=[0.5, 0.95]).round(1).T)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else OUT / "live_latency.csv")
