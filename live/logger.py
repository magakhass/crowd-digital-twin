"""Listens to the twin's outputs and logs end-to-end latency: from the moment the last
sensor message of a report was sent to the moment the twin's state for it arrived here.

  python -m live.logger --out data/results/live_latency.csv
"""
import argparse
import csv
import json
import time
from pathlib import Path

from live.common import broker_args, connect
from shared.venue import Venue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/results/live_latency.csv")
    ap.add_argument("--quiet-after", type=float, default=600.0, help="give up after this many idle seconds")
    broker_args(ap)
    args = ap.parse_args()
    venue = Venue()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, alerts = [], []
    last, stop = [time.time()], [False]

    def on_message(c, u, m):
        now = time.time()
        msg = json.loads(m.payload)
        last[0] = now
        if not m.topic.startswith(f"twin/{venue.id}/"):
            return
        if m.topic.endswith("/status"):
            stop[0] = stop[0] or (msg["status"] == "offline" and not m.retain)  # the twin finished
        elif m.topic.endswith("/state") and msg["last_sent_at"] is not None:
            rows.append({"seq": msg["seq"], "ts": msg["ts"], "sensors_in": len(msg["sensors_in"]),
                         "compute_ms": msg["compute_ms"], "e2e_ms": round(1000 * (now - msg["last_sent_at"]), 2)})
        elif m.topic.endswith("/alerts"):
            alerts.append({"ts": msg["ts"], "zone_id": msg["zone_id"], "level": msg["level"], "p": msg["p"],
                           "delay_ms": None if msg["last_sent_at"] is None else round(1000 * (now - msg["last_sent_at"]), 2)})

    c = connect(args, "logger")
    c.on_message = on_message
    c.subscribe(f"twin/{venue.id}/#", qos=1)
    print("logging twin output...", flush=True)
    while not stop[0] and time.time() - last[0] < args.quiet_after:
        time.sleep(0.2)
    c.disconnect()
    c.loop_stop()
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, ["seq", "ts", "sensors_in", "compute_ms", "e2e_ms"])
        w.writeheader()
        w.writerows(rows)
    with out.with_name(out.stem + "_alerts.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, ["ts", "zone_id", "level", "p", "delay_ms"])
        w.writeheader()
        w.writerows(alerts)
    if rows:
        import numpy as np
        e2e, comp = np.array([r["e2e_ms"] for r in rows]), np.array([r["compute_ms"] for r in rows])
        print(f"{len(rows)} reports, end-to-end median {np.median(e2e):.1f} ms, 95th {np.percentile(e2e, 95):.1f} ms, "
              f"max {e2e.max():.1f} ms; twin compute median {np.median(comp):.1f} ms", flush=True)
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()
