"""Minimal stdlib placeholder for Lab-03 catalog dummy agents.

The Lab-03 catalog includes a few dummy agents (Sales Discovery, IT Helpdesk,
Doc Q&A, Code Review) that exist purely for catalog variety. They are not
expected to serve real traffic — they just need to *build* cleanly and bind
to their declared port so OpenChoreo marks them healthy in the AM console.

Implementation uses ``http.server`` from the stdlib so the build does no real
pip work: requirements.txt is empty, the runtime layer is just CPython +
this 60-line file. Build finishes in well under a minute on a warm node.

Contract (loose — these never get traffic):

- ``GET  /health``  → ``{"status": "ok", "kind": "mock-placeholder"}``
- ``POST /chat``    → ``{"response": <placeholder text>, "session_id": <echoed>}``
- ``POST /*``       → same placeholder, so a custom-api dummy with a
                     different basePath still gets a 200.

Port is read from ``$PORT`` (defaults to 8000).
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PLACEHOLDER_REPLY = (
    "This agent is a Lab-03 catalog placeholder and does not implement real "
    "behavior. It exists so the agent record and its build show up cleanly in "
    "the AM console."
)


class _Handler(BaseHTTPRequestHandler):
    def _read_body_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            return {}

    def _reply(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/health"):
            self._reply(200, {"status": "ok", "kind": "mock-placeholder"})
        else:
            self._reply(200, {"response": PLACEHOLDER_REPLY})

    def do_POST(self) -> None:  # noqa: N802
        body = self._read_body_json()
        self._reply(
            200,
            {
                "response": PLACEHOLDER_REPLY,
                "session_id": body.get("session_id"),
            },
        )

    def log_message(self, *_args, **_kwargs) -> None:  # silence per-request stderr noise
        return


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    ThreadingHTTPServer(("0.0.0.0", port), _Handler).serve_forever()


if __name__ == "__main__":
    main()
