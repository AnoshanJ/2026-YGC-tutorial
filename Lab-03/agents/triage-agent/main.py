"""Programmatic entrypoint for the Order Triage Crew.

Invoked via the ``start.sh`` wrapper at deploy time so that ``HOME`` and
``CREWAI_STORAGE_DIR`` are exported into the process environment *before*
Python starts. This is required because AM's amp-instrumentation imports
CrewAI from ``sitecustomize``, which runs before any code in this module —
see ``start.sh`` for the full explanation.
"""

from __future__ import annotations

import uvicorn

from app import app


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
