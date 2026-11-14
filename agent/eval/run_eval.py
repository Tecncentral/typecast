"""Run the scene benchmark in-process; empty labels never become a retrieval score."""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.eval.harness import mock_app


def read_jsonl(path: Path) -> list[dict]:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"{path.name}:{number}: expected an object")
        records.append(record)
    ids = [record.get("id") for record in records]
    if any(not isinstance(identifier, str) or not identifier for identifier in ids):
        raise ValueError(f"{path.name}: each record needs a nonempty id")
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path.name}: duplicate ids")
    return records


def load_inputs(scenes_path: Path, labels_path: Path, split="all"):
    scenes = read_jsonl(scenes_path)
    for scene in scenes:
        if scene.get("split") not in {"test", "tune"} or not isinstance(scene.get("scene"), str) or not scene["scene"].strip():
            raise ValueError(f"{scene['id']}: scene text and test/tune split are required")
    known = {scene["id"] for scene in scenes}
    labels = {label["id"]: label for label in read_jsonl(labels_path)}
    if set(labels) - known:
        raise ValueError("Labels contain scene ids absent from the scene file")
    for identifier, label in labels.items():
        relevant = label.get("relevant_shot_ids")
        if not isinstance(relevant, list) or any(not isinstance(shot, str) or not shot.strip() for shot in relevant):
            raise ValueError(f"{identifier}: relevant_shot_ids must be a list of nonempty strings")
        if relevant and (not isinstance(label.get("labeler"), str) or not label["labeler"].strip()):
            raise ValueError(f"{identifier}: labeled scenes require a labeler")
    selected = [scene for scene in scenes if split == "all" or scene["split"] == split]
    if not selected:
        raise ValueError("No scenes selected")
    return selected, labels


def evaluate_app(app, scenes: list[dict], labels: dict) -> list[dict]:
    from fastapi.testclient import TestClient
    from agent import state
    from contracts.schemas import ScoutResponse

    rows = []
    city_pools = {}
    with TestClient(app) as client:
        for scene in scenes:
            row = {"id": scene["id"], "split": scene["split"], "recall_at_10": None,
                   "relevant_count": len(set(labels.get(scene["id"], {}).get("relevant_shot_ids", []))),
                   "retrieved_count": 0, "engine": "unknown", "source_mode": "unknown", "error": None}
            if "evaluation" in scene:
                row.update(pool_scope=scene["evaluation"]["pool_scope"], requested_city=None,
                           reviewed_count=len(labels.get(scene["id"], {}).get("reviewed_shot_ids", [])),
                           eligible_relevant_count=None)
            started = perf_counter()
            response = client.post("/scout", json={"scene": scene["scene"]})
            row["latency_ms"] = (perf_counter() - started) * 1000
            if response.status_code != 200:
                row["error"] = f"HTTP {response.status_code}"
            else:
                run = ScoutResponse.model_validate(response.json())
                row.update(engine=run.engine, source_mode=run.source_mode)
                # The UI picks retain only a few views. Retrieval recall uses the full
                # ranked candidate pool persisted by the pipeline before card selection.
                candidates = state.load(run.thread_id, "candidates")
                top10 = [shot.shot_id if hasattr(shot, "shot_id") else shot["shot_id"]
                         for shot in candidates[:10]]
                relevant = set(labels.get(scene["id"], {}).get("relevant_shot_ids", []))
                row["retrieved_count"] = len(top10)
                if relevant:
                    row["recall_at_10"] = len(set(top10) & relevant) / len(relevant)
                if "evaluation" in scene:
                    # Diagnose the global-label/city-filter mismatch without changing
                    # the human text or the metric's full pooled denominator.
                    from data.costar_tools import search_costar
                    from index.search import get_active_index
                    requirements = state.load(run.thread_id, "requirements")
                    city = requirements.city if hasattr(requirements, "city") else requirements["city"]
                    row["requested_city"] = city
                    if city not in city_pools:
                        city_pools[city] = {p.property_id for p in search_costar(city=city, available_only=False)}
                    catalog = get_active_index()
                    row["eligible_relevant_count"] = sum(
                        catalog.get_shot(sid).property_id in city_pools[city] for sid in relevant)
            rows.append(row)
    return rows


def summarize(rows: list[dict]) -> dict:
    latencies = sorted(row["latency_ms"] for row in rows)
    scored = [row["recall_at_10"] for row in rows if row["recall_at_10"] is not None]
    return {"attempted": len(rows), "succeeded": sum(row["error"] is None for row in rows),
            "scored": len(scored), "unlabeled": sum(row["relevant_count"] == 0 for row in rows),
            "recall_at_10": sum(scored) / len(scored) if scored else None,
            "p50_ms": median(latencies), "p95_ms": latencies[math.ceil(0.95 * len(latencies)) - 1],
            "engines": sorted({row["engine"] for row in rows}),
            "source_modes": sorted({row["source_mode"] for row in rows})}


def _score(value):
    return "N/A" if value is None else f"{value:.4f}"


def render_report(rows, *, mock: bool, labels_path: Path, date: str) -> str:
    summary = summarize(rows)
    pooled = any("pool_scope" in row for row in rows)
    marker = "mock run: not a result\n\n" if mock else ""
    lines = [marker + "# Retrieval evaluation", "", f"Date: {date}", "",
             ("The exact authored visual prompts and human/live judgments come from the frozen blinded lab."
              if pooled else "The scene texts are authored fiction, not source data. No relevance judgments are inferred from mock scores."), "",
             f"Engine(s): {', '.join(summary['engines'])}. Source mode(s): {', '.join(summary['source_modes'])}.", "",
             f"| Split | Attempted | Succeeded | Scored labels | {'Empty judged pools' if pooled else 'Unlabeled'} | Mean recall@10 | p50 ms | p95 ms |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for split in ("all", "test", "tune"):
        selected = rows if split == "all" else [row for row in rows if row["split"] == split]
        if not selected:
            continue
        values = summarize(selected)
        lines.append(f"| {split} | {values['attempted']} | {values['succeeded']} | {values['scored']} | {values['unlabeled']} | "
                     f"{_score(values['recall_at_10'])} | {values['p50_ms']:.2f} | {values['p95_ms']:.2f} |")
    lines.extend(["", "Recall@10 is the fraction of hand-labeled relevant shot ids found in the first ten cached ranked retrieval candidates, averaged over scored scenes. "
                  "Empty or absent labels are skipped, never counted as zero recall. Failed labeled requests are reported as failures and are not scored.", "",
                  "Latency is wall-clock time for the in-process POST /scout request, including response validation and serialization but excluding app startup. "
                  "There is no warmup. p50 is the median; p95 is the nearest-rank 95th percentile. These are local measurements, not deployed network latency.", "",
                  "| Scene | Split | Top-k count | Recall@10 | Latency ms | Engine | Source mode | Status |",
                  "|---|---|---:|---:|---:|---|---|---|"])
    for row in rows:
        status = row["error"] or ("scored" if row["recall_at_10"] is not None else
                                  "reviewed; no relevant in pool" if pooled else "unlabeled; skipped")
        lines.append(f"| {row['id']} | {row['split']} | {row['retrieved_count']} | {_score(row['recall_at_10'])} | "
                     f"{row['latency_ms']:.2f} | {row['engine']} | {row['source_mode']} | {status} |")
    if pooled:
        lines.extend(["", "These are judgments of a frozen global top-40 cosine pool, not exhaustive catalog relevance. "
                      "The /scout pipeline filters retrieval by the parsed city (Los Angeles by default) and may rerank candidates. "
                      "This measures pooled pipeline recall@10, not global CLIP retrieval accuracy. Relevant views outside the city pool remain in the denominator; "
                      "the diagnostic below shows this eligibility mismatch. Empty selections are complete reviews with no relevant views in the judged pool and are skipped for recall.", "",
                      "| Scene | Parsed city | Reviewed pool | Relevant gold | City-eligible gold |",
                      "|---|---|---:|---:|---:|"])
        for row in rows:
            if "pool_scope" in row:
                eligible = row["eligible_relevant_count"]
                lines.append(f"| {row['id']} | {row['requested_city'] or 'N/A'} | {row['reviewed_count']} | "
                             f"{row['relevant_count']} | {'N/A' if eligible is None else eligible} |")
    label_name = str(labels_path.relative_to(ROOT)) if labels_path.is_relative_to(ROOT) else labels_path.name
    if pooled:
        lines.extend(["", f"Labels file: `{label_name}`. Reviewer provenance, reviewed pools and frozen index fingerprints remain in ignored private JSONL files.", "",
                      "Keep test judgments frozen and use only tune scenes for development. Reproduce with the same exported `--scenes` and `--labels`, "
                      "`--mode live --split test`, and the frozen `--index-dir`. Index changes or stale/AI/mock reviews are rejected.", ""])
        return "\n".join(lines)
    lines.extend(["", f"Labels file: `{label_name}`. The template intentionally has 20 empty label sets.", "",
                  "Before tuning, inspect the real shot corpus and hand-label relevant shots for all 20 scenes, recording the labeler. "
                  "Keep licensed shot ids and judgments in an ignored private file such as `cache/eval/labels.jsonl`; do not fill the public template. "
                  "Freeze the 15 test scenes and their labels. Use only the five tune scenes for development, then report test recall separately.", "",
                  "Reproduce the offline harness: `.venv/bin/python agent/eval/run_eval.py --mode mock`. "
                  "Once authorized real data and labels exist, use `--mode live --labels cache/eval/labels.jsonl --split test`. "
                  "Mock mode blanks provider keys, disables parsing/vision models and tracing, blocks sockets and isolates thread/draft files in a temporary directory.", "",
                  "The report contains aggregate metrics and authored scene ids only; retrieved shot ids are not published.", ""])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenes", type=Path, default=Path(__file__).with_name("scenes.jsonl"))
    parser.add_argument("--labels", type=Path, default=Path(__file__).with_name("labels.template.jsonl"))
    parser.add_argument("--split", choices=("all", "test", "tune"), default="all")
    parser.add_argument("--mode", choices=("mock", "live"), default="mock")
    parser.add_argument("--engine", choices=("fixed", "deep"), default="fixed")
    parser.add_argument("--index-dir", type=Path, help="live frozen index root or generation; defaults to TYPECAST_INDEX_DIR/cache/shot-index")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/team/eval.md")
    args = parser.parse_args(argv)
    if args.mode == "mock" and args.engine != "fixed":
        parser.error("mock evaluation uses the fixed engine with all model calls disabled")
    scenes, labels = load_inputs(args.scenes.resolve(), args.labels.resolve(), args.split)
    bridged = any("evaluation" in scene for scene in scenes)
    pinned_index = None
    if bridged and args.mode != "live":
        parser.error("Frozen human/live lab exports require --mode live")
    if args.mode == "mock":
        context = mock_app()
    else:
        # Configure adapters before importing app; live mode never substitutes fixtures.
        os.environ.update(TYPECAST_USE_MOCKS="0", TYPECAST_ENGINE=args.engine)
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
        if bridged:
            from agent.eval.label_bridge import validate_live_inputs
            try:
                pinned_index = validate_live_inputs(
                    scenes, labels, args.index_dir or Path(os.getenv("TYPECAST_INDEX_DIR", str(ROOT / "cache/shot-index"))))
            except ValueError as exc:
                parser.error(str(exc))
            os.environ["TYPECAST_INDEX_DIR"] = str(pinned_index)
            from index.search import configure_index
            configure_index(cache_dir=pinned_index)
        elif args.index_dir:
            os.environ["TYPECAST_INDEX_DIR"] = str(args.index_dir.resolve())
        from agent.app import app
        context = nullcontext(app)
    with context as app:
        rows = evaluate_app(app, scenes, labels)
    if pinned_index is not None:
        validate_live_inputs(scenes, labels, pinned_index)
    summary = summarize(rows)
    is_mock = args.mode == "mock" or "mock" in summary["source_modes"]
    report = render_report(rows, mock=is_mock, labels_path=args.labels.resolve(),
                           date=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    if is_mock:
        print("mock run: not a result")
    skipped = "reviewed empty pools" if bridged else "unlabeled"
    print(f"Scenes: {summary['attempted']} attempted, {summary['succeeded']} succeeded; "
          f"{summary['scored']} labeled scenes scored, {summary['unlabeled']} {skipped} skipped")
    print(f"recall@10: {_score(summary['recall_at_10'])}")
    print(f"Latency: p50={summary['p50_ms']:.2f} ms, p95={summary['p95_ms']:.2f} ms")
    print(f"Engine: {', '.join(summary['engines'])}; source mode: {', '.join(summary['source_modes'])}")
    print(f"Report: {args.output.resolve()}")
    return 0 if summary["succeeded"] == summary["attempted"] and summary["source_modes"] == [args.mode] else 1


if __name__ == "__main__":
    raise SystemExit(main())
