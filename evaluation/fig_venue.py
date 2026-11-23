"""Venue figure: zones, candidate sensor spots and one placement's 10 m ranges."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

from experiments.placement import place
from sensors.emulator import CAND_IDS, CANDIDATES, RANGE
from shared.venue import Venue, data_dir

OUT = data_dir() / "results"


def main(strategy="greedy_mi", budget=4, mode="phones"):
    v = Venue()
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    fill = {"static": "#dfe7f2", "dynamic": "#f3e3cf"}
    for z, b, kind in zip(v.zone_ids, v.bounds, v.kind):
        ax.add_patch(Rectangle((b[0], b[2]), b[1] - b[0], b[3] - b[2], fc=fill[kind], ec="#6b7785", lw=0.8))
        name = v.zones[v.idx[z]]["name"]
        label = z if b[1] - b[0] < 7 else f"{z}\n{name}"
        ax.text((b[0] + b[1]) / 2, b[3] + 0.4 if z != "Z06" else b[2] - 1.6, label, ha="center", va="bottom", fontsize=6)
    chosen = place(strategy, budget, mode)
    for i, (x, y) in enumerate(CANDIDATES):
        on = i in chosen
        ax.plot(x, y, "o", ms=4 if on else 2.5, color="#c8553d" if on else "#55606e")
        if on:
            ax.add_patch(Circle((x, y), RANGE, fc="#c8553d", alpha=0.08, ec="#c8553d", lw=0.6))
            ax.text(x + 0.6, y + 0.6, CAND_IDS[i], fontsize=6, color="#c8553d")
    ax.annotate("exit", (42, 0), (43.5, -0.4), fontsize=6)
    ax.set_xlim(-30, 46)
    ax.set_ylim(-14, 15)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    fig.tight_layout()
    fig.savefig(OUT / "fig_venue.png", dpi=200)
    print(strategy, budget, [CAND_IDS[c] for c in chosen])


if __name__ == "__main__":
    main()
