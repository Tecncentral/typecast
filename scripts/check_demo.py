"""Verify private demo scenes, source honesty, refinement and local drafts live."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_live import check, require


def validate_evidence(result: dict) -> None:
    for pick in result["picks"]:
        prop, logistics, fit = pick["property"], pick["logistics"], pick["shot_fit"]
        require(bool(pick["shots"]), "Demo pick has no real interior camera view.")
        require(all(shot["property_id"] == prop["property_id"] for shot in pick["shots"]), "Demo property/shot join mismatch.")
        require({e["source"] for e in pick["evidence"]} == {"costar", "matterport", "vexcel"}, "Demo pick is missing one of its three evidence sources.")
        require(prop.get("availability_status") == "available", "Demo pick has no verified marketed lease availability.")
        require(logistics.get("parking_status") in {"estimated", "measured"}, "Demo pick has unknown parking.")
        require(logistics.get("car_spaces") is not None, "Demo pick has unknown parking capacity.")
        for value, status in (("walk_m", "walk_status"), ("car_spaces", "parking_status")):
            require(logistics.get(value) is not None or logistics.get(status) == "unknown", "Missing source value has a misleading evidence status.")
        require(all(e["status"] in {"measured", "estimated", "unknown"} for e in pick["evidence"]), "Invalid evidence status.")
        if any(s.get("depth_m") is None or s.get("ceiling_m") is None for s in pick["shots"][:1]):
            require(fit["status"] == "unknown" and not fit["fits"], "Missing geometry was promoted to fit.")
        notes = " ".join(pick["skeptic_notes"]).lower()
        caveats = ["permission" in notes or "access" in notes]
        if fit["status"] == "unknown":
            caveats.append("measure" in notes or "unknown" in notes)
        if logistics.get("walk_m") is None:
            caveats.append("walk" in notes and "unknown" in notes)
        if logistics.get("noise_flags"):
            caveats.append("noise" in notes)
        require(any(caveats), "Skeptic does not cite an actual source limitation.")


def approve(client: httpx.Client, thread: str) -> None:
    response = client.post("/approve", json={"thread_id": thread, "pick_rank": 1, "decision": "yes"})
    response.raise_for_status()
    result = response.json()
    require(result.get("status") == "draft_saved" and result.get("sent") is False, "Approval did not save a local unsent draft.")
    draft = ROOT / "cache/outbox" / f"{thread}-1.md"
    require(draft.is_file() and draft.stat().st_size > 0, "Approval draft was not persisted locally.")


def follow_up(base: str, original: dict, output: Path) -> dict:
    thread = original["thread_id"]
    before = json.loads((ROOT / "cache/threads" / thread / "candidates.json").read_text())
    with httpx.Client(base_url=base, timeout=180) as client:
        # Exercise the original engine approval before refine switches to fixed.
        approve(client, thread)
        started = perf_counter()
        response = client.post("/refine", json={"thread_id": thread, "message": "Need parking for 5 trucks."})
        response.raise_for_status()
        elapsed = perf_counter() - started
        result = response.json()
        output.write_text(json.dumps(result, indent=2))
        require(result["thread_id"] == thread and result["source_mode"] == "live", "Refine lost its live thread.")
        require(elapsed < 90, "Demo refine exceeded the 90-second acceptance limit.")
        validate_evidence(result)
        require(not ({"search_shots", "search_costar"} & result["timings"].keys()), "Refine performed a fresh search.")
        require(not any(e.get("type") == "tool" and e.get("agent") in {"search_shots", "search_costar"} for e in result["events"]), "Refine emitted a fresh search call.")
        after = json.loads((ROOT / "cache/threads" / thread / "candidates.json").read_text())
        require(len(before) == len(after) and {s["shot_id"] for s in before} == {s["shot_id"] for s in after}, "Refine changed the retrieved candidate pool.")
        req = json.loads((ROOT / "cache/threads" / thread / "requirements.json").read_text())
        require(req["trucks"] == 5, "Refine did not apply five trucks.")
        require(len(result["picks"]) == 3, "Refine did not preserve three picks.")
        for pick in result["picks"]:
            log = pick["logistics"]
            if log.get("parking_area_m2") is not None:
                require(log.get("truck_spaces") is not None and log.get("car_spaces") is not None, "Parking area has no usable allocation.")
                budget = int(log["parking_area_m2"] // 30)
                require(log["truck_spaces"] * 4 + log["car_spaces"] <= budget, "Parking allocation exceeds its single area budget.")
        approve(client, thread)
    old = [(p["property"]["property_id"], p["logistics"]["truck_spaces"], p["logistics"]["car_spaces"]) for p in original["picks"]]
    new = [(p["property"]["property_id"], p["logistics"]["truck_spaces"], p["logistics"]["car_spaces"]) for p in result["picks"]]
    require(old != new, "Five-truck refine did not change ranking or allocation.")
    return {"refine_elapsed_s": round(elapsed, 3), "refine_new_searches": 0,
            "refine_same_candidate_pool": True, "refine_changed_rank_or_allocation": True,
            "original_and_refined_local_drafts": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--engine", choices=("fixed", "deep"), required=True)
    parser.add_argument("--demo", type=Path, default=ROOT / "cache/demo-set.json")
    parser.add_argument("--phase", choices=("baseline", "precompute", "warm"), required=True)
    parser.add_argument("--scene-id", action="append")
    parser.add_argument("--verify-trace", action="store_true")
    parser.add_argument("--skip-follow-up", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    scenes = json.loads(args.demo.read_text())["scenes"]
    if args.scene_id:
        require(set(args.scene_id) <= {scene["id"] for scene in scenes}, "Unknown requested demo scene id.")
        scenes = [scene for scene in scenes if scene["id"] in args.scene_id]
    require(bool(scenes), "No demo scenes selected.")
    attempt = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = ROOT / "cache/demo-checks" / args.phase / args.engine / attempt
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for number, scene in enumerate(scenes, 1):
        output = directory / f"scene-{number}.json"
        row = {"scene_id": scene["id"], "engine": args.engine, "ok": False}
        try:
            row.update(check(args.base_url, args.engine, scene["scene"], output, args.verify_trace))
            original = json.loads(output.with_suffix(".response.json").read_text())
            validate_evidence(original)
            require(row["elapsed_s"] < 90, "Demo scout exceeded the 90-second acceptance limit.")
            if not args.skip_follow_up:
                row.update(follow_up(args.base_url, original, output.with_suffix(".refine.json")))
            row["ok"] = True
        except Exception as error:
            if output.is_file():
                row.update(json.loads(output.read_text()))
            row.update(error_type=type(error).__name__, error=str(error) if type(error) is RuntimeError else "Diagnostic failed; inspect private artifacts.")
        rows.append(row)
        (directory / "summary.json").write_text(json.dumps(rows, indent=2))
        print(json.dumps(row), flush=True)
    return 0 if all(row["ok"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
