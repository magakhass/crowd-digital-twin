"""Tables and figures for the paper from data/results/runs_*.csv (the active venue's results folder).
Venue 2 (runs_small.csv) is scored on amber warnings, since no zone there reaches red (evidence log D23):
summary_small_compare.csv, summary_small_by_scenario.csv, summary_small_placement.csv, fig_timeseries.png.

Writes to data/results/: summary_main.csv, summary_baselines.csv, summary_heldout.csv, summary_movements.csv,
summary_failure.csv, summary_noise.csv, summary_compare.csv, summary_placement.csv, fig_budget.png, fig_noise.png, fig_timeseries.png.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from shared.venue import data_dir

OUT = data_dir() / "results"
KEYS = ["method", "mode", "noise", "option", "strategy", "budget"]
LEVELS = ["low", "medium", "high"]


def extra(g):
    # metrics added on 23 Nov; older result files do not have them
    if "alerts" not in g:
        return {}
    am = g["amber_events"].sum()
    out = {"far": g["false_alarms"].sum() / max(1, g["alerts"].sum()),
           "mae_sensed": g["mae_sensed"].mean(), "mae_unsensed": g["mae_unsensed"].mean(),
           "amber_pod": g["amber_hits"].sum() / am if am else np.nan,
           "amber_fa_per_hour": g["amber_false_alarms"].sum() / g["hours"].sum(),
           "red_alerts_per_hour": g["alerts"].sum() / g["hours"].sum()}
    if "amber_leads" in g:
        al = [int(x) for v in g["amber_leads"].dropna().astype(str) for x in v.split() if x not in ("", "nan")]
        out.update(amber_events=am, amber_late=g["amber_late"].sum(), amber_median_lead_s=np.median(al) if al else np.nan)
    return out


def ci(df, keys, n=2000, seed=0, level="red"):
    """95 % bootstrap intervals for detection rate and false alarms per hour, resampling whole test
    runs (all setups of a run stay together, since they share the same events). level="amber" gives
    the same for amber warnings (columns amber_pod_lo, ...)."""
    rng = np.random.default_rng(seed)
    cols = ["hits", "events", "false_alarms", "hours"]
    if level == "amber":
        cols = ["amber_hits", "amber_events", "amber_false_alarms", "hours"]
    out = []
    for key, g in df.groupby(keys, dropna=False):
        per_run = g.groupby("run")[cols].sum()
        x = per_run.to_numpy()
        idx = rng.integers(0, len(x), (n, len(x)))
        s = x[idx].sum(1)
        pod = np.where(s[:, 1] > 0, s[:, 0] / np.maximum(s[:, 1], 1), np.nan)
        fa = s[:, 2] / s[:, 3]
        out.append(dict(zip(keys, key if isinstance(key, tuple) else (key,)),
                        pod_lo=np.nanpercentile(pod, 2.5) if np.isfinite(pod).any() else np.nan,  # no events: no rate
                        pod_hi=np.nanpercentile(pod, 97.5) if np.isfinite(pod).any() else np.nan,
                        fa_lo=np.percentile(fa, 2.5), fa_hi=np.percentile(fa, 97.5)))
    res = pd.DataFrame(out).round(3)
    if level == "amber":
        res = res.rename(columns={c: "amber_" + c for c in ("pod_lo", "pod_hi", "fa_lo", "fa_hi")})
    return res


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
            "rmse_sensed": g["rmse_sensed"].mean(), "rmse_unsensed": g["rmse_unsensed"].mean(),
            **extra(g)})
    return df.groupby(keys, dropna=False).apply(one, include_groups=False).reset_index().round(3)


def small():
    """Venue 2: every scenario at medium noise and 4 sensors, scored on amber warnings; any red alert
    there is a false alarm, since no zone reaches red."""
    df = pd.read_csv(OUT / "runs_small.csv")
    agg(df, ["scenario"] + KEYS).to_csv(OUT / "summary_small_by_scenario.csv", index=False)
    keys = ["method", "option"]
    (agg(df, keys).merge(ci(df, keys)).merge(ci(df, keys, level="amber"))
     .to_csv(OUT / "summary_small_compare.csv", index=False))
    tw = df[df["method"] == "twin"]
    keys = ["mode", "strategy"]
    agg(tw, keys).merge(ci(tw, keys, level="amber")).to_csv(OUT / "summary_small_placement.csv", index=False)


def main():
    if (OUT / "runs_small.csv").exists():
        small()
    if not (OUT / "runs_core.csv").exists():
        return
    core = pd.read_csv(OUT / "runs_core.csv")
    main_ = core[core["group"] == "main"]
    agg(main_, KEYS).to_csv(OUT / "summary_main.csv", index=False)
    base = core[core["group"] == "baseline"]
    agg(base, KEYS).to_csv(OUT / "summary_baselines.csv", index=False)
    fail = core[core["group"] == "failure"]
    fs = agg(fail, ["mode", "option"])
    if "blind_lead" in fail:  # coverage-loss alert: how long before the first event it fired
        fs = fs.merge(fail.groupby(["mode", "option"])["blind_lead"].median().rename("median_blind_lead_s").reset_index())
    fs.to_csv(OUT / "summary_failure.csv", index=False)
    agg(core[core["group"] != "failure"], ["scenario"] + KEYS).to_csv(OUT / "summary_by_scenario.csv", index=False)
    for which in ("heldout", "movements"):
        f = OUT / f"runs_{which}.csv"
        if f.exists():
            agg(pd.read_csv(f), ["scenario"] + KEYS).to_csv(OUT / f"summary_{which}.csv", index=False)
    # twin against the baselines on the same setups (4 sensors; the baselines only run with 4)
    same = core[(core["group"] != "failure") & ((core["budget"] == 4) | (core["method"] == "full"))]
    agg(same, ["method", "option"]).merge(ci(same, ["method", "option"])).to_csv(OUT / "summary_compare.csv", index=False)
    tw = main_[main_["method"] == "twin"]
    agg(tw, ["strategy", "budget"]).merge(ci(tw, ["strategy", "budget"])).to_csv(OUT / "summary_placement.csv", index=False)
    sensed = core[core["method"].isin(["twin", "sensor", "trend"]) & (core["group"] != "failure") & (core["budget"] == 4)]
    agg(sensed, ["method", "mode", "noise", "option"]).to_csv(OUT / "summary_noise.csv", index=False)
    fig_noise(sensed)

    # detection rate and false alarms against sensor budget, per placement (twin, medium noise)
    s = agg(main_[main_["noise"] == "medium"], KEYS)
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


def fig_noise(sensed):
    # detection rate, false alarms and sensed-zone error by noise level: twin A/B against the baselines
    lines = [("twin", "A", "#4a78b5", "-", "Twin, option A"), ("twin", "B", "#4a78b5", "--", "Twin, option B"),
             ("trend", "A", "#e0a458", "-", "Trend"), ("sensor", "A", "#9aa5b1", "-", "Sensor-only")]
    s = agg(sensed, ["method", "mode", "noise", "option"])
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.2), sharex=True)
    for row, mode in enumerate(("phones", "tags")):
        for method, opt, c, ls, lab in lines:
            d = s[(s["method"] == method) & (s["mode"] == mode) & (s["option"] == opt)].set_index("noise").reindex(LEVELS)
            for col, k in enumerate(("pod", "fa_per_hour", "rmse_sensed")):
                axes[row, col].plot(LEVELS, d[k], ls, color=c, marker="o", ms=3, label=lab if row == col == 0 else None)
        axes[row, 0].set_ylabel("Phones (Wi-Fi)" if mode == "phones" else "BLE tags")
    for col, t in enumerate(("Detection rate", "False alarms per hour", "RMSE sensed (p/m²)")):
        axes[0, col].set_title(t, fontsize=9)
        axes[1, col].set_xlabel("Noise level")
    for a in axes.flat:
        a.grid(alpha=0.3)
    fig.legend(loc="lower center", ncol=4, fontsize=7, frameon=False)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(OUT / "fig_noise.png", dpi=200)


def timeseries(run_id="surge-s05", mode="phones", strategy="bottleneck", budget=4, level="red"):
    """One test run: true vs estimated density in the first risk zone and the forecast probability of
    red (or amber, for venue 2)."""
    from evaluation.truth import truth
    from experiments.placement import place
    from shared.venue import Venue
    from twin.run_twin import run
    v = Venue()
    occ, _ = truth(run_id)
    z = v.idx[v.risk_zones[0]]
    sensors = place(strategy, budget, mode, int(run_id[-2:]))
    out = run(run_id, "twin", mode, sensors, seed=int(run_id[-2:]))
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.plot(np.arange(len(occ)), occ[:, z] / v.area[z], color="#222", lw=1.2, label="True density")
    ax.plot(out["t"], out["est"][:, z], color="#4a78b5", lw=1.2, label="Twin estimate")
    col = "#c8553d" if level == "red" else "#d99a2b"
    ax.axhline((v.red if level == "red" else v.amber)[z], color=col, ls=":", lw=1, label=f"{level.capitalize()} threshold")
    for zz, t in out[level]:
        if zz == z:
            ax.axvline(t, color=col, lw=1, alpha=0.7)
    ax2 = ax.twinx()
    ax2.fill_between(out["t"], out["p_" + level][:, z], color=col, alpha=0.12, label=f"P({level} within 2 min)")
    ax2.set_ylim(0, 1)
    ax2.set_ylabel("Forecast probability")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(f"Density {v.risk_zones[0]} (p/m²)")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "fig_timeseries.png", dpi=200)


def typical_run(df, mode="tags", strategy="bottleneck", level="red"):
    """The example run for the timeseries figure, picked by a rule rather than by eye: among the twin's runs
    with this setup (option A, 4 sensors, medium noise), the one whose lead time is closest to the setup's
    median lead (ties: first by name)."""
    col = "leads" if level == "red" else "amber_leads"
    g = df[(df["group"] != "failure") & (df["method"] == "twin") & (df["option"] == "A") & (df["budget"] == 4) & (df["noise"] == "medium")
           & (df["mode"] == mode) & (df["strategy"] == strategy)]
    leads = [(r, int(x)) for r, v in zip(g["run"], g[col].fillna("").astype(str)) for x in v.split() if x not in ("", "nan")]
    med = np.median([l for _, l in leads])
    return sorted(leads, key=lambda x: (abs(x[1] - med), x[0]))[0][0]


if __name__ == "__main__":
    from shared.venue import ACTIVE, DEFAULT
    main()
    if ACTIVE == DEFAULT:
        run_id = typical_run(pd.read_csv(OUT / "runs_core.csv"))
        timeseries(run_id, mode="tags", strategy="bottleneck")
    else:  # venue 2: the entry queue, scored on amber
        run_id = typical_run(pd.read_csv(OUT / "runs_small.csv"), level="amber")
        timeseries(run_id, mode="tags", strategy="bottleneck", level="amber")
    print("timeseries figure:", run_id)
