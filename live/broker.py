"""Pure-Python MQTT broker (amqtt) for live mode, for PCs where Mosquitto can't run
(e.g. Windows application control). No passwords or topic rules: local testing only.

  python -m live.broker [--port 1883]
"""
import argparse
import asyncio
import logging

from amqtt.broker import Broker


async def serve(port):
    broker = Broker({
        "listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{port}"}},
        "plugins": {"amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True}},
    })
    await broker.start()
    print(f"broker listening on 127.0.0.1:{port} (Ctrl+C to stop)", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await broker.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=1883)
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    try:
        asyncio.run(serve(args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
