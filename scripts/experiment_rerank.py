"""Cold-vision experiments on five frozen TUNE scenes; --execute makes live calls.

Paid image calls reserve a persistent, file-locked budget before each request.
Interrupted reservations are never refunded. No test exports or v1 reports are
read or rewritten. Each attempt gets a fresh score-cache directory and process.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import inspect
import json
import math
import os
from pathlib import Path
import signal
from statistics import median
import subprocess
import sys
import tempfile
from threading import RLock, local
from time import perf_counter
from uuid import uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TUNE_IDS = frozenset(f'interior-{n}' for n in range(16, 21))
HARD_IMAGE_LIMIT = 1000
REQUEST_LIMIT_S = 90.
_LEDGER_LOCK = RLock()


class ExperimentStop(RuntimeError):
    """Local budget/rate-limit stop, before an additional provider request."""


def private_path(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to((ROOT / 'cache').resolve()):
        raise ValueError('Experiment inputs and outputs must stay under ignored cache/')
    return path


def atomic_json(path: Path, value) -> None:
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hard_stop() -> datetime:
    return datetime.now(ZoneInfo('America/New_York')).replace(hour=16, minute=30, second=0, microsecond=0)


class Ledger:
    def __init__(self, path: Path):
        self.path = private_path(path)

    @contextmanager
    def transaction(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER_LOCK, self.path.with_suffix('.lock').open('a+b') as lock:
            if os.name == 'nt':
                import msvcrt
                if lock.seek(0, 2) == 0:
                    lock.write(b'0'); lock.flush()
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                value = json.loads(self.path.read_text()) if self.path.exists() else {
                    'version': 1, 'image_limit': HARD_IMAGE_LIMIT, 'images_reserved': 0,
                    'paused': None, 'attempts': {}}
                if (value.get('version') != 1 or value.get('image_limit') != HARD_IMAGE_LIMIT
                        or type(value.get('images_reserved')) is not int
                        or not 0 <= value['images_reserved'] <= HARD_IMAGE_LIMIT
                        or not isinstance(value.get('attempts'), dict)
                        or any(type(r.get('images_reserved')) is not int or r['images_reserved'] < 0
                               for r in value['attempts'].values())
                        or sum(r['images_reserved'] for r in value['attempts'].values()) != value['images_reserved']):
                    raise ValueError('Invalid experiment ledger; refusing calls')
                yield value
                atomic_json(self.path, value)
            finally:
                if os.name == 'nt':
                    lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def snapshot(self):
        with self.transaction() as value:
            return json.loads(json.dumps(value))

    def register(self, attempt: str, metadata: dict):
        with self.transaction() as value:
            if value['paused']:
                raise ExperimentStop('Ledger is paused')
            if attempt in value['attempts']:
                raise ValueError('Attempt already registered')
            value['attempts'][attempt] = {**metadata, 'images_reserved': 0,
                'vision_calls': 0, 'parse_calls': 0, 'http_calls': {}, 'status': 'registered'}

    def reserve(self, attempt: str, images: int):
        if type(images) is not int or images < 0:
            raise ValueError('Image reservation must be a nonnegative integer')
        stopped = False
        with self.transaction() as value:
            if value['paused']:
                stopped = True
            elif value['images_reserved'] + images > HARD_IMAGE_LIMIT:
                value['paused'] = {'reason': 'image_budget', 'at': now(), 'attempt': attempt}
                stopped = True
            else:
                row = value['attempts'][attempt]
                value['images_reserved'] += images
                row['images_reserved'] += images
                role = 'vision_calls' if images else 'parse_calls'
                row[role] += 1
        if stopped:
            raise ExperimentStop('Image budget exhausted or ledger paused')

    def http_call(self, attempt: str, role: str):
        with self.transaction() as value:
            if value['paused']:
                raise ExperimentStop('Ledger is paused')
            calls = value['attempts'][attempt]['http_calls']
            calls[role] = calls.get(role, 0) + 1

    def pause(self, reason: str, attempt: str):
        with self.transaction() as value:
            value['paused'] = value['paused'] or {'reason': reason, 'attempt': attempt, 'at': now()}

    def finish(self, attempt: str, status: str):
        with self.transaction() as value:
            value['attempts'][attempt]['status'] = status


def configuration(value: str) -> dict:
    try:
        pool, concurrency, batch = (int(x) for x in value.split(','))
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('Use POOL,CONCURRENCY,BATCH such as 20,5,5') from None
    if pool not in (10, 20, 30, 40) or concurrency not in (5, 10) or batch not in (1, 5, 10):
        raise argparse.ArgumentTypeError('Pool=10/20/30/40, concurrency=5/10, batch=1/5/10')
    return {'pool': pool, 'concurrency': concurrency, 'batch_size': batch}


def tune_inputs(directory: Path, index_dir: Path):
    from agent.eval.run_eval import read_jsonl
    from agent.eval.label_bridge import validate_live_inputs
    directory = private_path(directory)
    scenes = read_jsonl(directory / 'scenes.jsonl')
    labels = read_jsonl(directory / 'labels.jsonl')
    if (len(scenes) != 5 or {s['id'] for s in scenes} != TUNE_IDS
            or any(s.get('split') != 'tune' for s in scenes)
            or len(labels) != 5 or {s['id'] for s in labels} != TUNE_IDS
            or any(s.get('split') != 'tune' for s in labels)):
        raise ValueError('Only the exact five frozen tune scenes and labels are allowed')
    by_id = {r['id']: r for r in labels}
    pinned = validate_live_inputs(scenes, by_id, private_path(index_dir))
    return scenes, by_id, pinned


def metrics(top10, scene: dict, label: dict) -> dict:
    ids = [s['shot_id'] if isinstance(s, dict) else s for s in top10[:10]]
    gold, pool = set(label['relevant_shot_ids']), set(scene['evaluation']['pool_shot_ids'])
    hits = len(set(ids) & gold)
    return {'recall_at_10': hits / len(gold) if gold else None,
        'precision_lower_bound_at_10': hits / 10, 'recovered_gold': hits,
        'relevant_count': len(gold), 'retrieved_count': len(ids),
        'reviewed_slots': len(set(ids) & pool), 'unjudged_slots': len(set(ids) - pool),
        'missing_slots': 10 - len(ids), 'top10': ids}


def image_count(image) -> int:
    if image is None:
        return 0
    if isinstance(image, str) and image:
        return 1
    if isinstance(image, list) and all(isinstance(x, str) and x for x in image):
        return len(image)
    raise ValueError('Unrecognized provider image payload; refusing budget bypass')


def completed_vision(accounting: list[dict], config: dict) -> bool:
    if len(accounting) != 1:
        return False
    value = accounting[0]
    return (value.get('candidate_count') == value.get('images_scored') == config['pool']
            and value.get('pool') == config['pool']
            and value.get('concurrency') == config['concurrency']
            and value.get('batch_size') == config['batch_size']
            and value.get('failures') == 0 and value.get('cached') == 0
            and not value.get('rate_limited'))


@contextmanager
def provider_budget(ledger: Ledger, attempt: str, *, restore=True):
    """Guard actual calls, including batch/fallback images and deep text 429s."""
    import importlib
    from agent import models
    original = models.ModelProvider._call
    signature = inspect.signature(original)
    role_state = local()
    clients = []
    seen = set()
    for module_name in ('httpx', 'httpx2'):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        # New OpenAI/Anthropic SDKs use httpx2; older SDKs and the ASGI
        # diagnostic client use httpx. Deduplicate aliases if they share classes.
        for client_class, asynchronous in ((module.Client, False), (module.AsyncClient, True)):
            if client_class not in seen:
                seen.add(client_class)
                clients.append((client_class, asynchronous, client_class.send))

    def mark_rate_limit():
        ledger.pause('rate_limit', attempt)
        if hasattr(models, 'mark_rate_limit'):
            models.mark_rate_limit()

    def guarded(self, *args, **kwargs):
        arguments = signature.bind(self, *args, **kwargs).arguments
        images = image_count(arguments.get('image_url'))
        ledger.reserve(attempt, images)
        previous = getattr(role_state, 'role', None)
        role_state.role = 'vision' if images else 'parse'
        try:
            return original(self, *args, **kwargs)
        except Exception as exc:
            if getattr(exc, 'status_code', None) == 429 or 'ratelimit' in type(exc).__name__.lower():
                mark_rate_limit()
            raise
        finally:
            role_state.role = previous

    def before(request):
        provider = request.url.host in ('api.openai.com', 'api.anthropic.com')
        if provider:
            ledger.http_call(attempt, getattr(role_state, 'role', None) or 'deep_text')
        return provider

    def after(response, provider):
        if provider and response.status_code == 429:
            mark_rate_limit()

    def synchronous_guard(original_send):
        def send(client, request, *args, **kwargs):
            provider = before(request)
            response = original_send(client, request, *args, **kwargs)
            after(response, provider)
            return response
        return send

    def asynchronous_guard(original_send):
        async def send(client, request, *args, **kwargs):
            provider = before(request)
            response = await original_send(client, request, *args, **kwargs)
            after(response, provider)
            return response
        return send

    models.ModelProvider._call = guarded
    for client_class, asynchronous, original_send in clients:
        client_class.send = (asynchronous_guard if asynchronous else synchronous_guard)(original_send)
    try:
        yield
    finally:
        if restore:
            models.ModelProvider._call = original
            for client_class, _, original_send in clients:
                client_class.send = original_send


def worker(job_path: Path) -> int:
    job_path = private_path(job_path)
    job = json.loads(job_path.read_text())
    scene, label = job['scene'], job['label']
    if scene.get('id') not in TUNE_IDS or scene.get('split') != 'tune' or label.get('split') != 'tune':
        raise ValueError('Worker refuses non-tune inputs')
    from agent.eval.label_bridge import validate_live_inputs
    pinned = validate_live_inputs([scene], {scene['id']: label}, private_path(Path(job['index_dir'])))
    config, attempt = job['config'], job['attempt']
    os.environ.update(TYPECAST_USE_MOCKS='0', TYPECAST_ENGINE=job['engine'],
        TYPECAST_INDEX_DIR=str(pinned), TYPECAST_ENABLE_MODEL_PARSE='1',
        TYPECAST_ENABLE_VISION_RERANK='1', TYPECAST_ALLOW_VISION_UPLOAD='1',
        TYPECAST_RERANK_POOL=str(config['pool']),
        TYPECAST_VISION_CONCURRENCY=str(config['concurrency']),
        TYPECAST_VISION_BATCH_SIZE=str(config['batch_size']),
        TYPECAST_RERANK_CACHE_DIR=str(job_path.parent / 'score-cache'))
    from fastapi.testclient import TestClient
    from agent import state
    from agent.app import app
    from index.search import configure_index
    configure_index(cache_dir=pinned)
    ledger = Ledger(Path(job['ledger']))
    record = {'attempt': attempt, 'scene_id': scene['id'], 'split': 'tune',
        'config': config, 'requested_engine': job['engine'], 'actual_engine': None,
        'started_at': now(), 'ok': False, 'error_type': None, 'raw_response': None,
        'fallback': False, 'latency_s': None, 'top10': []}
    started = perf_counter()
    try:
        with provider_budget(ledger, attempt, restore=False), TestClient(app, raise_server_exceptions=False) as client:
            request_started = perf_counter()
            response = client.post('/scout', json={'scene': scene['scene']})
            record['latency_s'] = perf_counter() - request_started
            record['status_code'] = response.status_code
            body = response.json()
            record['raw_response'] = body
            record['actual_engine'] = body.get('engine')
            record['fallback'] = body.get('engine') != job['engine'] or any(
                event.get('type') == 'fallback' and event.get('agent') == 'runtime'
                for event in body.get('events', []))
            if body.get('thread_id'):
                requirements = state.load(body['thread_id'], 'requirements')
                requirements = requirements.model_dump(mode='json') if hasattr(requirements, 'model_dump') else requirements
                candidates = state.load(body['thread_id'], 'candidates')
                candidates = [s.model_dump(mode='json') if hasattr(s, 'model_dump') else s for s in candidates]
                record.update(requirements=requirements, model_parse=bool(requirements.get('parsed_with_model')))
                record.update(metrics(candidates[:10], scene, label))
            events = body.get('events', [])
            record['vision_events'] = [e['text'] for e in events if e.get('type') == 'rerank']
            accounting = []
            for text in record['vision_events']:
                if '; accounting=' in text:
                    accounting.append(json.loads(text.split('; accounting=', 1)[1]))
            record['vision_accounting'] = accounting
            record['trace_present'] = bool(body.get('trace_url'))
            record['model_fallback_events'] = sum(e.get('type') == 'fallback' and e.get('agent') == 'models' for e in events)
            record['ok'] = (response.status_code == 200 and body.get('source_mode') == 'live'
                and not record['fallback'] and record['latency_s'] <= REQUEST_LIMIT_S
                and record.get('model_parse', False) and record.get('retrieved_count', 0) == 10
                and record['model_fallback_events'] == 0 and completed_vision(accounting, config))
        validate_live_inputs([scene], {scene['id']: label}, pinned)
    except BaseException as exc:
        record['error_type'] = type(exc).__name__
        record['ok'] = False
    record['worker_elapsed_s'] = perf_counter() - started
    accounting = ledger.snapshot()
    record['accounting'] = accounting['attempts'][attempt]
    record['ledger_paused'] = accounting['paused']
    if accounting['paused']:
        record['ok'] = False
    ledger.finish(attempt, 'complete' if record['ok'] else 'failed')
    atomic_json(job_path.parent / 'result.json', record)
    return 0 if record['ok'] else 1


def aggregate(records: list[dict]) -> dict:
    def attempt_order(row):
        value = row.get('started_at') or (row.get('accounting') or {}).get('started_at')
        try:
            timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                raise ValueError('Missing timestamp timezone')
            timestamp = timestamp.astimezone(timezone.utc)
        except (AttributeError, TypeError, ValueError):
            # Incomplete/crashed records are conservatively ordered before later
            # successful retries, never silently replaced by the best outcome.
            timestamp = datetime.min.replace(tzinfo=timezone.utc)
        return timestamp, row.get('attempt', '')

    groups = defaultdict(list)
    for row in records:
        cfg = row['config']
        groups[f"{row['requested_engine']}/n{cfg['pool']}/c{cfg['concurrency']}/b{cfg['batch_size']}"] += [row]
    result = {}
    for key, rows in groups.items():
        success = [r for r in rows if r.get('ok')]
        first, scene_counts = {}, defaultdict(int)
        for row in sorted(rows, key=attempt_order):
            first.setdefault(row['scene_id'], row)
            scene_counts[row['scene_id']] += 1
        quality = [r for r in first.values() if r.get('ok')]
        times = sorted(r['latency_s'] if r.get('latency_s') is not None else r['worker_elapsed_s']
                       for r in rows if r.get('latency_s') is not None or r.get('worker_elapsed_s') is not None)
        recalls = [r['recall_at_10'] for r in quality if r.get('recall_at_10') is not None]
        precisions = [r['precision_lower_bound_at_10'] for r in quality]
        result[key] = {'attempts': len(rows), 'successful': len(success),
            'failed': len(rows)-len(success), 'distinct_successful_scenes': len({r['scene_id'] for r in success}),
            'quality_selection': 'first_attempt_per_scene_by_started_at_then_attempt',
            'quality_successful_scenes': len(quality),
            'quality_attempt_ids': {sid: row.get('attempt') for sid, row in sorted(first.items())},
            'duplicate_attempts': len(rows)-len(first),
            'duplicate_scenes': sum(count > 1 for count in scene_counts.values()),
            'fallbacks': sum(bool(r.get('fallback')) for r in rows),
            'macro_recall_at_10': sum(recalls)/len(recalls) if recalls else None,
            'macro_precision_lower_bound_at_10': sum(precisions)/len(precisions) if precisions else None,
            'all_attempt_latency_p50_s': median(times) if times else None,
            'all_attempt_latency_p95_s': times[math.ceil(.95*len(times))-1] if times else None,
            'all_attempt_latency_max_s': max(times) if times else None,
            'process_timeout_latency_count': sum(r.get('latency_s') is None for r in rows),
            'complete_five_scene_success': (len(rows) == len(success) == 5
                and {r['scene_id'] for r in success} == TUNE_IDS),
            'unjudged_slots': sum(r.get('unjudged_slots', 0) for r in rows)}
    return result


def run(args) -> dict:
    scenes, labels, pinned = tune_inputs(args.tune_dir, args.index_dir)
    selected = args.scene_id or [s['id'] for s in scenes]
    if not set(selected) <= TUNE_IDS or len(selected) != len(set(selected)):
        raise ValueError('Only unique tune scene ids are allowed')
    scenes = [s for s in scenes if s['id'] in selected]
    configs = args.config or [configuration('10,5,1')]
    engines = list(dict.fromkeys(args.engines))
    output = private_path(args.output_root)
    ledger = Ledger(output / 'ledger.json')
    if not args.execute:
        return {'plan_only': True, 'engines': engines, 'configs': configs,
            'scene_ids': [s['id'] for s in scenes], 'attempts': len(scenes)*len(configs)*len(engines),
            'nominal_images_without_fallback': sum(c['pool'] for c in configs)*len(scenes)*len(engines),
            'image_hard_limit': HARD_IMAGE_LIMIT, 'index_dir': str(pinned), 'hard_stop': hard_stop().isoformat()}
    stop = hard_stop()
    produced = []
    for config in configs:
        for scene in scenes:
            for engine in engines:
                remaining = (stop-datetime.now(ZoneInfo('America/New_York'))).total_seconds()
                if remaining < REQUEST_LIMIT_S or ledger.snapshot()['paused']:
                    return {'stopped': True, 'reason': 'hard_stop_or_paused_ledger', 'attempts': produced}
                attempt = uuid4().hex
                directory = output / 'attempts' / attempt
                job = {'attempt': attempt, 'scene': scene, 'label': labels[scene['id']],
                    'config': config, 'engine': engine, 'index_dir': str(pinned), 'ledger': str(ledger.path)}
                ledger.register(attempt, {'scene_id': scene['id'], 'config': config,
                    'requested_engine': engine, 'started_at': now()})
                atomic_json(directory / 'job.json', job)
                launch_started = perf_counter()
                with (directory / 'worker.log').open('w') as log:
                    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                        '--worker', str(directory / 'job.json')], cwd=ROOT,
                        stdout=log, stderr=log, start_new_session=os.name != 'nt')
                    try:
                        process.wait(timeout=min(remaining, 125.))
                    except subprocess.TimeoutExpired:
                        if os.name == 'nt':
                            process.kill()
                        else:
                            os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                result_path = directory / 'result.json'
                if result_path.is_file():
                    record = json.loads(result_path.read_text())
                else:
                    record = {'attempt': attempt, 'scene_id': scene['id'], 'config': config,
                        'requested_engine': engine, 'ok': False, 'latency_s': None,
                        'error_type': 'WorkerTimeoutOrCrash', 'worker_returncode': process.returncode,
                        'worker_elapsed_s': perf_counter()-launch_started,
                        'accounting': ledger.snapshot()['attempts'][attempt]}
                    atomic_json(result_path, record)
                    ledger.finish(attempt, 'failed')
                produced.append(attempt)
                records = [json.loads(p.read_text()) for p in (output / 'attempts').glob('*/result.json')]
                atomic_json(output / 'summary.json', aggregate(records))
                print(json.dumps({'attempt': attempt, 'scene_id': scene['id'], 'config': config,
                    'requested_engine': engine, 'ok': record['ok'], 'latency_s': record.get('latency_s'),
                    'images_reserved_total': ledger.snapshot()['images_reserved']}), flush=True)
                if ledger.snapshot()['paused']:
                    return {'stopped': True, 'reason': 'ledger_paused', 'attempts': produced}
    failed = sum(not json.loads((output/'attempts'/a/'result.json').read_text())['ok'] for a in produced)
    return {'stopped': False, 'attempts': produced, 'failed_attempts': failed, 'summary': str(output / 'summary.json')}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tune-dir', type=Path, default=ROOT / 'cache/evaluation/tune')
    parser.add_argument('--index-dir', type=Path, default=ROOT / 'cache/shot-index')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'cache/experiments/rerank-v2')
    parser.add_argument('--engines', nargs='+', choices=('fixed', 'deep'), default=['fixed'])
    parser.add_argument('--config', type=configuration, action='append')
    parser.add_argument('--scene-id', action='append', choices=sorted(TUNE_IDS))
    parser.add_argument('--execute', action='store_true', help='Make paid live calls; default only prints a plan.')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.worker:
            code = worker(args.worker)
            # No abandoned graph/scoring thread can outlive its guarded process.
            sys.stdout.flush(); sys.stderr.flush()
            os._exit(code)
        result = run(args)
        print(json.dumps(result, indent=2))
        return 1 if result.get('stopped') or result.get('failed_attempts') else 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
