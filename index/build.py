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

def cache_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to((ROOT / 'cache').resolve()):
        raise ValueError('Source and output images must stay inside cache/')
    return path

def prepare(manifest_path):
    rows = json.loads(cache_path(manifest_path).read_text(encoding='utf-8'))
    if isinstance(rows, dict):
        rows = rows['records']
    shots = []
    for row in rows:
        for key in ('property_id', 'model_id', 'sweep_id'):
            if not re.fullmatch(r'[A-Za-z0-9_-]+', row[key]):
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
                sweep_id=row['sweep_id'], heading_deg=heading, image_path='/' + target.relative_to(ROOT).as_posix(),
                room_area_m2=row.get('room_area_m2'), ceiling_m=row.get('ceiling_m'),
                depth_m=row.get('depth_m') if row['format'] == 'perspective' else None,
                measure_on_site=row.get('measure_on_site', True)))
    if not shots:
        raise ValueError('Empty image export')
    if len({s.shot_id for s in shots}) != len(shots):
        raise ValueError('Duplicate exported views')
    return shots

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
