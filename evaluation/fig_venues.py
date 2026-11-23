"""Paper figure with both venues: zones, candidate sensor spots and the four bottleneck-placement sensors
with their 10 m range. Reads only the venue files, so it needs no simulation data."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

from sensors.emulator import RANGE
from shared.venue import ROOT, VENUES, Venue

FILL = {"static": "#dfe7f2", "dynamic": "#f3e3cf"}


def panel(ax, v, title):
    for z, b, kind in zip(v.zone_ids, v.bounds, v.kind):
        ax.add_patch(Rectangle((b[0], b[2]), b[1] - b[0], b[3] - b[2], fc=FILL[kind], ec="#6b7785", lw=0.7))
        w, h = b[1] - b[0], b[3] - b[2]
        if w >= 8 and h >= 6:
            ax.text(b[0] + 0.5, b[3] - 0.5, z, ha="left", va="top", fontsize=6.5, fontweight="bold")
        elif w >= 6 and h >= 6:  # narrower zones: bottom corner, clear of the sensor spots
            ax.text(b[0] + 0.4, b[2] + 0.4, z, ha="left", va="bottom", fontsize=6.5, fontweight="bold")
        else:  # small zones (gates, checkpoint): label outside
            ax.text((b[0] + b[1]) / 2, b[2] - 0.6, z, ha="center", va="top", fontsize=5.5)
    chosen = v.presets["bottleneck"][:4]
    for i, (x, y) in enumerate(v.candidates):
        on = i in chosen
        ax.plot(x, y, "o", ms=3.5 if on else 2, color="#c8553d" if on else "#55606e", zorder=3)
        if on:
            ax.add_patch(Circle((x, y), RANGE, fc="#c8553d", alpha=0.07, ec="#c8553d", lw=0.5))
    for e in v.exit_areas:
        cx, cy = e.centroid.x, e.centroid.y
        ax.annotate("exit", (cx + 0.5, cy), (cx + 3.5, cy), fontsize=6, va="center",
                    arrowprops=dict(arrowstyle="<-", lw=0.6))
    sp = v.entrance["spawn"]
    cy = (sp["y_min"] + sp["y_max"]) / 2
    ax.annotate("in", (sp["x_min"], cy), (sp["x_min"] - 5, cy), fontsize=6, va="center",
                arrowprops=dict(arrowstyle="->", lw=0.6))
    x0, x1 = v.bounds[:, 0].min(), v.bounds[:, 1].max()
    y0, y1 = v.bounds[:, 2].min(), v.bounds[:, 3].max()
    ax.set_xlim(x0 - 7, x1 + 7)
    ax.set_ylim(y0 - 3, y1 + 2)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=8)
    ax.tick_params(labelsize=6)
    ax.set_xlabel("x (m)", fontsize=7)


def main():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7), gridspec_kw={"width_ratios": [1.15, 1]})
    panel(axes[0], Venue(VENUES / "concert_venue_v1.json"), "(a) Venue 1: concert venue (1,194 m²)")
    panel(axes[1], Venue(VENUES / "festival_hall_v2.json"), "(b) Venue 2: festival hall (1,652 m²)")
    axes[0].set_ylabel("y (m)", fontsize=7)
    fig.tight_layout()
    out = ROOT / "data" / "results" / "fig_venues.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=220)
    print("wrote", out)


if __name__ == "__main__":
    main()
