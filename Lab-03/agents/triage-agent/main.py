"""Programmatic entrypoint for the Order Triage Crew.

Used as the AM build's run command: ``python main.py``.

The first thing we do is point ``HOME`` at a writable directory. CrewAI's
instrumentor (auto-attached by Agent Manager at deploy time) initializes
CrewAI's internal telemetry, which writes to ``~/.crewai`` on first use.
Many container runtimes leave ``HOME`` unset; ``os.path.expanduser('~')``
then resolves to ``/nonexistent`` (the system-account default), and the
write fails with ``[Errno 30] Read-only file system``. ``HOME=/tmp`` is
benign and writable on every Linux/macOS container image we target.
"""

from __future__ import annotations

import os

os.environ.setdefault("HOME", "/tmp")

import uvicorn  # noqa: E402

from app import app  # noqa: E402


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
