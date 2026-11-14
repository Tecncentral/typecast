"""Build from a sponsor-authorized LOCAL image export, not an invented API endpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import math
import numpy as np
from PIL import Image
from contracts.schemas import Shot
from index.cut_views import cut_all
from index.store import ROOT, DEFAULT_MODEL, encoder, save_index
from index.matterport import atomic_write_json

def cache_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to((ROOT / 'cache').resolve()):
        raise ValueError('Source and output images must stay inside cache/')
    return path


def _dimension(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and number > 0 else None

def prepare(manifest_path, *, preserve_provenance=False):
    rows = json.loads(cache_path(manifest_path).read_text(encoding='utf-8'))
    if isinstance(rows, dict):
        rows = rows['records']
    shots = []
    provenance = {}
    if preserve_provenance:
        path = cache_path('cache/view-provenance.json')
        if path.is_file():
            provenance = json.loads(path.read_text(encoding='utf-8'))
    for row in rows:
        for key in ('property_id', 'model_id', 'sweep_id'):
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', row[key]):
                raise ValueError('Identifiers must be filesystem-safe')
        raw_source = Path(row['image_path'])
        source = cache_path(raw_source if raw_source.is_absolute() or raw_source.parts[0] == 'cache'
                            else cache_path(manifest_path).parent / raw_source)
        with Image.open(source) as image:
            array = np.asarray(image.convert('RGB'))
        if row['format'] == 'equirectangular':
            if not 1.9 <= array.shape[1] / array.shape[0] <= 2.1:
                raise ValueError('Expected 2:1 equirectangular panorama; cube faces are unsupported')
            # Explicit alignment required: image center longitude need not be true north.
            offset = float(row['heading_offset_deg'])
            if not math.isfinite(offset):
                raise ValueError('Invalid heading offset')
            views = [((yaw + offset) % 360, pixels) for yaw, pixels in cut_all(array)]
        elif row['format'] == 'perspective':
            heading = float(row['heading_deg'])
            if not math.isfinite(heading):
                raise ValueError('Invalid heading')
            views = [(heading % 360, array)]
        else:
            raise ValueError('Unsupported image format')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
        for heading, pixels in views:
            identity = f"{row['property_id']}-{row['model_id']}-{row['sweep_id']}-{heading:.3f}-{digest}"
            target = cache_path(f'cache/views/{identity}.jpg')
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                Image.fromarray(pixels).save(target, quality=90)
            shots.append(Shot(shot_id=identity, property_id=row['property_id'], model_id=row['model_id'],
                sweep_id=row['sweep_id'], heading_deg=heading,
                image_path='/cache/' + target.relative_to((ROOT / 'cache').resolve()).as_posix(),
                room_area_m2=_dimension(row.get('room_area_m2')), ceiling_m=_dimension(row.get('ceiling_m')),
                depth_m=_dimension(row.get('depth_m')) if row['format'] == 'perspective' else None,
                measure_on_site=row.get('measure_on_site', True) or any(
                    row.get(key) is not None and _dimension(row.get(key)) is None
                    for key in ('room_area_m2', 'ceiling_m', 'depth_m'))))
            provenance[identity] = {**row.get('provenance', {}),
                'room_id': row.get('room_id'), 'floor_id': row.get('floor_id'),
                'classification': row.get('classification'), 'source_digest': digest}
    if not shots:
        raise ValueError('Empty image export')
    if len({s.shot_id for s in shots}) != len(shots):
        raise ValueError('Duplicate exported views')
    atomic_write_json(cache_path('cache/view-provenance.json'), provenance)
    return shots


def encode_incremental(shots, *, previous_shots=(), previous_vectors=None,
                       model_name=DEFAULT_MODEL, batch_size=16, progress=None):
    """Encode new source views once, including scans shared by explicit properties.

    The image digest is part of prepared shot identities. Property-specific copies
    can therefore share a vector without assuming two different source files match.
    Existing rows are returned unchanged; callers must check the embedding model.
    """
    def key(shot):
        return (shot.model_id, shot.sweep_id, shot.heading_deg,
                shot.shot_id.rsplit('-', 1)[-1])
    cached = {}
    if previous_vectors is not None:
        if len(previous_shots) != len(previous_vectors):
            raise ValueError('Previous shots and embeddings must align')
        cached.update((key(shot), vector) for shot, vector in zip(previous_shots, previous_vectors))
    pending = {}
    for shot in shots:
        if key(shot) not in cached:
            pending.setdefault(key(shot), shot)
    unique = list(pending.items())
    for start in range(0, len(unique), batch_size):
        batch = unique[start:start + batch_size]
        images = []
        try:
            for _, shot in batch:
                with Image.open(cache_path(shot.image_path.lstrip('/'))) as image:
                    images.append(image.convert('RGB'))
            vectors = np.asarray(encoder(model_name).encode(images, batch_size=batch_size,
                convert_to_numpy=True, normalize_embeddings=True), dtype=np.float32)
            cached.update((identity, vector) for (identity, _), vector in zip(batch, vectors))
        finally:
            for image in images:
                image.close()
        if progress:
            progress(min(start + batch_size, len(unique)), len(unique))
    if not shots:
        return np.empty((0, previous_vectors.shape[1] if previous_vectors is not None else 0), dtype=np.float32)
    return np.asarray([cached[key(shot)] for shot in shots], dtype=np.float32)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', help='Private cache/export.json')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    shots = prepare(args.manifest)
    output = cache_path('cache/prepared-shots.json')
    output.write_text(json.dumps([s.model_dump() for s in shots], indent=2), encoding='utf-8')
    if not args.prepare_only:
        batches = []
        for start in range(0, len(shots), 16):
            images = []
            for shot in shots[start:start + 16]:
                with Image.open(cache_path(shot.image_path.lstrip('/'))) as image:
                    images.append(image.convert('RGB'))
            batches.append(encoder(DEFAULT_MODEL).encode(images, batch_size=16, show_progress_bar=True))
            for image in images:
                image.close()
        vectors = np.concatenate(batches)
        save_index(shots, vectors)
    print(f'Prepared {len(shots)} views; indexed={not args.prepare_only}')

if __name__ == '__main__':
    main()
