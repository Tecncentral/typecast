"""Strike real scan points.

  python -m strike --demo [--api http://localhost:8010] [--dry-run]   # Director demo + stage top picks
  python -m strike --shot <shot_id> [--shot ...] [--force]

Each scan point is processed once (skipped when strike.json exists, unless --force). Output is
aggregate only: no keys, images or source identifiers are printed.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import requests
from dotenv import load_dotenv

from strike.core import ROOT, OpenAIClient, StrikeError, scan_point_dir, strike_scan_point


def director_shots(api: str) -> list[str]:
    js = (ROOT / "index" / "director.js").read_text(encoding="utf-8")
    block = re.search(r"const DEMO = \[(.*?)\]\.join", js, re.S)
    lines = re.findall(r"'([^']+)'", block.group(1)) if block else []
    scenes = []
    for i, line in enumerate(lines):
        heading, _, description = line.partition("|")
        scenes.append({"id": f"s{i + 1}", "heading": heading.strip(), "description": description.strip() or heading.strip()})
    if not scenes:
        return []
    plan = requests.post(f"{api}/api/production/plan", json={"scenes": scenes, "max_locations": 3, "forbidden_property_ids": [],
                                                            "require_available": False, "trucks": 0, "cars": 0}, timeout=300).json()
    plans = plan.get("plans") or []
    return [a["shot_id"] for a in (plans[0].get("assignments") or [])] if plans else []


def stage_pick_shots(limit_per_scene: int = 3) -> list[str]:
    shots = []
    for engine in ("deep", "fixed"):
        root = ROOT / "cache" / "demo-checks" / "warm" / engine
        runs = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
        for f in sorted(runs[-1].glob("scene-*.response.json")) if runs else []:
            data = json.loads(f.read_text(encoding="utf-8"))
            response = data.get("response") if isinstance(data.get("response"), dict) else data
            for pick in (response.get("picks") or [])[:limit_per_scene]:
                for shot in (pick.get("shots") or [])[:1]:
                    if shot.get("shot_id"):
                        shots.append(shot["shot_id"])
    return shots


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--shot", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-scan-points", type=int, default=14)
    args = parser.parse_args(argv)
    shots = list(args.shot)
    if args.demo:
        shots += director_shots(args.api) + stage_pick_shots()
    if not shots:
        parser.error("give --demo or --shot")
    sweeps, seen = [], set()
    for shot_id in shots:
        sweep = requests.get(f"{args.api}/api/sweep/{shot_id}", timeout=60)
        if not sweep.ok:
            print(f"skipped a shot: sweep HTTP {sweep.status_code}")
            continue
        sweep = sweep.json()
        key = (sweep["model_id"], sweep["sweep_id"])
        if key not in seen:
            seen.add(key)
            sweeps.append(sweep)
    sweeps = sweeps[: args.max_scan_points]
    todo = [s for s in sweeps if args.force or not (scan_point_dir(s["model_id"], s["sweep_id"]) / "strike.json").is_file()]
    print(f"{len(sweeps)} scan points, {len(todo)} to strike ({len(todo) * 4} faces at most)")
    if args.dry_run:
        return 0
    client = OpenAIClient()
    totals = {}
    for n, sweep in enumerate(todo, 1):
        print(f"scan point {n}/{len(todo)}")
        try:
            record = strike_scan_point(sweep, client, log=lambda m: print("  " + m), force=args.force)
        except StrikeError as error:
            print(f"  FAILED: {error}")
            if "429" in str(error) or "insufficient" in str(error).lower():
                break
            continue
        for face in record["faces"]:
            totals[face["status"]] = totals.get(face["status"], 0) + 1
    print("done:", ", ".join(f"{k} {v}" for k, v in sorted(totals.items())) or "nothing new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
