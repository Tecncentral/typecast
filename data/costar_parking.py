"""CoStar's recorded parking spaces, extracted once from the private sponsor kit.

``python -m data.costar_parking`` reads ``commercial-property.jsonl`` and writes
``cache/costar-parking.json``: ``{property_id: {"Surface": 73, "Covered": 129}}``
for joined properties only. Request-time code reads that small file and never
opens the kit. Like every derived CoStar record, the output stays in ignored cache/.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import tempfile
from functools import lru_cache

ROOT = pathlib.Path(__file__).resolve().parents[1]
KIT_ROOT = ROOT / "cache/costar-hackathon-kit"
JOIN_PATH = ROOT / "cache/join.parquet"
PARKING_PATH = ROOT / "cache/costar-parking.json"
_PROPERTY_ID = re.compile(r"[0-9]{1,12}")


def _label(name: str) -> str:
    """``SurfaceTandem`` -> ``Surface tandem``."""
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", name).lower()
    return words[:1].upper() + words[1:]


def recorded_spaces(record: dict, parking_types: dict[str, str]) -> dict[str, int]:
    """Sum ``parking[].totalSpaces`` by labelled type; unknown types and counts are skipped."""
    spaces: dict[str, int] = {}
    for entry in record.get("parking") or []:
        if not isinstance(entry, dict):
            continue
        total = entry.get("totalSpaces")
        name = parking_types.get(str(entry.get("parkingType")))
        if type(total) is not int or total < 0 or not name or name == "Unknown":
            continue
        label = _label(name)
        spaces[label] = spaces.get(label, 0) + total
    return spaces


def _joined_ids(join_path: pathlib.Path) -> set[str]:
    import duckdb

    with duckdb.connect(":memory:") as connection:
        rows = connection.execute("SELECT DISTINCT property_id FROM read_parquet(?)", [str(join_path)]).fetchall()
    return {str(row[0]) for row in rows}


def build(kit_root: pathlib.Path = KIT_ROOT, output: pathlib.Path = PARKING_PATH,
          join_path: pathlib.Path = JOIN_PATH) -> dict:
    enums = json.loads((kit_root / "schemas/enums.json").read_text(encoding="utf-8"))
    parking_types = {str(k): str(v) for k, v in enums["ParkingType"].items()}
    joined = _joined_ids(join_path)
    out: dict[str, dict[str, int]] = {}
    with open(kit_root / "data/commercial-property.jsonl", encoding="utf-8") as source:
        for line in source:
            if '"totalSpaces"' not in line:
                continue
            record = json.loads(line)
            property_id = str(record.get("id"))
            if property_id in joined:
                spaces = recorded_spaces(record, parking_types)
                if spaces:
                    out[property_id] = spaces
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=output.parent, prefix=".costar-parking-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(out, stream, sort_keys=True)
        os.chmod(temporary, 0o600)
        os.replace(temporary, output)
    except BaseException:
        pathlib.Path(temporary).unlink(missing_ok=True)
        raise
    recorded_parking.cache_clear()
    return {"joined_properties": len(joined), "with_recorded_spaces": len(out)}


@lru_cache(maxsize=1)
def recorded_parking(path: pathlib.Path = PARKING_PATH) -> dict[str, dict[str, int]]:
    """The extracted records, or {} when the optional file is absent or malformed."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {pid: {str(k): v for k, v in spaces.items() if type(v) is int and v >= 0}
            for pid, spaces in data.items()
            if isinstance(pid, str) and _PROPERTY_ID.fullmatch(pid) and isinstance(spaces, dict)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kit", type=pathlib.Path, default=KIT_ROOT)
    parser.add_argument("--output", type=pathlib.Path, default=PARKING_PATH)
    args = parser.parse_args()
    print(json.dumps(build(args.kit, args.output)))
