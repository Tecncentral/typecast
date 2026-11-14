"""Offline API acceptance and retrieval-evaluation contract checks."""
from pathlib import Path

import pytest

from agent.eval.harness import mock_app
from agent.eval.run_eval import evaluate_app, load_inputs, summarize
from scripts.e2e import run_e2e

EVAL_ROOT = Path(__file__).resolve().parents[1] / "eval"


@pytest.fixture(scope="module")
def e2e_result():
    return run_e2e()


def test_progress_is_delivered_before_result_while_search_is_pending(e2e_result):
    assert e2e_result["tool_pending_at_first_event"]
    assert e2e_result["first_event_ms"] < e2e_result["result_ms"]
    assert e2e_result["engine"] == "fixed" and e2e_result["source_mode"] == "mock"


def test_refine_keeps_thread_and_performs_no_search(e2e_result):
    assert e2e_result["thread_id"] == e2e_result["refined_thread_id"]
    assert e2e_result["search_calls_before_refine"] == {"search_shots": 1, "search_costar": 1}
    assert e2e_result["search_calls_after_refine"] == e2e_result["search_calls_before_refine"]


def test_yes_approval_only_creates_a_local_draft(e2e_result):
    assert e2e_result["approval"]["sent"] is False
    assert e2e_result["approval"]["status"] == "draft_saved"


def test_eval_fixtures_have_frozen_splits_and_no_invented_labels():
    scenes, labels = load_inputs(EVAL_ROOT / "scenes.jsonl", EVAL_ROOT / "labels.template.jsonl")
    assert len(scenes) == len(labels) == 20
    assert sum(scene["split"] == "test" for scene in scenes) == 15
    assert sum(scene["split"] == "tune" for scene in scenes) == 5
    assert all(label["relevant_shot_ids"] == [] and label["labeler"] == "" for label in labels.values())


def test_eval_uses_top_ten_cached_candidates_and_skips_empty_labels(monkeypatch):
    with mock_app() as app:
        from agent import pipeline

        # Learn the mock ranked pool for a controlled metric check. This is test
        # instrumentation, not a relevance judgment saved to the label template.
        captured = {}
        original = pipeline._persist

        def record_pool(ctx, req, shots, *args, **kwargs):
            captured[req.scene] = [shot.shot_id for shot in shots]
            return original(ctx, req, shots, *args, **kwargs)

        monkeypatch.setattr(pipeline, "_persist", record_pool)
        scenes = [{"id": "metric-check", "scene": "An open office in New York.", "split": "test"}]
        initial = evaluate_app(app, scenes, {})
        assert summarize(initial)["scored"] == 0 and summarize(initial)["recall_at_10"] is None
        pool = captured[scenes[0]["scene"]]
        assert len(pool) > 10
        labels = {"metric-check": {"relevant_shot_ids": [pool[8], pool[10]], "labeler": "test-only"}}
        rows = evaluate_app(app, scenes, labels)
        assert rows[0]["retrieved_count"] == 10
        assert rows[0]["recall_at_10"] == 0.5
        assert summarize(rows)["scored"] == 1
