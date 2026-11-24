"""One-command live demo: starts the twin service and the logger, then the sensors, against a
broker that is already running (see broker/README.md). Prints the live alerts and the latency.

  python -m live.demo --run gradual-s04 --mode tags --placement bottleneck --budget 4 --speed 10
"""
import argparse
import subprocess
import sys
import time

from experiments.placement import place
from sensors import emulator
from shared.venue import data_dir
from sim.scenarios import SCENARIOS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="gradual-s04")
    ap.add_argument("--mode", choices=["phones", "tags"], default="tags")
    ap.add_argument("--noise", default="medium")
    ap.add_argument("--placement", default="bottleneck")
    ap.add_argument("--budget", type=int, default=4)
    ap.add_argument("--sketches", action="store_true")
    ap.add_argument("--fail", action="store_true")
    ap.add_argument("--speed", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=None, help="default: the run's own seed, as in the experiments")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", default="1883")
    ap.add_argument("--out", default="data/results/live_latency.csv")
    ap.add_argument("--dashboard", action="store_true", help="also open the live dashboard (live/dashboard.py)")
    ap.add_argument("--password", default=None,
                    help="broker with the ACL (broker/mosquitto.conf, Docker): each part logs in as its own user")
    args = ap.parse_args()
    if args.seed is None:  # same sensor noise and ensemble as the experiment row for this run
        args.seed = int(args.run[-2:])

    traj = data_dir() / "trajectories" / f"{args.run}.csv"
    if not traj.exists():  # fresh clone or container: simulate this run first (same seed, same crowd)
        name, seed = args.run.rsplit("-s", 1)
        print(f"no trajectories for {args.run}, simulating it first (a few minutes)", flush=True)
        subprocess.run([sys.executable, "-m", "sim.run_sim", name, str(int(seed))], check=True)

    ids = [emulator.CAND_IDS[c] for c in place(args.placement, args.budget, args.mode, args.seed, args.noise)]
    phase = SCENARIOS[args.run.rsplit("-", 1)[0]].get("movement", "egress")  # the event schedule
    broker = ["--host", args.host, "--port", args.port]
    opt = ["--sketches"] if args.sketches else []

    def login(user):  # ACL users from broker/acl; nothing to add on the open test broker
        return ["--user", user, "--password", args.password] if args.password else []

    py = [sys.executable, "-m"]
    dash = None
    if args.dashboard:  # the dashboard has to be listening before the run starts
        dash = subprocess.Popen(py + ["live.dashboard"] + broker + login("evaluator"))
        time.sleep(2)
    logger = subprocess.Popen(py + ["live.logger", "--out", args.out] + broker + login("evaluator"))
    twin = subprocess.Popen(py + ["live.twin_service", "--sensors", ",".join(ids), "--mode", args.mode, "--noise",
                                  args.noise, "--phase", phase, "--seed", str(args.seed), "--speed", str(args.speed)]
                            + opt + broker + login("twin"))
    sim = ["--sim-user", "simulator", "--sim-password", args.password] if args.password else []
    pub = subprocess.Popen(py + ["live.publisher", "--run", args.run, "--mode", args.mode, "--noise", args.noise,
                                 "--placement", args.placement, "--budget", str(args.budget), "--speed", str(args.speed),
                                 "--seed", str(args.seed)] + opt + (["--fail"] if args.fail else []) + broker
                           + login("sensor_emulator") + sim)
    while pub.poll() is None:
        if twin.poll() not in (None, 0):  # twin crashed: don't leave the sensors waiting for it
            pub.terminate()
            logger.terminate()
            print("twin stopped with an error (see above)", flush=True)
            return 1
        time.sleep(0.5)
    twin.wait()
    logger.wait()
    if dash:
        print("dashboard still open (the recording is saved); Ctrl+C to close it", flush=True)
        try:
            dash.wait()
        except KeyboardInterrupt:
            dash.terminate()
    return pub.returncode


if __name__ == "__main__":
    sys.exit(main())
