"""Replay one simulation run in the browser, with the sensors and the twin next to the truth.

Writes data/replays/{run}_{mode}_{noise}_{strategy}{budget}{option}.html (self-contained, open it
in any browser). People are coloured by state: grey = waiting to leave (ingress: standing), blue = walking,
red = departed but nearly stopped (queue or jam). Zones are filled by their true density.

Usage: python -m evaluation.replay surge-s05 --mode tags --noise medium --strategy bottleneck --budget 4
"""
import argparse
import base64
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.truth import truth
from experiments.placement import place
from sensors import emulator
from shared.venue import Venue, data_dir
from sim.scenarios import SCENARIOS
from twin.run_twin import run

DATA = data_dir()
STEP = 2      # keep every 2nd frame (0.4 s)
FPS = 5
STUCK = 0.15  # m/s: slower than this after setting off counts as stopped


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def people(run_id, ingress=False):
    # positions every 0.4 s, in decimetres, plus a state per person and frame
    # (ingress: grey = standing in the hall, red = slow in the entrance)
    t = pd.read_csv(DATA / "trajectories" / f"{run_id}.csv")
    t = t[t["frame"] % STEP == 0].sort_values(["id", "frame"])
    first = t.groupby("id")[["x", "y"]].transform("first")
    moved = np.hypot(t["x"] - first["x"], t["y"] - first["y"]) > 0.5
    left_home = moved.groupby(t["id"]).cummax()
    dx = t.groupby("id")[["x", "y"]].diff()
    speed = np.hypot(dx["x"], dx["y"]).fillna(0) / (STEP / FPS)
    if ingress:
        state = np.where(speed >= STUCK, 1, np.where(t["x"] >= -18.0, 0, 2)).astype(np.uint8)
    else:
        state = np.where(~left_home, 0, np.where(speed < STUCK, 2, 1)).astype(np.uint8)
    t = t.assign(state=state).sort_values(["frame", "id"])
    frames = np.arange(0, t["frame"].max() + 1, STEP)
    counts = t.groupby("frame").size().reindex(frames, fill_value=0).to_numpy()
    xy = np.round(t[["x", "y"]].to_numpy() * 10).astype(np.int16)
    return frames, counts, xy, t["state"].to_numpy()


def build(run_id, mode, noise, strategy, budget, option):
    v = Venue()
    cfg = SCENARIOS[run_id.split("-")[0]]
    seed = int(run_id[-2:])
    occ, _ = truth(run_id)
    sensors = place(strategy, budget, mode, seed, noise)
    out = run(run_id, "twin", mode, sensors, sketches=option == "B", seed=seed, noise=noise)
    rd = emulator.readings(emulator.observe(run_id, mode, noise), sensors, seed=seed)
    ingress = cfg.get("movement") == "ingress"
    frames, counts, xy, state = people(run_id, ingress)

    g = v.walkable
    if "block" in cfg:
        from shapely.geometry import box
        x0, x1, y0, y1 = cfg["block"]
        g = g.difference(box(x0, y0, x1, y1))
    polys = list(getattr(g, "geoms", [g]))
    data = {
        "run": run_id, "setup": f"{mode}, {noise} noise, {strategy} x{budget}, option {option}",
        "key": ["standing in the hall", "walking", "slow in the entrance"] if ingress else ["waiting", "walking", "departed, nearly stopped"],
        "zones": [{"id": z, "b": list(map(float, b)), "red": float(r), "amber": float(a)}
                  for z, b, r, a in zip(v.zone_ids, v.bounds, v.red, v.amber)],
        "walk": [[list(map(list, p.exterior.coords))] + [list(map(list, h.coords)) for h in p.interiors] for p in polys],
        "exit": [41, 42, -1.5, 1.5],
        "sensors": [{"id": emulator.CAND_IDS[c], "x": emulator.CANDIDATES[c][0], "y": emulator.CANDIDATES[c][1]} for c in sensors],
        "range": emulator.RANGE,
        "truth": np.round(occ / v.area, 2).tolist(),
        "report_t": out["t"].tolist(),
        "est": np.round(out["est"], 2).tolist(),
        "p_red": np.round(out["p_red"], 2).tolist(),
        "alerts": [[v.zone_ids[z], t] for z, t in out["red"]],
        "readings": [[None if np.isnan(c) else int(c) for c in row] for row in rd["counts"][:len(out["t"])]],
        "dt": STEP / FPS, "counts": b64(counts.astype(np.int32)), "xy": b64(xy), "state": b64(state),
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(data))
    name = f"{run_id}_{mode}_{noise}_{strategy}{budget}{option}.html"
    (DATA / "replays").mkdir(parents=True, exist_ok=True)
    (DATA / "replays" / name).write_text(html, encoding="utf-8")
    return DATA / "replays" / name


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Replay</title>
<style>
 body{font:13px system-ui,sans-serif;margin:12px;color:#1d2733;background:#fafbfc}
 h1{font-size:16px;margin:0 0 2px} .sub{color:#5b6775;margin-bottom:8px}
 #wrap{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
 canvas{background:#fff;border:1px solid #d5dbe2;border-radius:6px}
 #side{min-width:300px} table{border-collapse:collapse;width:100%} td,th{padding:2px 6px;text-align:right}
 th{color:#5b6775;font-weight:600} td:first-child,th:first-child{text-align:left}
 .ctl{display:flex;gap:8px;align-items:center;margin:8px 0;flex-wrap:wrap} button,select{font:inherit;padding:3px 10px}
 input[type=range]{width:520px} .key span{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 4px 0 10px;vertical-align:-1px}
 #log{max-height:160px;overflow:auto;color:#a33}
</style></head><body>
<h1 id="title"></h1><div class="sub" id="setup"></div>
<div class="ctl"><button id="play">Play</button>
 <select id="spd"><option>1</option><option>4</option><option selected>10</option><option>30</option></select>x
 <input type="range" id="slider" min="0" value="0"> <b id="clock"></b></div>
<div class="key"><span style="background:#9aa5b1"></span><i class="k0"></i> <span style="background:#2f6fd6"></span><i class="k1"></i>
 <span style="background:#d6402f"></span><i class="k2"></i> &nbsp;|&nbsp; zone fill = true density (amber 3, red at threshold)
 &nbsp;|&nbsp; circles = sensor range, number = last reading</div>
<div id="wrap"><canvas id="cv" width="960" height="420"></canvas>
<div id="side"><div id="inside"></div><table id="tab"></table><p><b>Twin red alerts</b></p><div id="log"></div></div></div>
<script>
const D = __DATA__;
const dec = (s, T) => { const b = atob(s), u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return new T(u.buffer); };
const counts = dec(D.counts, Int32Array), xy = dec(D.xy, Int16Array), st = dec(D.state, Uint8Array);
const start = new Int32Array(counts.length + 1); for (let i = 0; i < counts.length; i++) start[i + 1] = start[i] + counts[i];
const cv = document.getElementById("cv"), cx = cv.getContext("2d");
const X0 = -30, X1 = 45, Y0 = -14, Y1 = 14, S = Math.min(cv.width / (X1 - X0), cv.height / (Y1 - Y0));
const px = x => (x - X0) * S, py = y => cv.height - (y - Y0) * S;
const slider = document.getElementById("slider"); slider.max = counts.length - 1;
document.getElementById("title").textContent = D.run; document.getElementById("setup").textContent = D.setup;
D.key.forEach((k, i) => document.querySelector(".k" + i).textContent = k);
const colour = (d, z) => d >= z.red ? "rgba(214,64,47,.35)" : d >= z.amber ? "rgba(224,164,88,.35)" : `rgba(47,111,214,${Math.min(.25, d / 12)})`;
let f = 0, playing = false, last = 0;
function reportIndex(t) { let i = 0; while (i + 1 < D.report_t.length && D.report_t[i + 1] <= t) i++; return D.report_t[0] <= t ? i : -1; }
function draw() {
  const t = f * D.dt, sec = Math.min(Math.floor(t), D.truth.length - 1), ri = reportIndex(t);
  cx.clearRect(0, 0, cv.width, cv.height);
  cx.fillStyle = "#eef1f4"; cx.fillRect(0, 0, cv.width, cv.height);
  for (const p of D.walk) { cx.beginPath(); for (const ring of p) { ring.forEach(([x, y], k) => k ? cx.lineTo(px(x), py(y)) : cx.moveTo(px(x), py(y))); cx.closePath(); } cx.fillStyle = "#fff"; cx.fill("evenodd"); }
  D.zones.forEach((z, k) => { const [x0, x1, y0, y1] = z.b, d = D.truth[sec][k];
    cx.fillStyle = colour(d, z); cx.fillRect(px(x0), py(y1), (x1 - x0) * S, (y1 - y0) * S);
    cx.strokeStyle = "#b8c2cc"; cx.strokeRect(px(x0), py(y1), (x1 - x0) * S, (y1 - y0) * S);
    cx.fillStyle = "#5b6775"; cx.font = "11px system-ui"; cx.fillText(z.id, px(x0) + 3, py(y1) + 12); });
  cx.fillStyle = "#3c8d5a"; const e = D.exit; cx.fillRect(px(e[0]), py(e[3]), (e[1] - e[0]) * S, (e[3] - e[2]) * S);
  const pal = ["#9aa5b1", "#2f6fd6", "#d6402f"];
  for (let i = start[f]; i < start[f + 1]; i++) { cx.fillStyle = pal[st[i]]; cx.beginPath(); cx.arc(px(xy[2 * i] / 10), py(xy[2 * i + 1] / 10), 2.2, 0, 6.29); cx.fill(); }
  D.sensors.forEach((s, k) => { cx.strokeStyle = "rgba(124,58,237,.6)"; cx.setLineDash([4, 4]); cx.beginPath(); cx.arc(px(s.x), py(s.y), D.range * S, 0, 6.29); cx.stroke(); cx.setLineDash([]);
    cx.fillStyle = "#7c3aed"; cx.fillRect(px(s.x) - 4, py(s.y) - 4, 8, 8);
    const r = ri >= 0 ? D.readings[ri][k] : null; cx.font = "bold 12px system-ui"; cx.fillText(`${s.id}: ${r === null ? "lost" : r}`, px(s.x) + 6, py(s.y) - 6); });
  D.alerts.forEach(([zid, ta]) => { if (ta <= t) { const z = D.zones.find(q => q.id === zid), [x0, x1, y0, y1] = z.b; cx.strokeStyle = "#d6402f"; cx.lineWidth = 3; cx.strokeRect(px(x0), py(y1), (x1 - x0) * S, (y1 - y0) * S); cx.lineWidth = 1; } });
  document.getElementById("clock").textContent = `t = ${t.toFixed(1)} s`;
  document.getElementById("inside").innerHTML = `<b>${counts[f]}</b> people in the venue`;
  let h = "<tr><th>Zone</th><th>true p/m²</th><th>twin p/m²</th><th>P(red, 2 min)</th></tr>";
  D.zones.forEach((z, k) => { const tr = D.truth[sec][k], es = ri >= 0 ? D.est[ri][k] : 0, pr = ri >= 0 ? D.p_red[ri][k] : 0;
    h += `<tr><td>${z.id}</td><td style="color:${tr >= z.red ? "#d6402f" : "inherit"}">${tr.toFixed(2)}</td><td>${es.toFixed(2)}</td><td>${(100 * pr).toFixed(0)} %</td></tr>`; });
  document.getElementById("tab").innerHTML = h;
  document.getElementById("log").innerHTML = D.alerts.filter(a => a[1] <= t).map(a => `${a[0]} at ${a[1]} s`).join("<br>") || "none yet";
  slider.value = f;
}
function tick(now) { if (playing) { const adv = (now - last) / 1000 * +document.getElementById("spd").value / D.dt; if (adv >= 1) { f = Math.min(counts.length - 1, f + Math.floor(adv)); last = now; draw(); if (f === counts.length - 1) playing = false; } } requestAnimationFrame(tick); }
document.getElementById("play").onclick = e => { playing = !playing; last = performance.now(); e.target.textContent = playing ? "Pause" : "Play"; };
slider.oninput = () => { f = +slider.value; draw(); };
draw(); requestAnimationFrame(tick);
</script></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--mode", default="tags", choices=["phones", "tags"])
    ap.add_argument("--noise", default="medium", choices=emulator.NOISE_LEVELS)
    ap.add_argument("--strategy", default="bottleneck", choices=["random", "entrance_exit", "bottleneck", "greedy_mi"])
    ap.add_argument("--budget", type=int, default=4)
    ap.add_argument("--option", default="A", choices=["A", "B"])
    a = ap.parse_args()
    print(build(a.run, a.mode, a.noise, a.strategy, a.budget, a.option))
