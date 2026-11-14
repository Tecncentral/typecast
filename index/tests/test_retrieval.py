"""Unit tests for index/search.py using controlled vectors and zero model downloads."""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest

from contracts.schemas import Shot
from index.search import (
    DEFAULT_EMBEDDING_MODEL,
    IndexUnavailableError,
    ShotNotFoundError,
    ShotRetrievalIndex,
    check_shot,
    configure_index,
    get_shot,
    search_shots,
)


def _shot_dict(
    shot_id: str,
    model_id: str,
    property_id: str,
    *,
    sweep_id: str = "sweep_1",
    heading_deg: float = 90.0,
    image_path: str = "images/frame.jpg",
    room_area_m2: float | None = 30.0,
    ceiling_m: float | None = 3.0,
    depth_m: float | None = 5.0,
    measure_on_site: bool = False,
) -> dict:
    return {
        "shot_id": shot_id,
        "model_id": model_id,
        "sweep_id": sweep_id,
        "heading_deg": heading_deg,
        "image_path": image_path,
        "property_id": property_id,
        "room_area_m2": room_area_m2,
        "ceiling_m": ceiling_m,
        "depth_m": depth_m,
        "measure_on_site": measure_on_site,
    }


def _write_cache(
    cache_dir: Path,
    shots: list[dict],
    embeddings: np.ndarray,
    *,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    row_count: int | None = None,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "manifest.json").write_text(
        json.dumps(
            {
                "embedding_model": embedding_model,
                "row_count": len(shots) if row_count is None else row_count,
            }
        ),
        encoding="utf-8",
    )
    (cache_dir / "shots.json").write_text(json.dumps(shots), encoding="utf-8")
    np.save(cache_dir / "embeddings.npy", embeddings)
    return cache_dir


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch):
    configure_index(None)
    monkeypatch.delenv("TYPECAST_USE_MOCKS", raising=False)
    yield
    configure_index(None)


def test_real_mode_missing_cache_fails_clearly_without_mock_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "0")
    configure_index(cache_dir=tmp_path / "missing-cache")

    with pytest.raises(IndexUnavailableError, match="unavailable"):
        search_shots(query_text="concrete loft")


def test_mock_mode_default_uses_mocks_shot_json(monkeypatch: pytest.MonkeyPatch) -> None:
    # TYPECAST_USE_MOCKS defaults to "1" and reads existing mocks/shot.json
    monkeypatch.delenv("TYPECAST_USE_MOCKS", raising=False)
    results = search_shots(query_text="room", k=5)
    assert isinstance(results, list)
    assert all(isinstance(s, Shot) for s in results)


def test_validation_rejects_bad_vectors_duplicates_and_model_mismatch(tmp_path: Path) -> None:
    base_shots = [
        _shot_dict("s1", "m1", "p1"),
        _shot_dict("s2", "m2", "p2"),
    ]
    valid = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    # Zero-norm vector
    c_zero = _write_cache(
        tmp_path / "zero",
        base_shots,
        np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.float32),
    )
    with pytest.raises(IndexUnavailableError, match="zero-norm"):
        ShotRetrievalIndex.from_cache_dir(c_zero)

    # Non-finite vector
    c_nan = _write_cache(
        tmp_path / "nan",
        base_shots,
        np.array([[1.0, np.nan], [0.0, 1.0]], dtype=np.float32),
    )
    with pytest.raises(IndexUnavailableError, match="NaN or Inf"):
        ShotRetrievalIndex.from_cache_dir(c_nan)

    # Wrong dtype
    c_dtype = _write_cache(tmp_path / "dtype", base_shots, valid.astype(np.float64))
    with pytest.raises(IndexUnavailableError, match="float32"):
        ShotRetrievalIndex.from_cache_dir(c_dtype)

    # Duplicate shot_id
    dup_shots = [_shot_dict("s1", "m1", "p1"), _shot_dict("s1", "m2", "p2")]
    c_dup = _write_cache(tmp_path / "dup", dup_shots, valid)
    with pytest.raises(IndexUnavailableError, match="Duplicate shot_id"):
        ShotRetrievalIndex.from_cache_dir(c_dup)

    # Row count mismatch
    c_rows = _write_cache(tmp_path / "rows", base_shots, valid[:1])
    with pytest.raises(IndexUnavailableError, match="does not match"):
        ShotRetrievalIndex.from_cache_dir(c_rows)

    # Embedding model mismatch
    c_model = _write_cache(
        tmp_path / "model",
        base_shots,
        valid,
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
    with pytest.raises(IndexUnavailableError, match="model mismatch"):
        ShotRetrievalIndex.from_cache_dir(c_model)


def test_text_search_cosine_ranking_deterministic_tie_break_and_returns_shots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "0")
    shots = [
        _shot_dict("shot_b", "m1", "p1"),
        _shot_dict("shot_a", "m2", "p2"),
        _shot_dict("shot_c", "m3", "p3"),
    ]
    vecs = np.array(
        [
            [0.6, 0.8, 0.0, 0.0],
            [0.6, 0.0, 0.8, 0.0],
            [1.0, 0.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    cache_dir = _write_cache(tmp_path / "cache", shots, vecs)

    idx = ShotRetrievalIndex.from_cache_dir(
        cache_dir,
        text_encoder=lambda _: np.array([3.0, 0.0, 0.0, 0.0], dtype=np.float32),
    )
    configure_index(idx)

    results = search_shots(query_text="industrial gallery", k=3)
    assert all(isinstance(r, Shot) for r in results)
    assert [r.shot_id for r in results] == ["shot_c", "shot_a", "shot_b"]
    assert results[0].score == pytest.approx(1.0)
    assert results[1].score == pytest.approx(0.6)
    assert results[2].score == pytest.approx(0.6)


def test_query_shot_id_excludes_both_model_id_and_property_id(tmp_path: Path) -> None:
    shots = [
        _shot_dict("src", "model_1", "prop_1"),
        _shot_dict("same_model", "model_1", "prop_other"),
        _shot_dict("same_prop", "model_other", "prop_1"),
        _shot_dict("valid_match", "model_2", "prop_2"),
    ]
    vecs = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.99, 0.14106736, 0.0, 0.0],
            [0.98, 0.19899748, 0.0, 0.0],
            [0.7, 0.71414284, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    cache_dir = _write_cache(tmp_path / "cache", shots, vecs)
    configure_index(ShotRetrievalIndex.from_cache_dir(cache_dir))

    results = search_shots(query_shot_id="src", k=10)
    assert [r.shot_id for r in results] == ["valid_match"]


def test_strict_null_geometry_filters_applied_before_top_k(tmp_path: Path) -> None:
    shots = [
        _shot_dict("null_dims", "m1", "p1", room_area_m2=None, ceiling_m=None, depth_m=None),
        _shot_dict("too_small", "m2", "p2", room_area_m2=15.0, ceiling_m=2.5, depth_m=4.0),
        _shot_dict("passes_all", "m3", "p3", room_area_m2=45.0, ceiling_m=3.4, depth_m=7.0),
    ]
    vecs = np.array(
        [
            [0.95, 0.3122499, 0.0],
            [0.80, 0.60, 0.0],
            [0.50, 0.8660254, 0.0],
        ],
        dtype=np.float32,
    )
    cache_dir = _write_cache(tmp_path / "cache", shots, vecs)
    idx = ShotRetrievalIndex.from_cache_dir(
        cache_dir,
        text_encoder=lambda _: np.array([1.0, 0.0, 0.0], dtype=np.float32),
    )
    configure_index(idx)

    # Without filter, null_dims is top-1
    assert [r.shot_id for r in search_shots(query_text="space", k=1)] == ["null_dims"]

    # Filter happens BEFORE top-1: null_dims and too_small are excluded so passes_all wins top-1
    filtered = search_shots(
        query_text="space",
        min_area_m2=20.0,
        min_ceiling_m=3.0,
        min_depth_m=6.0,
        k=1,
    )
    assert [r.shot_id for r in filtered] == ["passes_all"]

    # Every individual minimum rejects null dimensions
    for filt in ({"min_area_m2": 1.0}, {"min_ceiling_m": 1.0}, {"min_depth_m": 1.0}):
        ids = {r.shot_id for r in search_shots(query_text="space", k=10, **filt)}
        assert "null_dims" not in ids


def test_get_shot_and_check_shot_delegate_to_geometry_check_fit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shots = [
        _shot_dict(
            "s_check",
            "m1",
            "p1",
            room_area_m2=28.0,
            ceiling_m=3.1,
            depth_m=None,
            measure_on_site=True,
        )
    ]
    vecs = np.array([[1.0, 0.0]], dtype=np.float32)
    cache_dir = _write_cache(tmp_path / "cache", shots, vecs)
    configure_index(ShotRetrievalIndex.from_cache_dir(cache_dir))

    shot = get_shot("s_check")
    assert isinstance(shot, Shot)
    assert shot.shot_id == "s_check"
    assert shot.measure_on_site is True

    captured: dict = {}

    def fake_check_fit(depth_m, ceiling_m, focal_mm, frame_width_m, measure_on_site):
        captured.update(depth_m=depth_m, ceiling_m=ceiling_m, focal_mm=focal_mm,
                        frame_width_m=frame_width_m, measure_on_site=measure_on_site)
        return {"ok": True}

    monkeypatch.setattr("index.search.check_fit", fake_check_fit)
    res = check_shot("s_check", focal_mm=35.0, frame_width_m=4.0)
    assert res == {"ok": True}
    assert captured == {
        "ceiling_m": 3.1,
        "depth_m": None,
        "measure_on_site": True,
        "focal_mm": 35.0,
        "frame_width_m": 4.0,
    }

    with pytest.raises(ShotNotFoundError):
        get_shot("unknown")


def test_invalid_catalog_dimensions_become_unknown_and_bad_row_count_is_sanitized(tmp_path):
    data = [_shot_dict('s1', 'm1', 'p1', room_area_m2=0, ceiling_m=float('nan'), depth_m=-1)]
    path = _write_cache(tmp_path / 'index', data, np.array([[1, 0]], dtype=np.float32))
    idx = ShotRetrievalIndex.from_cache_dir(path)
    shot = idx.get_shot('s1')
    assert (shot.room_area_m2, shot.ceiling_m, shot.depth_m) == (None, None, None)
    assert shot.measure_on_site and idx.check_shot('s1').status == 'unknown'
    (path / 'manifest.json').write_text(json.dumps({'embedding_model': DEFAULT_EMBEDDING_MODEL,
                                                  'row_count': 'bad'}))
    with pytest.raises(IndexUnavailableError, match='row_count'):
        ShotRetrievalIndex.from_cache_dir(path)


def test_reader_honors_custom_index_directory(tmp_path, monkeypatch):
    path = _write_cache(tmp_path / 'custom', [_shot_dict('custom', 'm', 'p')],
                        np.array([[1, 0]], dtype=np.float32))
    monkeypatch.setenv('TYPECAST_USE_MOCKS', '0')
    monkeypatch.setenv('TYPECAST_INDEX_DIR', str(path))
    assert get_shot('custom').shot_id == 'custom'


@pytest.mark.parametrize('bad', ['unknown', '3.1m', True, [], {}])
def test_malformed_catalog_dimensions_never_abort_retrieval(tmp_path, bad):
    path = _write_cache(tmp_path / 'index',
        [_shot_dict('s', 'm', 'p', ceiling_m=bad)], np.array([[1, 0]], dtype=np.float32))
    idx = ShotRetrievalIndex.from_cache_dir(path)
    assert idx.get_shot('s').ceiling_m is None
    assert idx.check_shot('s').status == 'unknown'
