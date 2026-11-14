"""Measure real-model deep runs over fixtures; output timing metadata only.

Uses the configured paid provider. Model parsing and vision reranking are
disabled to isolate director/delegate latency consistently across revisions.
Use --tracing to include real trace upload and verified run-link retrieval.
Pass --checkout to benchmark an unchanged worktree with the same environment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from statistics import median
import subprocess
import sys
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SCENE = ("INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling, "
         "windows on one wall. Parking for 3 trucks and 30 crew cars.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=ROOT)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--director-effort", default="medium")
    parser.add_argument("--scout-effort", default="low")
    parser.add_argument("--tracing", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")

    from dotenv import load_dotenv
    load_dotenv(args.env_file, override=False)
    os.environ.update(TYPECAST_ENGINE="deep", TYPECAST_USE_MOCKS="1",
                      TYPECAST_ENABLE_MODEL_PARSE="0", TYPECAST_ENABLE_VISION_RERANK="0",
                      TYPECAST_REASONING_EFFORT=args.director_effort,
                      TYPECAST_SCOUT_REASONING_EFFORT=args.scout_effort,
                      LANGSMITH_TRACING="true" if args.tracing else "false",
                      LANGCHAIN_TRACING_V2="false")
    if not args.tracing:
        os.environ.update(LANGSMITH_API_KEY="", LANGCHAIN_API_KEY="")
    elif not os.getenv("LANGSMITH_API_KEY", "").strip():
        parser.error("--tracing requires LANGSMITH_API_KEY")
    sys.path.insert(0, str(args.checkout.resolve()))
    from agent import runtime

    if not runtime.deep.is_available():
        print(json.dumps({"error": "Deep model is not configured"}), flush=True)
        return 2
    revision = subprocess.check_output(
        ["git", "-C", str(args.checkout), "rev-parse", "HEAD"], text=True).strip()
    source_hash = hashlib.sha256()
    for path in sorted(list((args.checkout / "agent").glob("*.py")) +
                       list((args.checkout / "agent/prompts").glob("*.md"))):
        source_hash.update(str(path.relative_to(args.checkout)).encode() + b"\0" + path.read_bytes())
    report = {"date_utc": datetime.now(timezone.utc).isoformat(), "revision": revision,
              "agent_source_sha256": source_hash.hexdigest(),
              "model": os.getenv("TYPECAST_LLM_MODEL"), "director_effort": args.director_effort,
              "scout_effort": args.scout_effort, "source_mode": "mock",
              "model_parse": False, "vision_rerank": False, "tracing": args.tracing, "runs": []}
    for number in range(1, args.runs + 1):
        started = perf_counter()
        delegates = {}
        delegate_events = []
        event_count = 0
        first_event_s = None

        def emit(event):
            nonlocal event_count, first_event_s
            event_count += 1
            elapsed = perf_counter() - started
            if first_event_s is None:
                first_event_s = elapsed
            if event.engine == "deep" and event.type in {"subagent_start", "subagent_result"}:
                delegate_events.append({"type": event.type, "agent": event.agent, "elapsed_s": elapsed})
                timing = delegates.setdefault(event.agent, {})
                timing["start_s" if event.type == "subagent_start" else "end_s"] = elapsed
                print(json.dumps({"run": number, "event": event.type,
                                  "agent": event.agent, "elapsed_s": round(elapsed, 3)}), flush=True)
            elif event.type in {"error", "fallback"}:
                print(json.dumps({"run": number, "event": event.type,
                                  "agent": event.agent, "elapsed_s": round(elapsed, 3)}), flush=True)

        ctx = runtime.create_context(f"bench-{uuid4().hex[:16]}", emit=emit)
        row = {"run": number}
        try:
            result = runtime.run_scout(ctx, scene=SCENE)
            row.update(engine=result.engine, picks=len(result.picks),
                       fallback=result.engine != "deep", trace_url=result.trace_url)
        except Exception as error:
            row.update(engine="error", error_kind=type(error).__name__, fallback=False)
        row.update(total_s=perf_counter() - started, first_event_s=first_event_s,
                   event_count=event_count, delegates=delegates, delegate_events=delegate_events)
        for timing in delegates.values():
            if "start_s" in timing and "end_s" in timing and timing["end_s"] >= timing["start_s"]:
                timing["duration_s"] = timing["end_s"] - timing["start_s"]
        report["runs"].append(row)
        print(json.dumps(row), flush=True)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
    successful = [r for r in report["runs"] if r["engine"] == "deep"]
    report["summary"] = {"attempts": args.runs, "deep_successes": len(successful),
        "verified_trace_links": sum(bool(r.get("trace_url")) for r in report["runs"]),
        "p50_all_attempts_s": median(r["total_s"] for r in report["runs"]),
        "p50_deep_success_s": median(r["total_s"] for r in successful) if successful else None,
        "delegate_p50_s": {name: median(durations) for name in
            ("market_scout", "interior_scout", "logistics_scout", "skeptic")
            if (durations := [r["delegates"][name]["duration_s"] for r in report["runs"]
                              if "duration_s" in r["delegates"].get(name, {})])},
        "delegate_completed_samples": {name: sum("duration_s" in r["delegates"].get(name, {})
            for r in report["runs"]) for name in
            ("market_scout", "interior_scout", "logistics_scout", "skeptic")}}
    print(json.dumps({"summary": report["summary"]}), flush=True)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if (len(successful) == args.runs and
                 (not args.tracing or report["summary"]["verified_trace_links"] == args.runs)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
