"""Shared offline fixtures for the integration-readiness audit tests.

No network, no credentials, no model weights: indexes are built from
controlled vectors and an injected fake text encoder, providers are fake
sessions. Nothing here reads the private cache/ of the machine running it.
"""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from PIL import Image

from contracts.schemas import Shot
from index.search import DEFAULT_EMBEDDING_MODEL, ShotRetrievalIndex

# Fake CLIP space: 3 axes = (brick/warehouse, glass/office, wood/apartment).
VOCAB = {"brick": 0, "warehouse": 0, "glass": 1, "office": 1, "lobby": 1,
         "wood": 2, "apartment": 2, "kitchen": 2}


def fake_text_encoder(text: str) -> np.ndarray:
    vec = np.full(3, 0.01, dtype=np.float32)
    for word in text.lower().split():
        if word in VOCAB:
            vec[VOCAB[word]] += 1.0
    return vec


def shot(shot_id, property_id, *, model_id=None, depth_m=10.0, ceiling_m=3.0,
         room_area_m2=50.0, measure_on_site=False, heading_deg=0.0, image_path=None, sweep_id=None):
    return Shot(
        shot_id=shot_id, model_id=model_id or f"m-{property_id}",
        sweep_id=sweep_id or f"sw-{shot_id}", heading_deg=heading_deg,
        image_path=image_path or f"/cache/views/{shot_id}.jpg", property_id=property_id,
        room_area_m2=room_area_m2, ceiling_m=ceiling_m, depth_m=depth_m,
        measure_on_site=measure_on_site,
    )


def make_index(rows):
    """rows: list of (Shot, vector)."""
    shots = [r[0] for r in rows]
    vectors = np.array([r[1] for r in rows], dtype=np.float32)
    return ShotRetrievalIndex(shots, vectors, text_encoder=fake_text_encoder)


def write_generation(directory: Path, shots, vectors, *, manifest: Any = None,
                     shots_text: str | None = None, embeddings_bytes: bytes | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "embedding_model": DEFAULT_EMBEDDING_MODEL,
                "row_count": len(shots)} if manifest is None else manifest
    (directory / "manifest.json").write_text(
        manifest if isinstance(manifest, str) else json.dumps(manifest), encoding="utf-8")
    (directory / "shots.json").write_text(
        shots_text if shots_text is not None else json.dumps([s.model_dump() for s in shots]),
        encoding="utf-8")
    if embeddings_bytes is not None:
        (directory / "embeddings.npy").write_bytes(embeddings_bytes)
    else:
        np.save(directory / "embeddings.npy", np.asarray(vectors), allow_pickle=False)
    return directory


def jpeg_bytes(color=(120, 140, 160), size=(16, 16)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG")
    return buf.getvalue()


class FakeResponse:
    def __init__(self, status_code=200, *, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.headers = dict(headers or {})

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class FakeGraph:
    def __init__(self, handler):
        self.handler, self.calls = handler, 0

    def post(self, url, *, json=None, auth=None, timeout=15.0, follow_redirects=False):
        self.calls += 1
        return self.handler(json["variables"]["id"])


class FakeCdn:
    def __init__(self, handler):
        self.handler, self.calls = handler, 0

    def get(self, url, *, timeout=15.0, follow_redirects=False, stream=False):
        self.calls += 1
        return self.handler(url)


def pano(model_id: str, sweep: str, *, x=0.0, status="available"):
    return {"id": sweep, "label": None, "position": {"x": x, "y": 0, "z": 0},
            "skybox": {"status": status,
                       "children": [f"https://cdn.example.com/{model_id}/{sweep}/{i}.jpg?t=SIGNED-SECRET"
                                    for i in range(6)]}}


def panos_body(model_id: str, sweeps=("s1",), status="available") -> Mapping[str, Any]:
    """Sweeps are 5 m apart so the importer's 0.5 m spatial sampling keeps all of them."""
    return {"data": {"model": {"panoLocations": [
        pano(model_id, sweep, x=5.0 * i, status=status) for i, sweep in enumerate(sweeps)]}}}


def public_dns(_host):
    return ["93.184.216.34"]
