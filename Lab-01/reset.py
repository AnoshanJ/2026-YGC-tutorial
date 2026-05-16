"""Reset the lab's runtime state — restore mocks/data/ from seeds (including
the audit ledger), drop any non-seeded customer memory, wipe Strands session
storage.

Run this between demos / rehearsals to get back to the canonical starting
state:

    python reset.py

What it touches:

- mocks/data/customers.json          ← copied from mocks/seeds/customers.json
- mocks/data/orders.json             ← copied from mocks/seeds/orders.json
- mocks/data/ledger.json             ← copied from mocks/seeds/ledger.json
                                       (carries Bob's prior refund_0001 +
                                        TICKET-1001 used by §3's episodic
                                        memory demo)
- memory/episodic/customer_*.md      ← deleted, EXCEPT customer_cust_002.md
                                       (Bob's seeded memory, committed to git)
- memory/sessions/                   ← contents removed (Strands FileSessionManager
                                       state per customer — chat transcripts for
                                       §3's conversation memory layer)

If Bob's memory file got modified by `compact_memory` during a demo,
restore it via:

    git restore memory/episodic/customer_cust_002.md

(reset.py doesn't overwrite that file because it's the canonical seed and
we don't want to keep two copies of the same content in the repo.)
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "mocks" / "data"
SEEDS_DIR = ROOT / "mocks" / "seeds"
EPISODIC_DIR = ROOT / "memory" / "episodic"
SESSIONS_DIR = ROOT / "memory" / "sessions"

# Bob's memory is the one seeded file we keep — committed to git.
KEEP_MEMORY_FILES = {"customer_cust_002.md"}


def reset_mocks() -> list[str]:
    """Copy every seed JSON into mocks/data/. Includes ledger.json so the
    pre-existing TICKET-1001 + refund_0001 are present at demo start."""
    DATA_DIR.mkdir(exist_ok=True)
    touched = []
    for seed in SEEDS_DIR.glob("*.json"):
        target = DATA_DIR / seed.name
        target.write_text(seed.read_text())
        touched.append(str(target.relative_to(ROOT)))
    return touched


def reset_memory() -> list[str]:
    """Remove non-seeded customer memory files under memory/episodic/."""
    if not EPISODIC_DIR.exists():
        return []
    removed = []
    for f in EPISODIC_DIR.glob("customer_*.md"):
        if f.name in KEEP_MEMORY_FILES:
            continue
        f.unlink()
        removed.append(str(f.relative_to(ROOT)))
    return removed


def reset_sessions() -> list[str]:
    """Wipe FileSessionManager state. Each customer's chat history lives in
    memory/sessions/session_<customer_id>/."""
    if not SESSIONS_DIR.exists():
        return []
    removed = []
    for entry in SESSIONS_DIR.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
        removed.append(str(entry.relative_to(ROOT)))
    return removed


def main() -> None:
    print("Resetting lab state…\n")

    touched = reset_mocks()
    for path in touched:
        print(f"  ✓ {path}")

    removed = reset_memory()
    for path in removed:
        print(f"  ✗ removed {path}")

    sessions_removed = reset_sessions()
    for path in sessions_removed:
        print(f"  ✗ removed {path}")

    print("\nDone.")
    print("If memory/episodic/customer_cust_002.md was modified by `compact_memory`,")
    print("restore it with: git restore memory/episodic/customer_cust_002.md")


if __name__ == "__main__":
    main()
