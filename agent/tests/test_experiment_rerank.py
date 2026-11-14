"""Tune gate and pre-call budget guards; no model or network calls."""
from concurrent.futures import ThreadPoolExecutor
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import pytest
from scripts import experiment_rerank as exp


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(exp, 'ROOT', tmp_path)
    result = exp.Ledger(tmp_path / 'cache/experiment/ledger.json')
    result.register('attempt', {'scene_id': 'interior-16'})
    return result


def test_parallel_reservations_cannot_overshoot_and_remain_charged(ledger):
    def reserve(_):
        try:
            ledger.reserve('attempt', 10)
            return True
        except exp.ExperimentStop:
            return False
    with ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(reserve, range(120)))
    value = ledger.snapshot()
    assert sum(outcomes) == 100
    assert value['images_reserved'] == value['attempts']['attempt']['images_reserved'] == 1000
    assert value['paused']['reason'] == 'image_budget'


def test_budget_is_shared_across_processes(ledger):
    code = """import sys
from pathlib import Path
from scripts import experiment_rerank as e
e.ROOT=Path(sys.argv[1]);l=e.Ledger(Path(sys.argv[2]))
try:l.reserve('attempt',600)
except e.ExperimentStop:pass
"""
    processes = [subprocess.Popen([sys.executable, '-c', code, str(exp.ROOT), str(ledger.path)],
                                 cwd=Path(exp.__file__).resolve().parents[1]) for _ in range(2)]
    assert all(p.wait(timeout=15) == 0 for p in processes)
    assert ledger.snapshot()['images_reserved'] == 600
    assert ledger.snapshot()['paused']['reason'] == 'image_budget'


def test_provider_guard_reserves_batch_images_before_original_call(ledger, monkeypatch):
    from agent import models
    calls = []
    def call(self, provider, model, key, instructions, text, output_model, image_url, timeout):
        calls.append(image_url)
        assert ledger.snapshot()['images_reserved'] == 6
        return 'result'
    monkeypatch.setattr(models.ModelProvider, '_call', call)
    provider = models.ModelProvider(vision=True)
    args = ('openai', 'fake', 'synthetic', 'instructions', 'text', dict)
    with exp.provider_budget(ledger, 'attempt'):
        assert provider._call(*args, ['a']*6, 1) == 'result'
    assert len(calls) == 1 and ledger.snapshot()['attempts']['attempt']['vision_calls'] == 1


def test_rate_limit_stops_following_calls_and_parser_is_separate(ledger, monkeypatch):
    from agent import models
    class Limited(Exception):
        status_code = 429
    calls = []
    def call(self, provider, model, key, instructions, text, output_model, image_url, timeout):
        calls.append(image_url)
        if image_url:
            raise Limited()
        return 'parsed'
    monkeypatch.setattr(models.ModelProvider, '_call', call)
    monkeypatch.setattr(models, 'mark_rate_limit', lambda: None)
    provider = models.ModelProvider()
    args = ('openai', 'fake', 'synthetic', 'instructions', 'text', dict)
    with exp.provider_budget(ledger, 'attempt'):
        assert provider._call(*args, None, 1) == 'parsed'
        with pytest.raises(Limited):
            provider._call(*args, ['a']*5, 1)
        with pytest.raises(exp.ExperimentStop):
            provider._call(*args, 'b', 1)
    value = ledger.snapshot()
    assert len(calls) == 2 and value['images_reserved'] == 5
    assert value['attempts']['attempt']['parse_calls'] == 1
    assert value['paused']['reason'] == 'rate_limit'


def test_unknown_payload_and_negative_reservations_cannot_bypass_budget(ledger):
    for value in ({'images': ['x']}, 3, ''):
        with pytest.raises(ValueError):
            exp.image_count(value)
    with pytest.raises(ValueError):
        ledger.reserve('attempt', -1)


def test_tune_gate_rejects_test_exports_before_index_load(tmp_path, monkeypatch):
    monkeypatch.setattr(exp, 'ROOT', tmp_path)
    directory = tmp_path / 'cache/tune'
    directory.mkdir(parents=True)
    (directory / 'scenes.jsonl').write_text(json.dumps({'id': 'interior-01', 'split': 'test'})+'\n')
    (directory / 'labels.jsonl').write_text(json.dumps({'id': 'interior-01', 'split': 'test'})+'\n')
    with pytest.raises(ValueError, match='five frozen tune'):
        exp.tune_inputs(directory, directory)


def test_precision_lower_bound_counts_unjudged_and_missing_slots_as_misses():
    scene = {'evaluation': {'pool_shot_ids': ['good', 'bad']}}
    result = exp.metrics(['good', 'unjudged'], scene, {'relevant_shot_ids': ['good']})
    assert result['recall_at_10'] == 1
    assert result['precision_lower_bound_at_10'] == .1
    assert result['unjudged_slots'] == 1 and result['missing_slots'] == 8


def test_completed_vision_requires_exact_pool_single_event_and_no_cache():
    config = exp.configuration('20,5,5')
    item = {'candidate_count': 20, 'images_scored': 20, 'pool': 20, 'concurrency': 5,
            'batch_size': 5, 'failures': 0, 'cached': 0, 'rate_limited': False}
    assert exp.completed_vision([item], config)
    assert not exp.completed_vision([item, item], config)
    for changes in ({'candidate_count': 10}, {'images_scored': 10}, {'cached': 1},
                    {'failures': 1}, {'rate_limited': True}, {'concurrency': 10}):
        assert not exp.completed_vision([{**item, **changes}], config)


def test_failed_deep_fallback_and_timeout_are_retained_in_summary():
    config = exp.configuration('10,5,1')
    records = [{'requested_engine': 'deep', 'config': config, 'scene_id': 'interior-16',
                'ok': False, 'fallback': True, 'latency_s': 91.},
               {'requested_engine': 'deep', 'config': config, 'scene_id': 'interior-17',
                'ok': False, 'latency_s': None, 'worker_elapsed_s': 125.}]
    result = exp.aggregate(records)['deep/n10/c5/b1']
    assert result['failed'] == 2 and result['fallbacks'] == 1
    assert result['all_attempt_latency_max_s'] == 125.
    assert result['macro_recall_at_10'] is None and not result['complete_five_scene_success']


def test_duplicate_scene_does_not_weight_quality_or_qualify_six_attempts():
    config = exp.configuration('20,5,1')
    first = [{'requested_engine': 'fixed', 'config': config, 'scene_id': f'interior-{n}',
              'attempt': f'first-{n}', 'started_at': '2026-11-14T15:00:00-05:00',
              'ok': True, 'latency_s': 10., 'recall_at_10': .2,
              'precision_lower_bound_at_10': .3} for n in range(16, 21)]
    later = {**first[0], 'attempt': 'later', 'started_at': '2026-11-14T20:01:00+00:00',
             'latency_s': 60., 'recall_at_10': 1., 'precision_lower_bound_at_10': 1.}
    # Reverse input ordering and use different timezone offsets: actual start
    # time, rather than insertion order or a higher score, declares the first.
    value = exp.aggregate([later, *reversed(first)])['fixed/n20/c5/b1']
    assert value['macro_recall_at_10'] == pytest.approx(.2)
    assert value['macro_precision_lower_bound_at_10'] == pytest.approx(.3)
    assert value['quality_attempt_ids']['interior-16'] == 'first-16'
    assert value['duplicate_attempts'] == value['duplicate_scenes'] == 1
    assert value['attempts'] == value['successful'] == 6
    assert value['all_attempt_latency_max_s'] == 60.
    assert not value['complete_five_scene_success']
    assert exp.aggregate(first)['fixed/n20/c5/b1']['complete_five_scene_success']


def test_failed_first_attempt_is_not_replaced_by_successful_retry():
    base = {'requested_engine': 'deep', 'config': exp.configuration('10,5,1'),
            'scene_id': 'interior-16', 'started_at': '2026-11-14T20:00:00+00:00'}
    failed = {**base, 'attempt': 'a', 'ok': False, 'latency_s': 89., 'fallback': True}
    retry = {**base, 'attempt': 'b', 'ok': True, 'latency_s': 25.,
             'recall_at_10': 1., 'precision_lower_bound_at_10': 1.}
    value = exp.aggregate([retry, failed])['deep/n10/c5/b1']
    assert value['quality_attempt_ids']['interior-16'] == 'a'
    assert value['macro_recall_at_10'] is None and value['quality_successful_scenes'] == 0
    assert value['failed'] == value['fallbacks'] == 1
    assert value['all_attempt_latency_max_s'] == 89.


@pytest.mark.parametrize('sdk_name', ['openai', 'anthropic'])
@pytest.mark.parametrize('asynchronous', [False, True])
def test_installed_sdk_429_pauses_deep_text_and_blocks_next_transport(
        ledger, monkeypatch, sdk_name, asynchronous):
    """Exercise the actual SDK/httpx2 boundary, not a fake ModelProvider._call."""
    sdk = pytest.importorskip(sdk_name)
    httpx2 = pytest.importorskip('httpx2')
    from agent import models
    monkeypatch.setattr(models, 'mark_rate_limit', lambda: None)
    transport_calls = []

    def handler(request):
        transport_calls.append(request.url.host)
        return httpx2.Response(429, json={
            'type': 'error',
            'error': {'type': 'rate_limit_error', 'message': 'synthetic offline rate limit'}})

    if sdk_name == 'openai':
        client_class = sdk.AsyncOpenAI if asynchronous else sdk.OpenAI
        def invoke(client):
            return client.responses.create(model='test-only-model', input='synthetic test')
    else:
        client_class = sdk.AsyncAnthropic if asynchronous else sdk.Anthropic
        def invoke(client):
            return client.messages.create(model='test-only-model', max_tokens=1,
                messages=[{'role': 'user', 'content': 'synthetic test'}])

    original_send = (httpx2.AsyncClient if asynchronous else httpx2.Client).send
    with exp.provider_budget(ledger, 'attempt'):
        if asynchronous:
            async def exercise():
                async with client_class(api_key='synthetic-test-key', max_retries=0,
                        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))) as client:
                    with pytest.raises(sdk.RateLimitError):
                        await invoke(client)
                    with pytest.raises(Exception):
                        await invoke(client)
            asyncio.run(exercise())
        else:
            with client_class(api_key='synthetic-test-key', max_retries=0,
                    http_client=httpx2.Client(transport=httpx2.MockTransport(handler))) as client:
                with pytest.raises(sdk.RateLimitError):
                    invoke(client)
                with pytest.raises(Exception):
                    invoke(client)
    value = ledger.snapshot()
    assert len(transport_calls) == 1
    assert value['paused']['reason'] == 'rate_limit'
    assert value['attempts']['attempt']['http_calls'] == {'deep_text': 1}
    assert value['images_reserved'] == 0
    assert (httpx2.AsyncClient if asynchronous else httpx2.Client).send is original_send
