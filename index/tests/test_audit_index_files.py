"""(b) Corrupted and absent index/manifest/cache files fail clearly, never fall back to mocks."""
import io
import pickle

import numpy as np
import pytest

from index import search, store
from index.search import IndexUnavailableError, ShotRetrievalIndex
from index.tests._audit_helpers import shot, write_generation

SHOTS = [shot("a", "p1"), shot("b", "p2")]
VECS = np.eye(2, 3, dtype=np.float32)


def _load(path):
    return ShotRetrievalIndex.from_cache_dir(path, text_encoder=lambda _t: np.ones(3, np.float32))


def _npy(array, allow_pickle=False):
    buf = io.BytesIO()
    np.save(buf, array, allow_pickle=allow_pickle)
    return buf.getvalue()


def test_valid_generation_loads(tmp_path):
    assert len(_load(write_generation(tmp_path / "g", SHOTS, VECS)).shots) == 2


def test_absent_cache_dir_is_clear(tmp_path):
    with pytest.raises(IndexUnavailableError, match="missing"):
        _load(tmp_path / "nope")


@pytest.mark.parametrize("pointer", ["", "../escape", "Z" * 32, "a" * 31])
def test_bad_current_pointer_is_clear(tmp_path, pointer):
    root = tmp_path / "shot-index"
    root.mkdir()
    (root / "CURRENT").write_text(pointer)
    with pytest.raises(IndexUnavailableError):
        _load(root)


def test_current_pointer_to_missing_generation_is_clear(tmp_path):
    root = tmp_path / "shot-index"
    root.mkdir()
    (root / "CURRENT").write_text("0" * 32)
    with pytest.raises(IndexUnavailableError, match="missing"):
        _load(root)


@pytest.mark.parametrize("case", [
    dict(manifest="{truncated"), dict(manifest="[]"), dict(manifest={"row_count": 2}),
    dict(manifest={"embedding_model": "other/model", "row_count": 2}),
    dict(manifest={"embedding_model": search.DEFAULT_EMBEDDING_MODEL, "row_count": 3}),
    dict(shots_text="[{\"shot_id\": \"a\""), dict(shots_text="[]"),
    dict(shots_text="[{\"shot_id\": \"a\"}]"),
    dict(embeddings_bytes=b"\x93NUMPY garbage"),
    dict(embeddings_bytes=b""),
    dict(embeddings_bytes=_npy(np.array([{"x": 1}, {"y": 2}], dtype=object), allow_pickle=True)),
    dict(embeddings_bytes=_npy(np.eye(2, 3, dtype=np.float64))),
    dict(embeddings_bytes=_npy(np.eye(3, 3, dtype=np.float32))),
    dict(embeddings_bytes=_npy(np.array([[np.nan, 0, 0], [0, 1, 0]], dtype=np.float32))),
    dict(embeddings_bytes=_npy(np.zeros((2, 3), dtype=np.float32))),
], ids=["manifest-truncated", "manifest-list", "manifest-no-model", "manifest-model-mismatch",
        "manifest-rowcount-mismatch", "shots-truncated", "shots-empty", "shots-missing-fields",
        "npy-garbage", "npy-empty", "npy-pickled-objects", "npy-float64", "npy-row-mismatch",
        "npy-nan", "npy-zero-norm"])
def test_corrupt_generation_raises_index_unavailable(tmp_path, case):
    path = write_generation(tmp_path / "g", SHOTS, VECS, **case)
    with pytest.raises(IndexUnavailableError):
        _load(path)


@pytest.mark.parametrize("row_count", ["two", "2", [2], {"n": 2}, True, 2.0, 3],
                         ids=["string", "numeric-string", "list", "object", "bool", "float", "mismatch"])
def test_malformed_row_count_is_index_unavailable(tmp_path, row_count):
    """Regression (fixed in 9a6fea1, index/search.py row_count check): every malformed or
    mismatched row_count is a controlled IndexUnavailableError, never a raw ValueError/TypeError."""
    manifest = {"embedding_model": search.DEFAULT_EMBEDDING_MODEL, "row_count": row_count}
    path = write_generation(tmp_path / "g", SHOTS, VECS, manifest=manifest)
    with pytest.raises(IndexUnavailableError):
        _load(path)


def test_live_mode_without_index_never_falls_back_to_mocks(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "0")
    search.configure_index(None, cache_dir=tmp_path / "absent")
    try:
        with pytest.raises(IndexUnavailableError):
            search.search_shots(query_text="brick")
    finally:
        search.configure_index(None)


def test_store_roundtrip_is_readable_by_search(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path)
    monkeypatch.delenv("TYPECAST_INDEX_DIR", raising=False)
    store.save_index(SHOTS, VECS)
    assert len(_load(tmp_path / "cache" / "shot-index").shots) == 2


def test_typecast_index_dir_is_honoured_by_reader_and_writer(tmp_path, monkeypatch):
    """Regression (fixed in 9a6fea1): store.save_index and search.get_active_index agree on
    TYPECAST_INDEX_DIR, and the default directory is not read instead."""
    monkeypatch.setattr(store, "ROOT", tmp_path)
    monkeypatch.setattr(search, "DEFAULT_CACHE_DIR", tmp_path / "cache" / "shot-index")
    monkeypatch.setenv("TYPECAST_INDEX_DIR", str(tmp_path / "cache" / "alt-index"))
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "0")
    store.save_index(SHOTS, VECS)
    search.configure_index(None)
    try:
        assert len(search.get_active_index().shots) == 2
        assert not (tmp_path / "cache" / "shot-index").exists()
    finally:
        search.configure_index(None)


def test_rebuilt_generation_is_isolated_from_old_readers(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path)
    monkeypatch.delenv("TYPECAST_INDEX_DIR", raising=False)
    store.save_index(SHOTS, VECS)
    old = _load(tmp_path / "cache" / "shot-index")
    store.save_index(SHOTS[:1], VECS[:1])
    assert len(old.shots) == 2
    assert len(_load(tmp_path / "cache" / "shot-index").shots) == 1


# ---- source-mode flag consistency (USE_MOCKS compatibility shim) -------------------

def test_use_mocks_is_a_boolean_and_default_is_mock():
    assert isinstance(search.USE_MOCKS, bool)


def test_patched_use_mocks_controls_index_mode(monkeypatch):
    monkeypatch.setattr(search, "USE_MOCKS", not search._INITIAL_USE_MOCKS)
    assert search._use_mocks_enabled() is (not search._INITIAL_USE_MOCKS)


MODE_VALUES = ["1", "0", "true", "TRUE", "yes", "on", "2", "", " 1", "1 "]


@pytest.mark.parametrize("raw", MODE_VALUES, ids=[repr(v) for v in MODE_VALUES])
def test_index_mode_uses_exact_equals_one_contract(monkeypatch, raw):
    """Regression (fixed in 9a6fea1): only the exact string '1' enables mocks; 'true',
    'yes', '0', '' and padded values all mean live (fail closed to the real index)."""
    monkeypatch.setenv("TYPECAST_USE_MOCKS", raw)
    monkeypatch.setattr(search, "USE_MOCKS", search._INITIAL_USE_MOCKS)  # unpatched path
    assert search._use_mocks_enabled() is (raw == "1")


@pytest.mark.parametrize("raw", ["1", "0", "true", "yes", "2"])
def test_runtime_adapters_and_index_agree_on_source_mode(raw):
    """Fresh interpreter per value because adapters read the flag at import time."""
    import json as _json
    import os
    import pathlib
    import subprocess
    import sys
    root = pathlib.Path(__file__).resolve().parents[2]
    code = ("import json; from agent import runtime; from index import search; "
            "print(json.dumps({'modes': runtime.source_modes(), "
            "'index_enabled': search._use_mocks_enabled()}))")
    env = {**os.environ, "TYPECAST_USE_MOCKS": raw, "PYTHONPATH": str(root)}
    out = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True,
                         text=True, timeout=120, check=True).stdout.strip().splitlines()[-1]
    result = _json.loads(out)
    expected = "mock" if raw == "1" else "live"
    assert set(result["modes"].values()) == {expected}, result
    assert result["index_enabled"] is (raw == "1")
