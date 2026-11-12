"""Standalone management CLI (worker runner, DB health check)."""

from __future__ import annotations

import argparse
import signal
import time

import app.tasks.handlers  # noqa: F401
from app.tasks.queue import Worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Recova backend management CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("worker", help="Run standalone background job worker")
    w.add_argument("--concurrency", type=int, default=2)

    args = parser.parse_args()
    if args.cmd == "worker":
        worker = Worker(concurrency=args.concurrency)
        worker.start()
        stop = False

        def _sig(_s, _f):
            nonlocal stop
            stop = True

        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)
        while not stop:
            time.sleep(1)
        worker.stop()


if __name__ == "__main__":
    main()
