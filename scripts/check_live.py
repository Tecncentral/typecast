"""Verify a running live scout with real models; print aggregate diagnostics only.

Run against a local server with TYPECAST_USE_MOCKS=0, model parsing and vision
reranking enabled. Full source responses stay in ignored cache/live-checks/.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from io import BytesIO
import json
import os
from pathlib import Path
import re
from time import perf_counter
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENE = ("INT. LOS ANGELES APARTMENT, DAY. Bright living room with windows, "
                 "a kitchen and neutral walls for an intimate conversation scene. "
                 "Parking for 1 truck and 3 crew cars. No required construction era.")


def require(condition: bool, message: str):
    if not condition:
        raise RuntimeError(message)


def check(base: str, engine: str, scene: str, output: Path, verify_trace: bool) -> dict:
    output = output.resolve()
    require(output.is_relative_to((ROOT / "cache").resolve()), "Diagnostic output must remain in private cache.")
    with httpx.Client(base_url=base, timeout=180, follow_redirects=False) as client:
        config_response = client.get("/config")
        config_response.raise_for_status()
        config = config_response.json()
        require(config["mode"] == "live" and config["engine"] == engine, "Server mode/engine differs from requested live check.")
        started = perf_counter()
        response = client.post("/scout", json={"scene": scene})
        response.raise_for_status()
        elapsed = perf_counter() - started
        result = response.json()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.with_suffix(".response.json").write_text(json.dumps(result, indent=2))
        require(result["source_mode"] == "live" and result["engine"] == engine, "Live run used mocks or fell back to another engine.")
        require(len(result["picks"]) == 3, "Live run did not return three source-backed picks.")
        thread = result["thread_id"]
        require(bool(re.fullmatch(r"[a-z0-9-]{4,40}", thread)), "Unexpected thread identifier.")
        requirements = json.loads((ROOT / "cache/threads" / thread / "requirements.json").read_text())
        require(requirements["parsed_with_model"], "Scene parser used its non-model fallback.")
        vision = [event["text"] for event in result["events"]
                  if event["type"] == "rerank" and event["text"].startswith("Vision rerank:")]
        require(bool(vision), "No completed vision rerank event.")
        match = re.search(r"Vision rerank: (\d+) of (\d+) views scored \((\d+) cached\); (\d+) failures", vision[-1])
        require(bool(match) and int(match[1]) > 0, "Vision reranking did not score any real views.")
        source_counts = {name: 0 for name in ("costar", "matterport", "vexcel")}
        frame_count, aerial_count, unknown_fit = 0, 0, 0

        def image(path: str):
            require(path.lstrip("/").startswith("cache/"), "Live pick references an image outside private cache.")
            image_response = client.get("/" + path.lstrip("/"))
            image_response.raise_for_status()
            with Image.open(BytesIO(image_response.content)) as decoded:
                decoded.verify()

        for pick in result["picks"]:
            evidence = {entry["source"] for entry in pick["evidence"]}
            require(evidence == set(source_counts), "Pick is missing one of its three evidence sources.")
            for name in evidence:
                source_counts[name] += 1
            require(bool(pick["skeptic_notes"]) and pick["skeptic_notes"] != ["No objection."], "Missing source-grounded skeptic caveat.")
            for shot in pick["shots"]:
                require(shot["property_id"] == pick["property"]["property_id"], "Property/shot join mismatch.")
                image(shot["image_path"])
                frame_count += 1
            aerial = pick["logistics"].get("aerial_image_path")
            require(bool(aerial), "Pick is missing its real cached aerial image.")
            image(aerial)
            aerial_count += 1
            unknown_fit += pick["shot_fit"]["status"] == "unknown"

    trace_verified, spans = False, 0
    if verify_trace:
        from langsmith import Client
        require(bool(result.get("trace_url")), "No verified LangSmith trace was returned.")
        run_id = urlparse(result["trace_url"]).path.rstrip("/").split("/")[-1]
        with closing(Client(api_key=os.environ["LANGSMITH_API_KEY"], timeout_ms=8000)) as client:
            run = client.read_run(run_id, load_child_runs=True)
            require(run.end_time is not None and run.parent_run_id is None, "Trace root is incomplete.")
            stack, all_spans = [run], []
            while stack:
                span = stack.pop()
                all_spans.append(span)
                stack.extend(span.child_runs or [])
            require(all(not span.inputs and not span.outputs for span in all_spans), "Trace contains unredacted payloads.")
            require(client.get_run_url(run=run, project_name=os.getenv("LANGSMITH_PROJECT", "typecast")) == result["trace_url"], "Trace URL verification failed.")
            trace_verified, spans = True, len(all_spans)
    summary = {"engine": engine, "source_mode": "live", "picks": 3,
               "elapsed_s": round(elapsed, 3), "model_parse": True,
               "vision_scored": int(match[1]), "vision_cached": int(match[3]),
               "vision_failures": int(match[4]), "frames_http_verified": frame_count,
               "aerials_http_verified": aerial_count, "source_evidence_counts": source_counts,
               "unknown_shot_fits": unknown_fit, "trace_verified": trace_verified,
               "trace_spans": spans, "trace_url": result.get("trace_url"), "timings": result["timings"]}
    output.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--engine", required=True, choices=["fixed", "deep"])
    parser.add_argument("--scene", default=DEFAULT_SCENE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-trace", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    output = args.output or ROOT / "cache/live-checks" / f"{args.engine}.json"
    try:
        print(json.dumps(check(args.base_url, args.engine, args.scene, output, args.verify_trace), indent=2))
        return 0
    except Exception as error:
        print(json.dumps({"ok": False, "error_type": type(error).__name__,
                          "detail": str(error) if type(error) is RuntimeError else "Live diagnostic failed; inspect private server/cache evidence."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
