"""Spending guard for billable Vexcel calls.

check_and_record(endpoint, count) runs before a billable request. It refuses the call if it would
exceed a cap, otherwise it appends one line to the git-ignored ledger cache/vexcel/ledger.jsonl:
{"ts", "endpoint", "count"}. Keys, URLs, parameters and response bodies are never written.

Units: embedding counts records requested, images counts oriented/extract images, elevation counts
dtm and dsm calls together. A call is recorded when it is allowed, not when it succeeds, so a failed
request still counts: billing may happen anyway. A 429 retry is the same call and is not recorded
again. Days are UTC. A corrupt ledger refuses every call rather than guess.

The Vexcel specs state no price, quota or rate limit; they only say embedding/extract and
oriented/query bill per record returned. The billing unit is still unconfirmed; for the hackathon the
team treats access as unmetered (DECISIONS.md), so a demo machine may raise any cap without code
changes: TYPECAST_VEXCEL_<CATEGORY>_<LIMIT>, e.g. TYPECAST_VEXCEL_EMBEDDING_PER_DAY=2000. The ledger
keeps recording either way.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from data.vexcel_client import ProviderError

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "cache" / "vexcel" / "ledger.jsonl"

# Every cap lives here.
CAPS = {
    "embedding": {"per_search": 5, "per_day": 40},
    "images": {"per_day": 60},
    # Not set by the plan: two elevation calls (dtm, dsm) per place for up to 60 images a day.
    "elevation": {"per_day": 120},
}
CATEGORY = {
    "embedding/extract": "embedding",
    "oriented/extract": "images",
    "dtm/elevation": "elevation",
    "dsm/elevation": "elevation",
}


def caps(category: str) -> dict:
    """The caps for a category: CAPS, raised or lowered by positive integer environment overrides."""
    out = dict(CAPS[category])
    for limit in out:
        raw = os.getenv(f"TYPECAST_VEXCEL_{category.upper()}_{limit.upper()}", "").strip()
        if raw.isdigit() and int(raw) > 0:
            out[limit] = int(raw)
    return out


class BudgetExceeded(ProviderError):
    """A billable call was refused before it was sent."""


class LedgerError(ProviderError):
    """The ledger cannot be trusted, so billable calls are refused."""


def _now() -> datetime:
    return datetime.now(UTC)


@contextmanager
def _exclusive():
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.with_name("ledger.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def _used_today(category: str, today: str) -> int:
    if not LEDGER.is_file():
        return 0
    used = 0
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            ts, endpoint, count = row["ts"], row["endpoint"], row["count"]
            if not (
                isinstance(ts, str) and isinstance(endpoint, str) and type(count) is int
            ):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise LedgerError(
                "Vexcel ledger is unreadable; billable calls are refused"
            ) from None
        if ts[:10] == today and CATEGORY.get(endpoint) == category:
            used += count
    return used


def check_and_record(endpoint: str, count: int) -> None:
    category = CATEGORY.get(endpoint)
    if category is None:
        raise ValueError("Unsupported Vexcel endpoint")
    if type(count) is not int or count < 1:
        raise ValueError("count must be a positive whole number")
    limits = caps(category)
    if "per_search" in limits and count > limits["per_search"]:
        raise BudgetExceeded(
            f"Vexcel {category} request of {count} exceeds the per-search cap of {limits['per_search']}"
        )
    now = _now()
    with _exclusive():
        used = _used_today(category, now.date().isoformat())
        if used + count > limits["per_day"]:
            raise BudgetExceeded(
                f"Vexcel {category} would exceed the daily cap of {limits['per_day']} ({used} used today)"
            )
        line = json.dumps(
            {
                "ts": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "endpoint": endpoint,
                "count": count,
            },
            sort_keys=True,
        )
        with LEDGER.open("a", encoding="utf-8") as ledger:
            ledger.write(line + "\n")
            ledger.flush()
            os.fsync(ledger.fileno())
