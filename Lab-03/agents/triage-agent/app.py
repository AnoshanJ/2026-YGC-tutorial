"""FastAPI entrypoint for the Order Triage Crew.

Exposes ``POST /triage`` taking an email payload and returning the verifier's
verdict plus the final drafted response. ``GET /health`` for liveness.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from crew import run_triage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("triage-agent")


class TriageRequest(BaseModel):
    # JSON key "from" is a Python keyword, so use an alias
    from_: str | None = Field(default=None, alias="from")
    subject: str | None = None
    body: str

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TriageResponse(BaseModel):
    result: Any


app = FastAPI(title="Order Triage Crew", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResponse)
def triage(req: TriageRequest) -> TriageResponse:
    email = {
        "from": req.from_ or "",
        "subject": req.subject or "",
        "body": req.body or "",
    }
    try:
        result = run_triage(email)
    except Exception as exc:  # noqa: BLE001
        log.exception("triage crew failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    payload: Any = result.raw if hasattr(result, "raw") else str(result)
    return TriageResponse(result=payload)
