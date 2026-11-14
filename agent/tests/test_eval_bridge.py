"""Credential-free checks of frozen lab provenance and pooled evaluation semantics."""
from copy import deepcopy
import json
import os
from pathlib import Path

import numpy as np
import pytest

from agent.eval import label_bridge as bridge
from agent.eval.run_eval import evaluate_app, load_inputs, render_report
from agent.eval.harness import mock_app


@pytest.fixture
def frozen_lab(tmp_path, monkeypatch):
    from index.search import DEFAULT_EMBEDDING_MODEL, ShotRetrievalIndex

    directory = tmp_path / "index" / ("a" * 32)
    directory.mkdir(parents=True)
    (directory.parent / "CURRENT").write_text(directory.name)
    shots = json.loads((bridge.ROOT / "mocks/shot.json").read_text())[:3]
    (directory / "shots.json").write_text(json.dumps(shots))
    (directory / "manifest.json").write_text(json.dumps(
        {"embedding_model": DEFAULT_EMBEDDING_MODEL, "row_count": len(shots)}))
    np.save(directory / "embeddings.npy", np.array([[1, 0], [.8, .2], [0, 1]], dtype=np.float32))
    original = ShotRetrievalIndex.from_cache_dir
    monkeypatch.setattr(ShotRetrievalIndex, "from_cache_dir", classmethod(
        lambda cls, path: original(path, text_encoder=lambda text: np.array([1, 0], dtype=np.float32))))
    scenes = [{"id": "interior-test", "scene": "bright kitchen with cabinets", "split": "test"},
              {"id": "interior-tune", "scene": "empty room with windows", "split": "tune"}]
    snapshot, pinned = bridge.freeze(scenes, directory.parent)
    assert pinned == directory
    labels = {scene["id"]: {"scene_id": scene["id"], "scene": scene["scene"], "split": scene["split"],
                            "reviewer": "Test-only reviewer", "reviewer_kind": "human", "mode": "live",
                            "labelled_at": snapshot["frozen_at"], "reviewed_shot_ids": scene["pool_shot_ids"],
                            "relevant_shot_ids": scene["pool_shot_ids"][:1]}
              for scene in snapshot["scenes"]}
    return snapshot, labels, directory.parent


def test_export_preserves_exact_prompts_human_provenance_and_complete_empty_review(frozen_lab, tmp_path):
    snapshot, labels, index_dir = frozen_lab
    labels["interior-test"]["relevant_shot_ids"] = []
    scenes, exported = bridge.export(snapshot, {"labels": list(labels.values())}, index_dir)
    assert len(scenes) == len(exported) == 1
    assert scenes[0]["id"] == "interior-test" and scenes[0]["scene"] == snapshot["scenes"][0]["scene"]
    assert scenes[0]["split"] == "test"
    assert exported[0] == {**labels["interior-test"], "id": "interior-test", "labeler": "Test-only reviewer"}
    assert exported[0]["relevant_shot_ids"] == []
    paths = [tmp_path / name for name in ("scenes.jsonl", "labels.jsonl")]
    for path, records in zip(paths, (scenes, exported)):
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
    loaded_scenes, loaded_labels = load_inputs(*paths, split="test")
    assert bridge.validate_live_inputs(loaded_scenes, loaded_labels, index_dir) == index_dir / ("a" * 32)


@pytest.mark.parametrize(("field", "value", "message"), [
    ("reviewer_kind", "ai", "human"), ("mode", "mock", "live"),
    ("reviewer", " ", "attribution"), ("scene", "rewritten scene", "stale scene"),
    ("split", "tune", "stale scene"), ("reviewed_shot_ids", ["unknown"], "stale/incomplete"),
    ("relevant_shot_ids", ["unknown"], "unknown relevant"),
    ("labelled_at", "2000-01-01T00:00:00+00:00", "predates"),
    ("labelled_at", "2026-11-14T12:00:00", "timezone-aware"),
])
def test_export_rejects_ai_mock_stale_or_incomplete_reviews(frozen_lab, field, value, message):
    snapshot, labels, index_dir = frozen_lab
    labels["interior-test"][field] = value
    with pytest.raises(ValueError, match=message):
        bridge.export(snapshot, labels, index_dir)


def test_export_rejects_unknown_missing_duplicate_and_tampered_sets(frozen_lab):
    snapshot, labels, index_dir = frozen_lab
    with pytest.raises(ValueError, match="unknown scene"):
        bridge.export(snapshot, labels | {"unknown": {**labels["interior-test"], "scene_id": "unknown"}}, index_dir)
    with pytest.raises(ValueError, match="Every selected"):
        bridge.export(snapshot, {}, index_dir)
    with pytest.raises(ValueError, match="unique scene_id"):
        bridge.export(snapshot, {"labels": [labels["interior-test"], labels["interior-test"]]}, index_dir)
    altered = deepcopy(snapshot)
    altered["scenes"][0]["scene"] = "changed after freezing"
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        bridge.export(altered, labels, index_dir)


def test_test_export_ignores_old_unselected_tune_judgments(frozen_lab):
    snapshot, labels, index_dir = frozen_lab
    labels["interior-tune"].update(reviewer_kind="ai", mode="mock", scene="old prompt",
                                    labelled_at="2000-01-01T00:00:00+00:00")
    scenes, exported = bridge.export(snapshot, labels, index_dir, split="test")
    assert [scene["id"] for scene in scenes] == ["interior-test"]
    assert exported[0]["reviewer_kind"] == "human"
    with pytest.raises(ValueError, match="human"):
        bridge.export(snapshot, labels, index_dir, split="all")


def test_cli_loads_private_local_model_and_index_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "ROOT", tmp_path)
    for name in ("HF_HOME", "TYPECAST_INDEX_DIR"):
        monkeypatch.setenv(name, "temporary test value")
        monkeypatch.delenv(name)
    (tmp_path / ".env").write_text("HF_HOME=/private/local-models\nTYPECAST_INDEX_DIR=/private/frozen-index\n")
    with pytest.raises(SystemExit) as result:
        bridge.main(["--help"])
    assert result.value.code == 0
    assert os.environ["HF_HOME"] == "/private/local-models"
    assert os.environ["TYPECAST_INDEX_DIR"] == "/private/frozen-index"


def test_changed_index_rejected_at_export_and_again_before_live_scoring(frozen_lab):
    snapshot, labels, index_dir = frozen_lab
    scenes, exported = bridge.export(snapshot, labels, index_dir)
    (index_dir / ("a" * 32) / "manifest.json").write_text("changed generation")
    with pytest.raises(ValueError, match="differs from frozen"):
        bridge.export(snapshot, labels, index_dir)
    with pytest.raises(ValueError, match="differs from frozen"):
        bridge.validate_live_inputs(scenes, {label["id"]: label for label in exported}, index_dir)


def test_outputs_stay_private_and_cannot_replace_frozen_files(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "ROOT", tmp_path)
    private = tmp_path / "cache/evaluation/scenes.jsonl"
    with pytest.raises(ValueError, match="ignored cache"):
        bridge._write_outputs([(private, "private"), (tmp_path / "public.jsonl", "public")])
    assert not private.exists()
    bridge._write_outputs([(private, "private")])
    bridge._write_outputs([(private, "private")])
    with pytest.raises(ValueError, match="overwrite frozen"):
        bridge._write_outputs([(private, "changed")])
    assert private.read_text() == "private"


def test_pooled_report_keeps_global_gold_and_discloses_city_eligibility(monkeypatch):
    from index import search

    with mock_app() as app:
        from agent import pipeline
        from data import costar_tools
        monkeypatch.setattr(search, "_ACTIVE_INDEX", search.ShotRetrievalIndex.from_mocks())
        catalog = search.get_active_index()
        first = catalog.shots[0]
        outside = next(shot for shot in catalog.shots if shot.property_id != first.property_id)
        relevant = [first.shot_id, outside.shot_id]
        city_pool = [costar_tools.get_property(first.property_id)]
        monkeypatch.setattr(costar_tools, "search_costar", lambda **kwargs: city_pool)
        monkeypatch.setattr(pipeline, "search_costar", lambda **kwargs: city_pool)
        scenes = [{"id": "test-only-pooled", "scene": "a bright kitchen", "split": "test",
                   "evaluation": {"pool_scope": bridge.POOL_SCOPE}}]
        labels = {scenes[0]["id"]: {"relevant_shot_ids": relevant, "reviewed_shot_ids": relevant}}
        rows = evaluate_app(app, scenes, labels)
        assert rows[0]["relevant_count"] == 2
        assert rows[0]["requested_city"] == "Los Angeles"
        assert rows[0]["eligible_relevant_count"] == 1
        assert rows[0]["recall_at_10"] == .5
        report = render_report(rows, mock=True, labels_path=Path("private.jsonl"), date="test")
        assert "mock run: not a result" in report
        assert "pooled pipeline recall@10" in report and "City-eligible gold" in report
        assert "outside the city pool remain in the denominator" in report
        assert all(sid not in report for sid in relevant)
