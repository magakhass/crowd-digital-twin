"""Demo dashboard: listens to the broker as the evaluator (sensors, twin, and the restricted ground
truth) and shows it live in the browser. When the twin finishes, the whole session is saved as one
HTML file that replays in any browser, with no Python, broker or repo.

  python -m live.dashboard            # then open http://localhost:8050 (opens by itself)
  python -m live.demo --run surge-s05 --fail --speed 5     # in a second terminal

Recordings: data/results/dashboard_{run}.html (the active venue's results folder).
"""
import argparse
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from live.common import broker_args, connect
from sensors import emulator
from shared.venue import Venue, data_dir

PAGE = Path(__file__).with_name("dashboard.html")


class Session:
    """Every message of the current run, with its arrival time; cleared when a new twin starts."""

    def __init__(self):
        self.lock = threading.Lock()
        self.msgs, self.gen, self.t0, self.run = [], 0, time.time(), None

    def reset(self):
        with self.lock:
            self.msgs, self.gen, self.t0, self.run = [], self.gen + 1, time.time(), None

    def add(self, topic, payload, retained):
        now = time.time()
        if topic.endswith("/state") and payload.get("last_sent_at"):
            payload["_e2e_ms"] = round(1000 * (now - payload["last_sent_at"]), 1)  # sensor send -> here
        with self.lock:
            if topic.startswith("sim/") and self.run is None:
                self.run = topic.split("/")[1] + ("-failure" if payload.get("failure_test") else "")
            self.msgs.append({"w": round(now - self.t0, 3), "topic": topic, "p": payload, "r": retained})

    def since(self, i):
        with self.lock:
            return self.gen, self.msgs[i:]


def venue_info():
    v = Venue()
    return {"id": v.id, "zones": v.zones, "candidates": v.raw.get("sensor_candidates", []),
            "risk_zones": v.risk_zones, "range_m": emulator.RANGE,
            "gates": v.gates, "entrance": v.entrance}


def render(session=None):
    html = PAGE.read_text(encoding="utf-8").replace("/*VENUE*/null", json.dumps(venue_info()))
    if session is not None:  # a recording: the messages go into the page itself
        _, msgs = session.since(0)
        html = html.replace("/*RECORDING*/null", json.dumps({"run": session.run, "msgs": msgs}, separators=(",", ":")))
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--http-port", type=int, default=8050)
    ap.add_argument("--no-browser", action="store_true")
    broker_args(ap)
    args = ap.parse_args()
    venue = Venue()
    session = Session()
    saved = {"gen": -1}

    def save():
        if not session.msgs or saved["gen"] == session.gen:
            return
        out = data_dir() / "results" / f"dashboard_{session.run or 'session'}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(session), encoding="utf-8")
        saved["gen"] = session.gen
        print(f"recording saved: {out}", flush=True)

    def on_message(c, u, m):
        try:
            payload = json.loads(m.payload)
        except ValueError:
            return
        if m.topic.startswith("sim/") and payload.get("venue_id") != venue.id:
            return  # another venue's run
        if m.topic == f"twin/{venue.id}/status" and not m.retain:
            if payload.get("status") == "online":  # a new run starts
                session.reset()
                print("new run", flush=True)
            elif payload.get("status") == "offline":
                session.add(m.topic, payload, m.retain)
                threading.Timer(1.0, save).start()  # let the last messages arrive
                return
        session.add(m.topic, payload, m.retain)

    c = connect(args, "dashboard")
    c.on_message = on_message
    c.subscribe([(f"venue/{venue.id}/#", 1), (f"twin/{venue.id}/#", 1), ("sim/+/truth", 0)])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/events"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                gen, i = None, 0
                try:
                    while True:  # server-sent events: everything so far, then new messages as they come
                        g, new = session.since(i)
                        if g != gen:
                            if gen is not None:
                                self.wfile.write(b'data: {"reset": true}\n\n')
                            gen, i = g, 0
                            g, new = session.since(0)
                        for m in new:
                            self.wfile.write(b"data: " + json.dumps(m).encode() + b"\n\n")
                        i += len(new)
                        if not new:
                            self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        time.sleep(0.1)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return
            else:
                body = render().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", args.http_port), Handler)
    server.daemon_threads = True
    url = f"http://localhost:{args.http_port}"
    print(f"dashboard on {url} ({venue.id}); Ctrl+C to stop", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        save()
        c.disconnect()
        c.loop_stop()


if __name__ == "__main__":
    main()
