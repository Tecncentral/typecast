"""Pure-read CoStar property_id/model_id join validator backed by lazy DuckDB."""

from __future__ import annotations

from pathlib import Path
from typing import Any

MAX_PROPERTY_MODEL_ROWS = 100_000
PROPERTY_MODELS_QUERY = "SELECT property_id, model_id FROM read_parquet(?)"


def _norm_id(raw: Any) -> str | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, str):
        cleaned = raw.strip()
        return cleaned if cleaned else None
    return None


def load_property_model_pairs(path: Path) -> set[tuple[str, str]] | None:
    """Load verified (property_id, model_id) pairs from Parquet; return None if unavailable/corrupt."""
    target = Path(path)
    if not target.is_file():
        return None
    try:
        import duckdb  # type: ignore
    except ImportError:
        return None

    con = None
    try:
        con = duckdb.connect(database=":memory:")
        rows = con.execute(PROPERTY_MODELS_QUERY, [str(target)]).fetchmany(MAX_PROPERTY_MODEL_ROWS + 1)
        if len(rows) > MAX_PROPERTY_MODEL_ROWS:
            return None
        pairs: set[tuple[str, str]] = set()
        for row in rows:
            if not isinstance(row, tuple) or len(row) != 2:
                return None
            pid = _norm_id(row[0])
            mid = _norm_id(row[1])
            if pid is None or mid is None:
                return None
            pairs.add((pid, mid))
        return pairs
    except Exception:  # noqa: BLE001
        return None
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:  # noqa: BLE001
                pass
