"""Make dashboard recordings for several runs in one go (for the symposium backup).

Starts the Python broker (unless one is already running) and the dashboard, then plays each run
through live.demo; the dashboard saves one replayable HTML per run in the results folder.

  python -m live.record gradual-s04 counterflow-s06 ingress-s03 surge-s05:fail
  (venue 2: set CROWDTWIN_VENUE=festival_hall_v2 first)

A run name followed by ":fail" uses the failure test; options apply to every run.
"""
import argparse
import socket
import subprocess
import sys
import time

from shared.venue import data_dir


def broker_up(host, port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--mode", choices=["phones", "tags"], default="tags")
    ap.add_argument("--placement", default="bottleneck")
    ap.add_argument("--speed", type=float, default=10.0)
    ap.add_argument("--port", type=int, default=1883)
    args = ap.parse_args()
    py = [sys.executable, "-m"]
    started = []
    if not broker_up("localhost", args.port):
        started.append(subprocess.Popen(py + ["live.broker", "--port", str(args.port)]))
        time.sleep(2)
    started.append(subprocess.Popen(py + ["live.dashboard", "--no-browser", "--port", str(args.port)]))
    time.sleep(2)
    try:
        for item in args.runs:
            run, _, flag = item.partition(":")
            print(f"--- {run}{' (sensor failure)' if flag == 'fail' else ''}", flush=True)
            subprocess.run(py + ["live.demo", "--run", run, "--mode", args.mode, "--placement", args.placement,
                                 "--speed", str(args.speed), "--port", str(args.port),
                                 "--out", str(data_dir() / "results" / "live_latency_record.csv")]
                           + (["--fail"] if flag == "fail" else []), check=True)
            time.sleep(2)  # the dashboard saves the recording a second after the twin stops
    finally:
        for p in reversed(started):
            p.terminate()
    print(f"recordings in {data_dir() / 'results'} (dashboard_<run>.html)", flush=True)


if __name__ == "__main__":
    main()
