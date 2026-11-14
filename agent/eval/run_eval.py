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
    with TestClient(app) as client:
        for scene in scenes:
            row = {"id": scene["id"], "split": scene["split"], "recall_at_10": None,
                   "relevant_count": len(set(labels.get(scene["id"], {}).get("relevant_shot_ids", []))),
                   "retrieved_count": 0, "engine": "unknown", "source_mode": "unknown", "error": None}
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
    marker = "mock run: not a result\n\n" if mock else ""
    lines = [marker + "# Retrieval evaluation", "", f"Date: {date}", "",
             "The scene texts are authored fiction, not source data. No relevance judgments are inferred from mock scores.", "",
             f"Engine(s): {', '.join(summary['engines'])}. Source mode(s): {', '.join(summary['source_modes'])}.", "",
             "| Split | Attempted | Succeeded | Scored labels | Unlabeled | Mean recall@10 | p50 ms | p95 ms |",
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
        status = row["error"] or ("scored" if row["recall_at_10"] is not None else "unlabeled; skipped")
        lines.append(f"| {row['id']} | {row['split']} | {row['retrieved_count']} | {_score(row['recall_at_10'])} | "
                     f"{row['latency_ms']:.2f} | {row['engine']} | {row['source_mode']} | {status} |")
    label_name = str(labels_path.relative_to(ROOT)) if labels_path.is_relative_to(ROOT) else labels_path.name
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
    parser.add_argument("--output", type=Path, default=ROOT / "docs/team/eval.md")
    args = parser.parse_args(argv)
    if args.mode == "mock" and args.engine != "fixed":
        parser.error("mock evaluation uses the fixed engine with all model calls disabled")
    scenes, labels = load_inputs(args.scenes.resolve(), args.labels.resolve(), args.split)
    if args.mode == "mock":
        context = mock_app()
    else:
        # Configure adapters before importing app; live mode never substitutes fixtures.
        os.environ.update(TYPECAST_USE_MOCKS="0", TYPECAST_ENGINE=args.engine)
        from agent.app import app
        context = nullcontext(app)
    with context as app:
        rows = evaluate_app(app, scenes, labels)
    summary = summarize(rows)
    is_mock = args.mode == "mock" or "mock" in summary["source_modes"]
    report = render_report(rows, mock=is_mock, labels_path=args.labels.resolve(),
                           date=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    if is_mock:
        print("mock run: not a result")
    print(f"Scenes: {summary['attempted']} attempted, {summary['succeeded']} succeeded; "
          f"{summary['scored']} labeled scenes scored, {summary['unlabeled']} unlabeled skipped")
    print(f"recall@10: {_score(summary['recall_at_10'])}")
    print(f"Latency: p50={summary['p50_ms']:.2f} ms, p95={summary['p95_ms']:.2f} ms")
    print(f"Engine: {', '.join(summary['engines'])}; source mode: {', '.join(summary['source_modes'])}")
    print(f"Report: {args.output.resolve()}")
    return 0 if summary["succeeded"] == summary["attempted"] and summary["source_modes"] == [args.mode] else 1


if __name__ == "__main__":
    raise SystemExit(main())
