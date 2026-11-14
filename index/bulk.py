"""Private, bounded, resumable expansion from exact sponsor property/model pairs.

No licensed rows, image URLs, credentials or contacts are printed. A worker makes
one provider request at a time, so workers is also the total request bound.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

import httpx
import numpy as np

from index import store
from index.build import cache_path, encode_incremental, prepare
from index.matterport import (atomic_write_json, fetch_model_record, ingest_matterport,
                             is_valid_local_image, load_matterport_credentials,
                             MatterportIngestionError)
from index.planning import room_plans
from index.rooms import ROOMS_GRAPHQL_QUERY, enrich_source_manifest

ROOT = store.ROOT
CACHE = ROOT / 'cache/matterport'
COMMERCIAL = {'Office', 'Industrial', 'Flex', 'GeneralRetail'}


def _integer(value):
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0


def catalog_exclusion_reason(linked, recorded_failures):
    present = [model for model in linked if model]
    if not present:
        return 'catalog_missing'
    positive = [model for model in present if _integer(model.get('pano_count')) > 0]
    if not positive:
        return 'catalog_has_no_panoramas'
    if all(model['sid'] in recorded_failures for model in positive):
        return 'recorded_model_failures'
    return 'no_eligible_catalog_selection'


def select_models(rows, catalog, existing_shots=(), multifamily_count=20, unavailable_models=()):
    """One explicit catalog SID per property; retain supplied shared associations.

    Metadata helps choose useful coverage but is not a visual quality judgement.
    Multifamily is balanced across cities and spread across geography/era/size.
    """
    catalog = {r['sid']: r for r in catalog}
    existing = {(s.property_id, s.model_id) for s in existing_shots}
    unavailable_models = set(unavailable_models)
    candidates = defaultdict(list)
    properties = {}
    for row in rows:
        if not row['available'] or row['availability_status'] != 'available':
            continue
        if row['city'] not in {'Los Angeles', 'Houston'} or row['type'] not in COMMERCIAL | {'Multifamily'}:
            continue
        properties[row['property_id']] = row
        model = catalog.get(row['model_id'])
        if model is None or _integer(model['pano_count']) < 1:
            continue
        candidates[row['property_id']].append(model)

    def rank(pid, model):
        n = _integer(model['pano_count'])
        return ((pid, model['sid']) in existing, model['sid'] not in unavailable_models, n >= 8,
                model.get('defurnished') == 'no',
                model.get('costar_property_id') in ('', pid),
                model.get('costar_property_id') == pid,
                min(_integer(model.get('room_count')), 12),
                min(_integer(model.get('floor_count')), 3),
                -abs(min(n, 64) - 24), model['sid'])

    chosen = {}
    for pid, models in candidates.items():
        model = max(models, key=lambda m: rank(pid, m))
        row = properties[pid]
        chosen[pid] = {'property_id': pid, 'model_id': model['sid'],
            'city': row['city'], 'type': row['type'],
            'pano_count': _integer(model['pano_count']),
            'catalog_disagreement': model.get('costar_property_id') not in ('', pid),
            'metadata_selection_only': True,
            'alternatives': [m['sid'] for m in sorted(models, key=lambda m: rank(pid, m), reverse=True)
                             if m['sid'] != model['sid']]}

    selected = [r for r in chosen.values() if r['type'] in COMMERCIAL]
    multi = [r for r in chosen.values() if r['type'] == 'Multifamily' and r['pano_count'] >= 8
             and r['model_id'] not in unavailable_models]
    # Existing available apartments count toward the requested ~20, and all other
    # previously indexed properties are independently retained at publication.
    picked = [r for r in multi if (r['property_id'], r['model_id']) in existing]
    picked = sorted(picked, key=lambda r: r['property_id'])[:multifamily_count]
    while len(picked) < min(multifamily_count, len(multi)):
        remaining = [r for r in multi if r not in picked]
        def diversity(r):
            p = properties[r['property_id']]
            same_city = sum(s['city'] == r['city'] for s in picked)
            peers = [properties[s['property_id']] for s in picked if s['city'] == r['city']]
            geographic = min(((p['lat']-s['lat'])**2 + (p['lon']-s['lon'])**2
                              for s in peers), default=1.)
            era = (p.get('year_built') or 0) // 20
            era_count = sum((s.get('year_built') or 0) // 20 == era for s in peers)
            size = max(float(p.get('size_sqft') or 1), 1.)
            size_gap = min((abs(np.log(size / max(float(s.get('size_sqft') or 1), 1.)))
                            for s in peers), default=1.)
            return (-same_city, geographic, -era_count, size_gap, r['property_id'])
        picked.append(max(remaining, key=diversity))
    selected.extend(picked)
    return sorted(selected, key=lambda r: (r['type'] == 'Multifamily', r['city'], r['type'], r['property_id']))


def missing_mapping_counts():
    """Audit available source properties omitted from the pair-grain join."""
    from data.build_join import CITIES, _listing_properties, availability
    kit = ROOT / 'cache/costar-hackathon-kit'
    enums = json.loads((kit / 'schemas/enums.json').read_text())
    listings = defaultdict(list)
    for line in (kit / 'data/commercial-listing-summary.jsonl').open():
        listing = json.loads(line)
        for pid in _listing_properties(listing):
            listings[pid].append(listing)
    with (kit / 'commercial-properties.csv').open(newline='') as source:
        mapped = {r['PropertyId'] for r in csv.DictReader(source) if r['MatterportModelId'].strip()}
    counts = Counter()
    for line in (kit / 'data/commercial-property.jsonl').open():
        record = json.loads(line)
        pid = str(record['id'])
        city = CITIES.get(str((record.get('primaryAddress') or {}).get('city') or '').strip().casefold())
        kind = enums['PropertyType'].get(str(record.get('propertyType')))
        if city and kind in COMMERCIAL and pid not in mapped and availability(pid, listings[pid], enums)[0] == 'available':
            counts[f'{city}/{kind}'] += 1
    return dict(sorted(counts.items()))


def load_previous():
    directory = store.index_dir()
    name = (directory / 'CURRENT').read_text().strip()
    if not name or any(c not in '0123456789abcdef' for c in name):
        raise ValueError('Invalid current index generation')
    generation = directory / name
    manifest = json.loads((generation / 'manifest.json').read_text())
    if manifest['embedding_model'] != store.DEFAULT_MODEL:
        raise ValueError('Existing embeddings use a different model')
    from contracts.schemas import Shot
    shots = [Shot.model_validate(r) for r in json.loads((generation / 'shots.json').read_text())]
    vectors = np.load(generation / 'embeddings.npy', allow_pickle=False)
    if len(shots) != len(vectors) or not np.isfinite(vectors).all():
        raise ValueError('Existing shot/vector alignment is invalid')
    return shots, vectors, name


class _DeadlineClient:
    """Keep each request within the remaining fetch-stage budget."""
    def __init__(self, client, deadline):
        self.client, self.deadline = client, deadline

    def _request(self, method, url, kwargs):
        if self.deadline is not None:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise MatterportIngestionError('Fetch deadline reached')
            kwargs['timeout'] = min(float(kwargs.get('timeout', 10)), remaining)
        return getattr(self.client, method)(url, **kwargs)

    def post(self, url, **kwargs):
        return self._request('post', url, kwargs)

    def get(self, url, **kwargs):
        return self._request('get', url, kwargs)


def ingest_one(model_id, property_id, *, auth, max_sweeps, timeout, deadline=None):
    """Independent model directories avoid shared-manifest writes among workers."""
    directory = CACHE / 'bulk' / model_id
    completed = directory / 'completed.json'
    if completed.is_file():
        state = json.loads(completed.read_text())
        manifest = json.loads((directory / 'source_manifest.json').read_text())
        if (state.get('max_sweeps') == max_sweeps and not state.get('shots_failed')
                and not state.get('sweeps_skipped') and manifest.get('records') and all(
                is_valid_local_image(directory / r['image_path']) for r in manifest['records'])):
            return {**state, 'resumed': True, 'shots_written': 0,
                    'shots_resumed': len(manifest['records'])}
        completed.unlink(missing_ok=True)
    directory.mkdir(parents=True, exist_ok=True)
    models_path = directory / 'models.json'
    atomic_write_json(models_path, [{'model_id': model_id, 'property_id': property_id}])
    try:
        with httpx.Client() as graph, httpx.Client() as cdn:
            manifest, report = ingest_matterport(models_path=models_path, output_dir=directory,
                max_models=1, max_sweeps=max_sweeps, timeout=timeout, max_retries=1, auth=auth,
                graph_session=_DeadlineClient(graph, deadline),
                cdn_session=_DeadlineClient(cdn, deadline))
    except Exception as exc:
        state = {'model_id': model_id, 'ok': False, 'error_type': type(exc).__name__}
        atomic_write_json(directory / 'failure.json', state)
        return state
    room_failure = False
    plans = {}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            model = fetch_model_record(_DeadlineClient(client, deadline), model_id=model_id, auth=auth,
                query=ROOMS_GRAPHQL_QUERY, timeout=timeout, max_retries=1)
        payload = {model_id: {'data': {'model': model}}}
        manifest = enrich_source_manifest(manifest, payload)
        plans = room_plans(payload)
    except Exception:
        room_failure = True
    atomic_write_json(directory / 'source_manifest.json', manifest)
    atomic_write_json(directory / 'room-plans.json', plans)
    complete = report.shots_failed == 0 and report.sweeps_skipped == 0
    state = {'model_id': model_id, 'ok': complete, 'usable': True, 'records': len(manifest['records']),
             'max_sweeps': max_sweeps, 'room_failure': room_failure,
             'shots_written': report.shots_written, 'shots_resumed': report.shots_resumed,
             'shots_failed': report.shots_failed, 'sweeps_skipped': report.sweeps_skipped}
    atomic_write_json(completed if complete else directory / 'partial.json', state)
    return state


def _view_key(row):
    return (row.get('property_id'), row.get('model_id'), row.get('sweep_id'), row.get('heading_deg'))


def model_tasks(selection, indexed_shots, source_records, max_sweeps):
    """Retry partial checkpoints and grow smaller captures without refetching all models."""
    indexed_pairs = {(s.property_id, s.model_id) for s in indexed_shots}
    source_by_pair = defaultdict(list)
    for row in source_records:
        source_by_pair[row['property_id'], row['model_id']].append(row)
    tasks = {}
    for item in selection:
        pid, mid = item['property_id'], item['model_id']
        directory = CACHE / 'bulk' / mid
        completed = directory / 'completed.json'
        if completed.is_file():
            state = json.loads(completed.read_text())
            complete = (state.get('max_sweeps', 0) >= max_sweeps
                        and not state.get('shots_failed') and not state.get('sweeps_skipped'))
            if complete:
                # A missing index pair can be repaired from this checkpoint.
                if ((pid, mid) not in indexed_pairs
                        or len(source_by_pair.get((pid, mid), [])) < state.get('records', 0)):
                    tasks.setdefault(mid, pid)
                continue
        if (directory / 'partial.json').is_file():
            tasks.setdefault(mid, pid)
            continue
        rows = source_by_pair.get((pid, mid), [])
        faces = defaultdict(set)
        for row in rows:
            faces[row['sweep_id']].add(row.get('heading_deg'))
        enough = (len(faces) >= min(max_sweeps, item['pano_count'])
                  and all(len(headings) == 4 for headings in faces.values()))
        if not enough:
            tasks.setdefault(mid, pid)
    return tasks


def merge_records(previous, selection, successful_models, indexed_shots=None):
    """Keep old records intact; fan out shared imagery only to supplied exact pairs."""
    records = list(previous['records'])
    existing_keys = {_view_key(r) for r in records}
    selected_pairs = {(r['property_id'], r['model_id']) for r in selection}
    if indexed_shots is None:
        indexed_keys = existing_keys
    else:
        indexed_keys = {(s.property_id, s.model_id, s.sweep_id, s.heading_deg) for s in indexed_shots
                        if cache_path(s.image_path.lstrip('/')).is_file()}
    plans_path = CACHE / 'room-plans.json'
    plans = json.loads(plans_path.read_text()) if plans_path.is_file() else {}
    # Source publication may have succeeded before an interrupted index publish.
    # Those source views must be prepared even though their property pair exists.
    added = [r for r in records if (r['property_id'], r['model_id']) in selected_pairs
             and _view_key(r) not in indexed_keys]
    for item in selection:
        pid, mid = item['property_id'], item['model_id']
        if mid not in successful_models:
            continue
        directory = CACHE / 'bulk' / mid
        manifest = json.loads((directory / 'source_manifest.json').read_text())
        for row in manifest['records']:
            copied = dict(row)
            copied['property_id'] = pid
            copied['shot_id'] = pid + '__' + row['shot_id']
            copied['image_path'] = (directory / row['image_path']).relative_to(CACHE).as_posix()
            copied['provenance'] = {**row.get('provenance', {}),
                'join_method': 'sponsor_csv_property_id_and_model_id',
                'catalog_disagreement': item['catalog_disagreement']}
            identity = _view_key(copied)
            if identity not in existing_keys:
                records.append(copied)
                added.append(copied)
                existing_keys.add(identity)
        model_plans = directory / 'room-plans.json'
        if model_plans.is_file():
            plans.update(json.loads(model_plans.read_text()))
    return records, added, plans


def run(args):
    import duckdb
    started = time.monotonic()
    if not 1 <= args.workers <= 8 or not 1 <= args.max_sweeps <= 12:
        raise ValueError('workers must be 1..8 and max-sweeps 1..12')
    if (args.batch_size < 1 or not math.isfinite(args.fetch_minutes) or args.fetch_minutes <= 0
            or not math.isfinite(args.timeout) or args.timeout <= 0 or args.multifamily < 0):
        raise ValueError('Batch size, time limits and timeout must be positive; multifamily must be nonnegative')
    previous_shots, previous_vectors, previous_generation = load_previous()
    previous = json.loads((CACHE / 'source_manifest.json').read_text())
    with (CACHE / 'models_index.csv').open(newline='') as source:
        catalog = list(csv.DictReader(source))
    with duckdb.connect(':memory:') as database:
        columns = ('property_id', 'model_id', 'city', 'type', 'available', 'availability_status',
                   'lat', 'lon', 'year_built', 'size_sqft')
        rows = [dict(zip(columns, values)) for values in database.execute(
            'SELECT DISTINCT ' + ','.join(columns) + ' FROM read_parquet(?)',
            [str(ROOT / 'cache/join.parquet')]).fetchall()]
    recorded_failures = {p.parent.name for p in (CACHE / 'bulk').glob('*/failure.json')
                         if not (p.parent / 'completed.json').is_file()}
    unavailable_models = set() if getattr(args, 'retry_failed', False) else recorded_failures
    selection = select_models(rows, catalog, previous_shots, args.multifamily, unavailable_models)
    commercial_targets = {r['property_id'] for r in rows if r['available']
        and r['availability_status'] == 'available' and r['type'] in COMMERCIAL
        and r['city'] in {'Los Angeles', 'Houston'}}
    selected_commercial = {r['property_id'] for r in selection if r['type'] in COMMERCIAL}
    catalog_models = {r['sid']: r for r in catalog}
    excluded_reasons = Counter()
    for pid in commercial_targets - selected_commercial:
        linked = [catalog_models.get(r['model_id']) for r in rows if r['property_id'] == pid]
        excluded_reasons[catalog_exclusion_reason(linked, recorded_failures)] += 1
    missing = missing_mapping_counts()
    atomic_write_json(CACHE / 'bulk-selection.json', {'models': selection,
        'missing_mapping_counts': missing, 'previous_generation': previous_generation})
    tasks = model_tasks(selection, previous_shots, previous['records'], args.max_sweeps)
    summary = {'selected_properties': len(selection), 'selected_by_city_type': dict(Counter(
        f"{r['city']}/{r['type']}" for r in selection)), 'unique_models_to_fetch': len(tasks),
        'missing_mapping': sum(missing.values()), 'catalog_disagreements': sum(r['catalog_disagreement'] for r in selection),
        'catalog_fewer_than_8_sweeps': sum(r['pano_count'] < 8 for r in selection),
        'retained_shots': len(previous_shots), 'workers': args.workers,
        'recorded_model_failures': len(recorded_failures),
        'retry_failed': getattr(args, 'retry_failed', False),
        'mapped_commercial_properties': len(commercial_targets),
        'catalog_excluded_properties': len(commercial_targets - selected_commercial),
        'catalog_excluded_reasons': dict(excluded_reasons)}
    print(json.dumps({'event': 'selection', **summary}), flush=True)
    if args.plan_only:
        return summary
    auth = load_matterport_credentials(ROOT / '.env')
    results = {}
    # Only a successful bulk checkpoint backs the new-property fanout below.
    # An old model in the published index is not proof that bulk/<sid> exists.
    successful = set()
    iterator = iter(tasks.items())
    deadline = started + args.fetch_minutes * 60
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {}
        def submit_next():
            if time.monotonic() >= deadline:
                return False
            try:
                mid, pid = next(iterator)
            except StopIteration:
                return False
            future = pool.submit(ingest_one, mid, pid, auth=auth,
                max_sweeps=args.max_sweeps, timeout=args.timeout, deadline=deadline)
            pending[future] = mid
            return True
        for _ in range(args.workers):
            submit_next()
        while pending:
            completed, _ = wait(pending, timeout=30, return_when=FIRST_COMPLETED)
            if not completed:
                print(json.dumps({'event': 'fetch_progress', 'completed': len(results),
                    'active': len(pending), 'elapsed_sec': round(time.monotonic()-started, 1)}), flush=True)
            for future in completed:
                mid = pending.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    result = {'model_id': mid, 'ok': False, 'error_type': type(exc).__name__}
                results[mid] = result
                if result.get('ok') or result.get('resumed') or result.get('usable'):
                    successful.add(mid)
                submit_next()
            if completed and (len(results) % 8 == 0 or not pending):
                print(json.dumps({'event': 'fetch_progress', 'completed': len(results),
                    'succeeded': sum(r.get('ok', False) or r.get('resumed', False) for r in results.values()),
                    'images': sum(r.get('records', 0) for r in results.values()),
                    'elapsed_sec': round(time.monotonic()-started, 1)}), flush=True)
    atomic_write_json(CACHE / 'bulk-fetch-report.json', results)
    all_records, added, plans = merge_records(previous, selection, successful, previous_shots)
    source = {**previous, 'generated_at': datetime.now(timezone.utc).isoformat(), 'records': all_records,
        'summary': {'models_requested': len(results), 'models_succeeded': sum(
            bool(r.get('ok') or r.get('resumed')) for r in results.values()),
            'models_failed': sum(not (r.get('ok') or r.get('resumed')) for r in results.values()),
            'shots_written': sum(r.get('shots_written', 0) for r in results.values()),
            'shots_resumed': sum(r.get('shots_resumed', 0) for r in results.values()),
            'shots_failed': sum(r.get('shots_failed', 0) for r in results.values()),
            'errors': []}}
    additions_path = CACHE / 'bulk-additions.json'
    atomic_write_json(additions_path, {'records': added})
    new_shots = prepare(additions_path, preserve_provenance=True) if added else []
    old_ids = {s.shot_id for s in previous_shots}
    new_shots = [s for s in new_shots if s.shot_id not in old_ids]
    print(json.dumps({'event': 'prepared', 'new_shots': len(new_shots),
                      'elapsed_sec': round(time.monotonic()-started, 1)}), flush=True)
    last_report = [0.]
    def progress(done, total):
        if time.monotonic() - last_report[0] >= 20 or done == total:
            print(json.dumps({'event': 'encode_progress', 'encoded_unique': done,
                'total_unique': total, 'elapsed_sec': round(time.monotonic()-started, 1)}), flush=True)
            last_report[0] = time.monotonic()
    new_vectors = encode_incremental(new_shots, previous_shots=previous_shots,
        previous_vectors=previous_vectors, progress=progress, batch_size=args.batch_size)
    shots = previous_shots + new_shots
    vectors = np.vstack([previous_vectors, new_vectors]) if new_shots else previous_vectors
    if new_shots:
        store.save_index(shots, vectors, already_normalized=True)
    atomic_write_json(CACHE / 'source_manifest.json', source)
    atomic_write_json(CACHE / 'room-plans.json', plans)
    indexed_pairs = {(s.property_id, s.model_id) for s in shots}
    covered = [r for r in selection if (r['property_id'], r['model_id']) in indexed_pairs]
    summary.update({'models_attempted': len(results), 'models_not_attempted': len(tasks)-len(results),
        'models_failed': sum(
        not (r.get('ok') or r.get('resumed')) for r in results.values()),
        'models_degraded': sum(bool(r.get('usable')) and not (r.get('ok') or r.get('resumed'))
                               for r in results.values()),
        'properties_covered': len(covered), 'properties_uncovered': len(selection)-len(covered)
            + len(commercial_targets - selected_commercial),
        'covered_by_city_type': dict(Counter(f"{r['city']}/{r['type']}" for r in covered)),
        'shots': len(shots), 'new_shots': len(new_shots), 'index_published': bool(new_shots),
        'distinct_properties': len({s.property_id for s in shots}),
        'distinct_models': len({s.model_id for s in shots}),
        'elapsed_sec': round(time.monotonic()-started, 1)})
    atomic_write_json(CACHE / 'bulk-report.json', summary)
    print(json.dumps({'event': 'complete', **summary}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--max-sweeps', type=int, default=8)
    parser.add_argument('--multifamily', type=int, default=20)
    parser.add_argument('--fetch-minutes', type=float, default=40)
    parser.add_argument('--timeout', type=float, default=10)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--retry-failed', action='store_true',
                        help='Allow candidates with recorded provider/transport failures again.')
    args = parser.parse_args()
    try:
        summary = run(args)
        if (summary.get('properties_uncovered', 0) or summary.get('models_not_attempted', 0)
                or summary.get('models_degraded', 0) or summary.get('models_failed', 0)):
            raise SystemExit(2)
    except Exception as exc:
        print(json.dumps({'event': 'failed', 'error_type': type(exc).__name__}), flush=True)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
