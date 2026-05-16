#!/usr/bin/env bash
# Wrapper entrypoint for the triage-agent.
#
# Why a wrapper instead of just `python main.py`:
#
# CrewAI evaluates `DEFAULT_STORAGE_PATH = db_storage_path()` as a module-level
# constant in crewai.rag.chromadb.constants — meaning it runs the moment
# anything in the `crewai` package is imported. That call ends up calling
# `path.mkdir(parents=True, exist_ok=True)` for a directory derived from the
# user's data dir (defaults to ~/.local/share/CrewAI on Linux). On a Google
# Buildpacks container, HOME is unset, so `~` resolves to `/nonexistent` and
# the mkdir fails with errno 30 (read-only file system) — the agent crashes
# at import time before main.py ever runs.
#
# AM's auto-instrumentation (amp-instrumentation, loaded via sitecustomize)
# imports `crewai` to set up the CrewAI OTEL instrumentor — and that happens
# BEFORE main.py executes. So setting these env vars from Python (e.g.
# os.environ.setdefault in main.py) is too late.
#
# The fix: set the env vars in the process environment before Python starts.
# This wrapper does exactly that. The values are short-circuits to writable
# locations under /tmp; CrewAI honors CREWAI_STORAGE_DIR as a documented
# escape hatch for exactly this scenario.
#
# Data stored in /tmp is ephemeral — fine for our use because we don't use
# CrewAI's Memory or Knowledge features (no Crew(memory=True), no Knowledge
# sources). The storage dir just satisfies the import-time mkdir; nothing
# is ever written to it at runtime.

set -e

export HOME="${HOME:-/tmp}"
export CREWAI_STORAGE_DIR="${CREWAI_STORAGE_DIR:-/tmp/.crewai}"

exec python main.py
