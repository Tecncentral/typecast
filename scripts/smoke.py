"""Exercise JSON and streamed API contracts without secrets or provider calls."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from agent.eval.harness import mock_app
from contracts.schemas import ScoutResponse

with mock_app() as app, TestClient(app) as client:
    assert client.get('/health').json()['mocks'] is True
    response = client.post('/scout', json={'scene': 'An office. Parking for 3 trucks and 30 cars.'})
    response.raise_for_status()
    run = ScoutResponse.model_validate(response.json())
    assert len(run.picks) == 3
    refined = client.post('/refine', json={'thread_id': run.thread_id, 'message': '50 trucks'})
    refined.raise_for_status()
    assert refined.json()['thread_id'] == run.thread_id
    stream = client.get('/scout/stream', params={'scene': 'An office'})
    stream.raise_for_status()
    blocks = stream.text.strip().split('\n\n')
    final = next(b for b in blocks if b.startswith('event: result\n'))
    ScoutResponse.model_validate(json.loads(final.split('data: ', 1)[1]))
    assert client.post('/approve', json={'thread_id': run.thread_id, 'pick_rank': 1, 'decision': 'no'}).json()['sent'] is False
print('PASS: mock search -> validated picks -> same-thread refinement -> SSE result -> no-send approval')
