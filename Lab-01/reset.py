"""Reset the lab's runtime state — restore mocks/data/ from seeds, clear the
ledger, drop any non-seeded customer memory.

Run this between demos / rehearsals to get back to the canonical starting
state:

    python reset.py

What it touches:

- mocks/data/customers.json   ← copied from mocks/seeds/customers.json
- mocks/data/orders.json      ← copied from mocks/seeds/orders.json
- mocks/data/ledger.json      ← truncated to []
- memory/customer_*.md        ← deleted, EXCEPT memory/customer_cust_002.md
                                (Bob's seeded memory, committed to git)

If Bob's memory file got modified by `compact_memory` during a demo,
restore it via:

    git restore memory/customer_cust_002.md

(reset.py doesn't overwrite that file because it's the canonical seed and
we don't want to keep two copies of the same content in the repo.)
"""
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "mocks" / "data"
SEEDS_DIR = ROOT / "mocks" / "seeds"
MEMORY_DIR = ROOT / "memory"

# Bob's memory is the one seeded file we keep — committed to git.
KEEP_MEMORY_FILES = {"customer_cust_002.md"}


def reset_mocks() -> list[str]:
    DATA_DIR.mkdir(exist_ok=True)
    touched = []
    for seed in SEEDS_DIR.glob("*.json"):
        target = DATA_DIR / seed.name
        target.write_text(seed.read_text())
        touched.append(str(target.relative_to(ROOT)))
    # Always reset the ledger to empty
    ledger = DATA_DIR / "ledger.json"
    ledger.write_text("[]\n")
    touched.append(str(ledger.relative_to(ROOT)))
    return touched


def reset_memory() -> list[str]:
    if not MEMORY_DIR.exists():
        return []
    removed = []
    for f in MEMORY_DIR.glob("customer_*.md"):
        if f.name in KEEP_MEMORY_FILES:
            continue
        f.unlink()
        removed.append(str(f.relative_to(ROOT)))
    return removed


def main() -> None:
    print("Resetting lab state…\n")

    touched = reset_mocks()
    for path in touched:
        print(f"  ✓ {path}")

    removed = reset_memory()
    for path in removed:
        print(f"  ✗ removed {path}")

    print("\nDone.")
    print("If memory/customer_cust_002.md was modified by `compact_memory`,")
    print("restore it with: git restore memory/customer_cust_002.md")


if __name__ == "__main__":
    main()
