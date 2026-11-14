"""Shot retrieval over mocks/shot.json (when TYPECAST_USE_MOCKS=1) or cache/shot-index."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Sequence
import numpy as np

from contracts.schemas import Shot
from index.geometry import check_fit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = ROOT / "cache/shot-index"
DEFAULT_MOCKS_PATH = ROOT / "mocks/shot.json"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/clip-ViT-B-32"

SHOTS_FILENAME = "shots.json"
EMBEDDINGS_FILENAME = "embeddings.npy"
MANIFEST_FILENAME = "manifest.json"
# Compatibility override used by the integrator's isolated offline harness.
# None keeps normal process environment selection; True/False explicitly overrides it.
USE_MOCKS: bool | None = None


class IndexUnavailableError(RuntimeError):
    """Raised when the real shot index in cache/shot-index is missing or invalid."""


class ShotNotFoundError(KeyError):
    """Raised when a requested shot_id does not exist in the active catalog."""


def _use_mocks_enabled() -> bool:
    if USE_MOCKS is not None:
        return USE_MOCKS
    raw = os.environ.get("TYPECAST_USE_MOCKS", "1").strip().lower()
    return raw not in {"0", "false", "no", "off", ""}


def _l2_normalize_1d(vec: np.ndarray, *, context: str) -> np.ndarray:
    arr = np.asarray(vec, dtype=np.float32)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError(f"{context}: expected non-empty 1D vector, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{context}: vector contains NaN or Inf")
    norm = float(np.linalg.norm(arr))
    if norm <= 0.0 or not np.isfinite(norm):
        raise ValueError(f"{context}: vector has zero norm")
    return (arr / norm).astype(np.float32)


def _validate_and_normalize_matrix(matrix: np.ndarray, expected_rows: int) -> np.ndarray:
    arr = np.asarray(matrix)
    if arr.dtype != np.float32:
        raise IndexUnavailableError(f"Embeddings must be float32, got {arr.dtype}")
    if arr.ndim != 2 or arr.shape[0] != expected_rows or arr.shape[1] == 0:
        raise IndexUnavailableError(
            f"Embedding matrix shape {arr.shape} does not match shot count {expected_rows}"
        )
    if not np.all(np.isfinite(arr)):
        raise IndexUnavailableError("Embedding matrix contains NaN or Inf values")

    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    bad = np.where((norms[:, 0] <= 0.0) | (~np.isfinite(norms[:, 0])))[0]
    if bad.size > 0:
        raise IndexUnavailableError(f"Embedding matrix contains zero-norm rows at {bad[:5].tolist()}")
    return (arr / norms).astype(np.float32)


class _LazySentenceTransformerEncoder:
    """Lazily loads SentenceTransformer CLIP model on first text query without external API keys."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def encode_text(self, text: str) -> np.ndarray:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("query_text must be a non-empty string")
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
            except ImportError as exc:
                raise IndexUnavailableError(
                    "Text search requires optional dependency 'sentence-transformers'."
                ) from exc
            self._model = SentenceTransformer(self.model_name)

        vec = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return _l2_normalize_1d(np.asarray(vec, dtype=np.float32), context="Text embedding")


def _load_shots_file(path: Path, *, error_cls: type[Exception]) -> list[Shot]:
    if not path.is_file():
        raise error_cls(f"Shot catalog file not found: '{path}'")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise error_cls(f"Failed to parse shot catalog '{path}': {exc}") from exc

    if isinstance(payload, dict) and "shots" in payload:
        items = payload["shots"]
    elif isinstance(payload, list):
        items = payload
    else:
        raise error_cls(f"Shot catalog '{path}' must be a JSON list or object with 'shots'")

    shots: list[Shot] = []
    seen_ids: set[str] = set()
    for item in items:
        try:
            shot = Shot.model_validate(item)
        except Exception as exc:  # noqa: BLE001
            raise error_cls(f"Invalid Shot entry in '{path}': {exc}") from exc
        if shot.shot_id in seen_ids:
            raise error_cls(f"Duplicate shot_id '{shot.shot_id}' in '{path}'")
        seen_ids.add(shot.shot_id)
        shots.append(shot)

    if not shots:
        raise error_cls(f"Shot catalog '{path}' is empty")
    return shots


class ShotRetrievalIndex:
    """Validated in-memory shot catalog and aligned float32 embedding index."""

    def __init__(
        self,
        shots: Sequence[Shot],
        embeddings: np.ndarray | None,
        *,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        is_mock: bool = False,
        text_encoder: Callable[[str], np.ndarray] | None = None,
    ) -> None:
        if not shots:
            raise IndexUnavailableError("Cannot initialize index with empty shot list")
        if not isinstance(embedding_model, str) or not embedding_model.strip():
            raise IndexUnavailableError("Missing non-empty embedding_model identity")

        seen: set[str] = set()
        id_to_idx: dict[str, int] = {}
        for i, s in enumerate(shots):
            if s.shot_id in seen:
                raise IndexUnavailableError(f"Duplicate shot_id '{s.shot_id}'")
            seen.add(s.shot_id)
            id_to_idx[s.shot_id] = i

        self.shots: tuple[Shot, ...] = tuple(shots)
        self.is_mock: bool = is_mock
        self.embedding_model: str = embedding_model.strip()
        self._id_to_idx: dict[str, int] = id_to_idx
        self._text_encoder_fn = text_encoder
        self._lazy_st: _LazySentenceTransformerEncoder | None = None

        if embeddings is None:
            if not is_mock:
                raise IndexUnavailableError("Real index requires aligned float32 embeddings")
            self.embeddings: np.ndarray | None = None
        else:
            self.embeddings = _validate_and_normalize_matrix(embeddings, expected_rows=len(self.shots))

        self._model_ids = np.array([s.model_id for s in self.shots], dtype=object)
        self._property_ids = np.array([s.property_id for s in self.shots], dtype=object)
        self._room_areas = np.array(
            [np.nan if s.room_area_m2 is None else float(s.room_area_m2) for s in self.shots],
            dtype=np.float64,
        )
        self._ceilings = np.array(
            [np.nan if s.ceiling_m is None else float(s.ceiling_m) for s in self.shots],
            dtype=np.float64,
        )
        self._depths = np.array(
            [np.nan if s.depth_m is None else float(s.depth_m) for s in self.shots],
            dtype=np.float64,
        )

    @classmethod
    def from_cache_dir(
        cls,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
        *,
        expected_embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        text_encoder: Callable[[str], np.ndarray] | None = None,
    ) -> "ShotRetrievalIndex":
        root = Path(cache_dir)
        pointer = root / "CURRENT"
        if pointer.exists():
            name = pointer.read_text(encoding="utf-8").strip()
            if len(name) != 32 or any(c not in "0123456789abcdef" for c in name):
                raise IndexUnavailableError("Invalid index generation pointer")
            root = root / name
        manifest_path = root / MANIFEST_FILENAME
        shots_path = root / SHOTS_FILENAME
        embeddings_path = root / EMBEDDINGS_FILENAME

        missing = [p.name for p in (manifest_path, shots_path, embeddings_path) if not p.is_file()]
        if missing:
            raise IndexUnavailableError(
                f"Real index unavailable in '{root}': missing {', '.join(missing)}"
            )

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexUnavailableError(f"Failed to read manifest '{manifest_path}': {exc}") from exc

        if not isinstance(manifest, dict):
            raise IndexUnavailableError(f"Manifest '{manifest_path}' must be a JSON object")

        model_id = manifest.get("embedding_model")
        if not isinstance(model_id, str) or not model_id.strip():
            raise IndexUnavailableError(f"Manifest '{manifest_path}' missing 'embedding_model'")
        if expected_embedding_model and model_id.strip() != expected_embedding_model:
            raise IndexUnavailableError(
                f"Embedding model mismatch: found '{model_id}', expected '{expected_embedding_model}'"
            )

        shots = _load_shots_file(shots_path, error_cls=IndexUnavailableError)

        manifest_rows = manifest.get("row_count")
        if manifest_rows is not None and int(manifest_rows) != len(shots):
            raise IndexUnavailableError(
                f"Manifest row_count ({manifest_rows}) != shots count ({len(shots)})"
            )

        try:
            embeddings = np.load(embeddings_path, allow_pickle=False)
        except Exception as exc:  # noqa: BLE001
            raise IndexUnavailableError(f"Failed to load '{embeddings_path}': {exc}") from exc

        return cls(
            shots=shots,
            embeddings=embeddings,
            embedding_model=model_id.strip(),
            is_mock=False,
            text_encoder=text_encoder,
        )

    @classmethod
    def from_mocks(
        cls,
        mocks_path: str | Path = DEFAULT_MOCKS_PATH,
        *,
        text_encoder: Callable[[str], np.ndarray] | None = None,
    ) -> "ShotRetrievalIndex":
        shots = _load_shots_file(Path(mocks_path), error_cls=IndexUnavailableError)
        return cls(
            shots=shots,
            embeddings=None,
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            is_mock=True,
            text_encoder=text_encoder,
        )

    def _encode_text(self, query_text: str) -> np.ndarray:
        if self._text_encoder_fn is not None:
            raw = self._text_encoder_fn(query_text)
        else:
            if self._lazy_st is None:
                self._lazy_st = _LazySentenceTransformerEncoder(self.embedding_model)
            raw = self._lazy_st.encode_text(query_text)
        vec = _l2_normalize_1d(raw, context="Encoded query_text")
        if self.embeddings is not None and vec.shape[0] != self.embeddings.shape[1]:
            raise IndexUnavailableError(
                f"Query vector dim {vec.shape[0]} != index dim {self.embeddings.shape[1]}"
            )
        return vec

    def get_shot(self, shot_id: str) -> Shot:
        idx = self._id_to_idx.get(shot_id)
        if idx is None:
            raise ShotNotFoundError(f"Unknown shot_id: '{shot_id}'")
        return self.shots[idx].model_copy(deep=True)

    def check_shot(self, shot_id, focal_mm=24.0, frame_width_m=6.0):
        shot = self.get_shot(shot_id)
        return check_fit(shot.depth_m, shot.ceiling_m, focal_mm, frame_width_m, shot.measure_on_site)

    def search_shots(
        self,
        query_text: str | None = None,
        query_shot_id: str | None = None,
        property_ids: Sequence[str] | None = None,
        min_area_m2: float | None = None,
        min_ceiling_m: float | None = None,
        min_depth_m: float | None = None,
        k: int = 200,
    ) -> list[Shot]:
        if isinstance(k, bool) or not isinstance(k, int):
            raise ValueError("k must be an integer")
        if k <= 0:
            return []
        if (query_text is None) == (query_shot_id is None):
            raise ValueError("Provide exactly one of 'query_text' or 'query_shot_id'")
        if query_text is not None and (not isinstance(query_text, str) or not query_text.strip()):
            raise ValueError("query_text must be a non-empty string")
        for value in (min_area_m2, min_ceiling_m, min_depth_m):
            if value is not None and (not np.isfinite(value) or value < 0):
                raise ValueError("Geometry minimums must be finite and nonnegative")

        mask = np.ones(len(self.shots), dtype=bool)
        src_idx: int | None = None

        if query_shot_id is not None:
            src_idx = self._id_to_idx.get(query_shot_id)
            if src_idx is None:
                raise ShotNotFoundError(f"Unknown query_shot_id: '{query_shot_id}'")
            src_shot = self.shots[src_idx]
            mask &= self._model_ids != src_shot.model_id
            mask &= self._property_ids != src_shot.property_id

        # Hard filters applied BEFORE top-k selection; missing (NaN) dimensions fail explicit minimums.
        if property_ids is not None:
            allowed = set(property_ids)
            if not allowed:
                return []
            mask &= np.isin(self._property_ids, list(allowed))

        if min_area_m2 is not None:
            mask &= (~np.isnan(self._room_areas)) & (self._room_areas >= float(min_area_m2))
        if min_ceiling_m is not None:
            mask &= (~np.isnan(self._ceilings)) & (self._ceilings >= float(min_ceiling_m))
        if min_depth_m is not None:
            mask &= (~np.isnan(self._depths)) & (self._depths >= float(min_depth_m))

        candidates = np.flatnonzero(mask)
        if candidates.size == 0:
            return []

        if self.embeddings is None:
            # Preserve shared fixture ranking so offline demos remain reproducible.
            # These supplied scores are not measured semantic similarities.
            scores = np.array([self.shots[idx].score or 0.0 for idx in candidates], dtype=np.float32)
        else:
            if src_idx is not None:
                query_vec = self.embeddings[src_idx]
            else:
                assert query_text is not None
                query_vec = self._encode_text(query_text)
            scores = self.embeddings[candidates] @ query_vec

        ranked = sorted(
            zip(candidates.tolist(), scores.tolist()),
            key=lambda pair: (-pair[1], self.shots[pair[0]].shot_id),
        )[:k]

        results: list[Shot] = []
        for idx, score in ranked:
            base = self.shots[idx]
            reason = (
                f"similar to {query_shot_id}"
                if query_shot_id is not None
                else f"matched query: {query_text}"
            )
            if self.is_mock:
                reason = "MOCK fixture ranking (no semantic model)"
            results.append(
                base.model_copy(
                    update={
                        "score": float(score),
                        "reason": base.reason or reason,
                    }
                )
            )
        return results


_ACTIVE_INDEX: ShotRetrievalIndex | None = None
_CACHE_DIR_OVERRIDE: Path | None = None
_MOCKS_PATH_OVERRIDE: Path | None = None


def configure_index(
    index: ShotRetrievalIndex | None = None,
    *,
    cache_dir: str | Path | None = None,
    mocks_path: str | Path | None = None,
) -> None:
    """Configure or reset the active ShotRetrievalIndex instance."""
    global _ACTIVE_INDEX, _CACHE_DIR_OVERRIDE, _MOCKS_PATH_OVERRIDE
    _ACTIVE_INDEX = index
    _CACHE_DIR_OVERRIDE = Path(cache_dir) if cache_dir is not None else None
    _MOCKS_PATH_OVERRIDE = Path(mocks_path) if mocks_path is not None else None


def get_active_index() -> ShotRetrievalIndex:
    global _ACTIVE_INDEX
    if _ACTIVE_INDEX is None:
        if _use_mocks_enabled():
            _ACTIVE_INDEX = ShotRetrievalIndex.from_mocks(
                _MOCKS_PATH_OVERRIDE or DEFAULT_MOCKS_PATH
            )
        else:
            _ACTIVE_INDEX = ShotRetrievalIndex.from_cache_dir(
                _CACHE_DIR_OVERRIDE or DEFAULT_CACHE_DIR
            )
    return _ACTIVE_INDEX


def get_shot(shot_id: str) -> Shot:
    return get_active_index().get_shot(shot_id)


def check_shot(shot_id, focal_mm=24.0, frame_width_m=6.0):
    return get_active_index().check_shot(shot_id, focal_mm, frame_width_m)


def search_shots(
    query_text: str | None = None,
    query_shot_id: str | None = None,
    property_ids: Sequence[str] | None = None,
    min_area_m2: float | None = None,
    min_ceiling_m: float | None = None,
    min_depth_m: float | None = None,
    k: int = 200,
) -> list[Shot]:
    return get_active_index().search_shots(
        query_text=query_text,
        query_shot_id=query_shot_id,
        property_ids=property_ids,
        min_area_m2=min_area_m2,
        min_ceiling_m=min_ceiling_m,
        min_depth_m=min_depth_m,
        k=k,
    )
