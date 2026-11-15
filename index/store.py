"""Versioned, credential-free local shot index; licensed assets stay in cache/."""
import json
import os
from pathlib import Path
import numpy as np
from contracts.schemas import Shot

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = 'sentence-transformers/clip-ViT-B-32'

def index_dir():
    path = Path(os.getenv('TYPECAST_INDEX_DIR', str(ROOT / 'cache/shot-index'))).resolve()
    if not path.is_relative_to((ROOT / 'cache').resolve()):
        raise ValueError('TYPECAST_INDEX_DIR must be inside cache/')
    return path

def normalize(vectors):
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2 or not np.isfinite(vectors).all():
        raise ValueError('Expected finite 2D embeddings')
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms <= 0):
        raise ValueError('Zero embedding')
    return vectors / norms

def save_index(shots, vectors, model_name=DEFAULT_MODEL, *, already_normalized=False):
    if already_normalized:
        vectors = np.asarray(vectors, dtype=np.float32)
        if (vectors.ndim != 2 or not np.isfinite(vectors).all()
                or not np.allclose(np.linalg.norm(vectors, axis=1), 1., atol=1e-5)):
            raise ValueError('Expected finite normalized embeddings')
    else:
        vectors = normalize(vectors)
    if len(shots) != len(vectors) or not shots:
        raise ValueError('Nonempty shots and vectors must have equal length')
    if len({s.shot_id for s in shots}) != len(shots):
        raise ValueError('Duplicate shot id')
    # Publish only complete immutable generations; readers see old or new, never mixed.
    import uuid
    directory = index_dir(); directory.mkdir(parents=True, exist_ok=True)
    generation = directory / uuid.uuid4().hex
    generation.mkdir()
    np.save(generation / 'embeddings.npy', vectors, allow_pickle=False)
    (generation / 'shots.json').write_text(json.dumps([s.model_dump() for s in shots]), encoding='utf-8')
    (generation / 'manifest.json').write_text(json.dumps({'version': 1, 'embedding_model': model_name,
        'row_count': len(shots)}), encoding='utf-8')
    pending = directory / ('current-' + generation.name)
    pending.write_text(generation.name, encoding='utf-8')
    pending.replace(directory / 'CURRENT')

def load_index():
    directory = index_dir()
    try:
        pointer = directory / 'CURRENT'
        if pointer.is_file():
            name = pointer.read_text().strip()
            if not name or any(c not in '0123456789abcdef' for c in name):
                raise ValueError('Invalid generation')
            generation = directory / name
        else:
            # TYPECAST_INDEX_DIR may pin an immutable generation for evaluation.
            generation = directory
        manifest = json.loads((generation / 'manifest.json').read_text(encoding='utf-8'))
        if manifest['version'] != 1:
            raise ValueError('Unsupported index version')
        shots = [Shot.model_validate(s) for s in json.loads((generation / 'shots.json').read_text(encoding='utf-8'))]
        vectors = normalize(np.load(generation / 'embeddings.npy', allow_pickle=False))
        if len(shots) != len(vectors) or len({s.shot_id for s in shots}) != len(shots):
            raise ValueError('Corrupt shot/vector alignment')
        return shots, vectors, manifest['embedding_model']
    except FileNotFoundError as exc:
        raise RuntimeError('No real shot index. Follow index/README.md; mocks are not a live fallback.') from exc

def encoder(model_name):
    from functools import lru_cache
    return _encoder(model_name)

from functools import lru_cache
@lru_cache(maxsize=2)
def _encoder(model_name):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError('Install optional index/requirements.txt for CLIP encoding') from exc
    return SentenceTransformer(model_name)

def encode_text(text, model_name):
    return normalize(encoder(model_name).encode([text]))[0]
