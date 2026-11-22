"""Tables and figures for the paper from data/results/runs_*.csv.

Writes to data/results/: summary_main.csv, summary_baselines.csv, summary_heldout.csv,
summary_failure.csv, fig_budget.png, fig_timeseries.png.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "results"
KEYS = ["method", "mode", "option", "strategy", "budget"]


def agg(df, keys):
    def one(g):
        leads = [int(x) for s in g["leads"].dropna().astype(str) for x in s.split() if x not in ("", "nan")]
        ev = g["events"].sum()
        return pd.Series({
            "runs": len(g), "events": ev,
            "pod": g["hits"].sum() / ev if ev else np.nan,
            "late": g["late"].sum(),
            "median_lead_s": np.median(leads) if leads else np.nan,
            "fa_per_hour": g["false_alarms"].sum() / g["hours"].sum(),
            "rmse_sensed": g["rmse_sensed"].mean(), "rmse_unsensed": g["rmse_unsensed"].mean()})
    return df.groupby(keys, dropna=False).apply(one, include_groups=False).reset_index().round(3)


def main():
    core = pd.read_csv(OUT / "runs_core.csv")
    main_ = core[core["group"] == "main"]
    agg(main_, KEYS).to_csv(OUT / "summary_main.csv", index=False)
    base = core[core["group"] == "baseline"]
    agg(base, KEYS).to_csv(OUT / "summary_baselines.csv", index=False)
    agg(core[core["group"] == "failure"], ["mode", "option"]).to_csv(OUT / "summary_failure.csv", index=False)
    agg(core[core["group"] != "failure"], ["scenario"] + KEYS).to_csv(OUT / "summary_by_scenario.csv", index=False)
    held = OUT / "runs_heldout.csv"
    if held.exists():
        h = pd.read_csv(held)
        agg(h, ["scenario"] + KEYS).to_csv(OUT / "summary_heldout.csv", index=False)

    # detection rate and lead time against sensor budget, per placement (twin, option A and B)
    s = agg(main_, KEYS)
    fig, axes = plt.subplots(2, 2, figsize=(7, 4.6), sharex=True)
    colours = {"random": "#9aa5b1", "entrance_exit": "#e0a458", "bottleneck": "#4a78b5", "greedy_mi": "#c8553d"}
    for col, mode in enumerate(("phones", "tags")):
        for strat, c in colours.items():
            for opt, ls in (("A", "-"), ("B", "--")):
                d = s[(s["mode"] == mode) & (s["strategy"] == strat) & (s["option"] == opt)].sort_values("budget")
                axes[0, col].plot(d["budget"], d["pod"], ls, color=c, marker="o", ms=3,
                                  label=f"{strat} ({opt})" if col == 0 else None)
                axes[1, col].plot(d["budget"], d["fa_per_hour"], ls, color=c, marker="o", ms=3)
        axes[0, col].set_title("Phones (Wi-Fi)" if mode == "phones" else "BLE tags", fontsize=9)
        axes[1, col].set_xlabel("Number of sensors")
    axes[0, 0].set_ylabel("Detection rate")
    axes[1, 0].set_ylabel("False alarms per hour")
    for a in axes.flat:
        a.set_xticks([2, 4, 6])
        a.grid(alpha=0.3)
    fig.legend(loc="lower center", ncol=4, fontsize=7, frameon=False)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(OUT / "fig_budget.png", dpi=200)


def timeseries(run_id="surge-s05", mode="phones", strategy="bottleneck", budget=4):
    """One test run: true vs estimated density in Z05 and the forecast probability of red."""
    from evaluation.truth import truth
    from experiments.placement import place
    from shared.venue import Venue
    from twin.run_twin import run
    v = Venue()
    occ, _ = truth(run_id)
    z = v.idx["Z05"]
    sensors = place(strategy, budget, mode, int(run_id[-2:]))
    out = run(run_id, "twin", mode, sensors, seed=int(run_id[-2:]))
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.plot(np.arange(len(occ)), occ[:, z] / v.area[z], color="#222", lw=1.2, label="True density")
    ax.plot(out["t"], out["est"][:, z], color="#4a78b5", lw=1.2, label="Twin estimate")
    ax.axhline(v.red[z], color="#c8553d", ls=":", lw=1, label="Red threshold")
    for zz, t in out["red"]:
        if zz == z:
            ax.axvline(t, color="#c8553d", lw=1, alpha=0.7)
    ax2 = ax.twinx()
    ax2.fill_between(out["t"], out["p_red"][:, z], color="#c8553d", alpha=0.12, label="P(red within 2 min)")
    ax2.set_ylim(0, 1)
    ax2.set_ylabel("Forecast probability")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Density Z05 (p/m²)")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "fig_timeseries.png", dpi=200)


if __name__ == "__main__":
    main()
    timeseries()
