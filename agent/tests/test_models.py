"""Model paths use fakes only: no network calls or real credentials."""
import base64
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from agent import models, parse, rerank
from agent.interfaces import Requirements, RunContext
from contracts.schemas import Event, Shot

SCENE = "INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling. Parking for 3 trucks and 30 crew cars."
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII=")


@pytest.fixture(autouse=True)
def isolated_models(monkeypatch):
    for key in ("LLM_API_KEY", "VISION_API_KEY", "FALLBACK_API_KEY", "OPENAI_API_KEY",
                "TYPECAST_LLM_MODEL", "TYPECAST_VISION_MODEL", "TYPECAST_FALLBACK_MODEL",
                "TYPECAST_FALLBACK_PROVIDER", "TYPECAST_REASONING_EFFORT", "TYPECAST_RERANK_POOL",
                "TYPECAST_VISION_CONCURRENCY", "TYPECAST_VISION_BATCH_SIZE", "TYPECAST_RERANK_CACHE_DIR"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TYPECAST_LLM_PROVIDER", "openai")
    monkeypatch.setenv("TYPECAST_ENABLE_MODEL_PARSE", "1")
    monkeypatch.setenv("TYPECAST_ENABLE_VISION_RERANK", "1")
    monkeypatch.setenv("TYPECAST_VISION_BATCH_SIZE", "1")
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "0")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    models.reset_rate_limit()
    yield
    models.reset_rate_limit()


class FakeProvider:
    cache_identity = "fake:model"

    def __init__(self, result=None, *, configured=True, fail_call=None):
        self.result, self.available, self.fail_call = result, configured, fail_call
        self.calls = []
        self.active = self.max_active = 0
        self.lock = threading.Lock()

    def configured(self):
        return self.available

    def structured(self, instructions, text, output_model, **kwargs):
        with self.lock:
            self.calls.append((instructions, text, output_model, kwargs))
            number = len(self.calls)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if kwargs.get("image_url"):
                assert kwargs["image_url"].startswith("data:image/png;base64,")
                assert 0 < kwargs["timeout"] <= 20
                time.sleep(0.015)
            if number == self.fail_call:
                raise TimeoutError("fake timeout; private prompt must never be emitted")
            return output_model.model_validate(self.result or {"score": 0.85, "reason": "Drop ceiling matches the era."})
        finally:
            with self.lock:
                self.active -= 1


def shots_fixture(tmp_path, monkeypatch, count=3):
    root = tmp_path / "cache"
    root.mkdir()
    monkeypatch.setattr(rerank, "CACHE_ROOT", root)
    shots = []
    for number in range(count):
        image = root / f"shot-{number}.png"
        image.write_bytes(PNG)
        shots.append(Shot(shot_id=f"shot-{number}", model_id="model", sweep_id="sweep",
                          heading_deg=number, image_path=str(image), property_id="property",
                          score=0.6 - number * 0.01))
    return shots


def test_structured_parse_police_station(monkeypatch):
    fake = FakeProvider({"city": "Los Angeles", "era_label": "1980s", "year_max": 1992,
                         "trucks": 3, "cars": 30, "look": "big open room, drop ceiling",
                         "time_of_day": "night", "explicit_fields": ["era_label", "year_min", "year_max", "trucks", "cars", "look", "time_of_day"]})
    monkeypatch.setattr(parse, "get_provider", lambda **kwargs: fake)
    req = parse.parse_scene(SCENE)
    assert req.parsed_with_model and req.parse_note is None
    assert (req.city, req.year_max, req.trucks, req.cars) == ("Los Angeles", 1992, 3, 30)
    assert req.focal_mm == 24 and req.frame_width_m == 6 and req.min_area_m2 is None
    assert req.time_of_day == "night" and "drop ceiling" in req.look
    assert "city" not in req.explicit_fields and "trucks" in req.explicit_fields
    assert len(fake.calls) == 1 and fake.calls[0][2] is parse.SceneFields


@pytest.mark.parametrize("kind", ["model_request", "rate_limit", "fallback", "model_failure"])
def test_parse_preserves_provider_event_type_and_records_only_failure_notes(monkeypatch, kind):
    message = json.dumps({"images": 0, "provider_calls": 1, "vision": False}) if kind == "model_request" else "Controlled provider event"
    class EmittingProvider(FakeProvider):
        def structured(self, *args, **kwargs):
            self.emit(Event(type=kind, agent="models", text=message))
            return super().structured(*args, **kwargs)
    fake = EmittingProvider({"city": "Los Angeles", "explicit_fields": []})
    def provider(**kwargs):
        fake.emit = kwargs["emit"]
        return fake
    monkeypatch.setattr(parse, "get_provider", provider)
    events = []
    req = parse.parse_scene(SCENE, emit=events.append)
    assert req.parsed_with_model and len(events) == 1
    assert (events[0].type, events[0].agent, events[0].text) == (kind, "models", message)
    assert req.parse_note == (message if kind in {"fallback", "model_failure"} else None)


def test_successful_parser_accounting_does_not_emit_director_fallback(monkeypatch):
    from fastapi.testclient import TestClient
    from agent.eval.harness import mock_app

    class AccountingProvider(FakeProvider):
        def structured(self, *args, **kwargs):
            self.emit(Event(type="model_request", agent="models", text=json.dumps(
                {"images": 0, "provider_calls": 1, "vision": False})))
            return super().structured(*args, **kwargs)
    fake = AccountingProvider({"city": "Los Angeles", "explicit_fields": []})
    def provider(**kwargs):
        fake.emit = kwargs["emit"]
        return fake
    monkeypatch.setattr(parse, "get_provider", provider)
    with mock_app() as app:
        monkeypatch.setenv("TYPECAST_ENABLE_MODEL_PARSE", "1")
        with TestClient(app) as client:
            response = client.post("/scout", json={"scene": SCENE})
        assert response.status_code == 200
        events = response.json()["events"]
        assert sum(event["type"] == "model_request" for event in events) == 1
        assert not any(event["type"] in {"fallback", "model_failure"} for event in events)


def test_unconfigured_falls_back_and_preserves_original_era_bounds():
    req = parse.parse_scene(SCENE)
    assert not models.configured() and not req.parsed_with_model
    assert req.trucks == 3 and req.cars == 30 and req.year_max == 1992
    assert req.time_of_day == "night" and "without a model" in req.parse_note.lower()


@pytest.mark.parametrize("use_model", [False, True])
def test_no_trucks_is_explicit_zero(monkeypatch, use_model):
    fake = FakeProvider({"trucks": 7, "cars": 8}, configured=use_model)
    monkeypatch.setattr(parse, "get_provider", lambda **kwargs: fake)
    req = parse.parse_scene("Houston. No trucks and 0 crew cars.")
    assert req.trucks == req.cars == 0
    assert {"trucks", "cars"} <= req.explicit_fields


def test_invalid_model_output_falls_back_without_leaking_error(monkeypatch):
    fake = FakeProvider({"trucks": -1})
    monkeypatch.setattr(parse, "get_provider", lambda **kwargs: fake)
    req = parse.parse_scene(SCENE)
    assert not req.parsed_with_model and req.trucks == 3
    assert "ValidationError" in req.parse_note and "input_value" not in req.parse_note


def test_rule_parser_units():
    req = parse.rule_parse_scene("Houston, gritty night. 1000 sqft with 10 ft ceiling; 35mm lens and frame width 20 feet.")
    assert req.city == "Houston" and req.mood == "gritty" and req.time_of_day == "night"
    assert req.min_area_m2 == pytest.approx(92.90304)
    assert req.min_ceiling_m == pytest.approx(3.048)
    assert req.focal_mm == 35 and req.frame_width_m == pytest.approx(6.096)


def test_rerank_respects_upload_flag(tmp_path, monkeypatch):
    shots = shots_fixture(tmp_path, monkeypatch)
    fake = FakeProvider()
    monkeypatch.setattr(rerank, "get_provider", lambda **kwargs: fake)
    events = []
    result = rerank.rerank_shots(RunContext("t", emit=events.append), Requirements(scene=SCENE), shots)
    assert result == shots and fake.calls == []
    assert "TYPECAST_ALLOW_VISION_UPLOAD=1" in events[-1].text
    assert not list(rerank.CACHE_ROOT.rglob("*.json"))


def test_rerank_cache_and_concurrency(tmp_path, monkeypatch):
    shots = shots_fixture(tmp_path, monkeypatch, count=12)
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "1")
    fake = FakeProvider()
    monkeypatch.setattr(rerank, "get_provider", lambda **kwargs: fake)
    events = []
    ctx, req = RunContext("t", emit=events.append), Requirements(scene=SCENE)
    first = rerank.rerank_shots(ctx, req, shots)
    assert len(fake.calls) == 12 and 1 < fake.max_active <= 5
    assert all(shot.score == 0.85 for shot in first)
    assert shots[0].score == 0.6  # Caller working memory wasn't mutated.
    second = rerank.rerank_shots(ctx, req, shots)
    assert second == first and len(fake.calls) == 12
    assert len(list(rerank.CACHE_ROOT.rglob("*.json"))) == 12
    assert "12 cached" in events[-1].text


def test_rerank_uses_exact_authored_scene_across_inferred_parse_variation(tmp_path, monkeypatch):
    shots = shots_fixture(tmp_path, monkeypatch, count=1)
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "1")
    fake = FakeProvider()
    monkeypatch.setattr(rerank, "get_provider", lambda **kwargs: fake)
    ctx = RunContext("test-stable-visual-payload")
    first_req = Requirements(scene=SCENE, look="large room with drop ceiling", mood="tense",
                             time_of_day="night", year_max=1992, parsed_with_model=True,
                             explicit_fields={"look", "time_of_day"})
    varied_req = first_req.model_copy(update={"look": "open room; fluorescent ceiling", "mood": "gritty",
                                             "year_max": 1989, "explicit_fields": {"look", "mood"}})
    first = rerank.rerank_shots(ctx, first_req, shots)
    second = rerank.rerank_shots(ctx, varied_req, shots)
    assert first == second and len(fake.calls) == 1
    assert json.loads(fake.calls[0][1]) == {"scene": SCENE}
    for number, text in enumerate((SCENE + "\nFollow-up: Warmer light and exposed brick.",
                                   SCENE.replace("NIGHT", "DAY")), 2):
        rerank.rerank_shots(ctx, varied_req.model_copy(update={"scene": text}), shots)
        assert len(fake.calls) == number
        assert json.loads(fake.calls[-1][1]) == {"scene": text}
    assert first_req.look == "large room with drop ceiling" and shots[0].score == .6


@pytest.mark.parametrize("change", ["provider", "prompt", "image", "legacy_cache_version"])
def test_rerank_cache_invalidates_changed_scoring_inputs(tmp_path, monkeypatch, change):
    shots = shots_fixture(tmp_path, monkeypatch, count=1)
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "1")
    fake = FakeProvider()
    monkeypatch.setattr(rerank, "get_provider", lambda **kwargs: fake)
    ctx, req = RunContext("test-visual-invalidation"), Requirements(scene=SCENE)
    rerank.rerank_shots(ctx, req, shots)
    rerank.rerank_shots(ctx, req, shots)
    assert len(fake.calls) == 1
    if change == "provider":
        fake.cache_identity = "other-provider:other-model:other-effort"
    elif change == "prompt":
        prompt = tmp_path / "changed-rerank-prompt.md"
        prompt.write_text(rerank.PROMPT_PATH.read_text() + "\nPrefer visible architectural cues.\n")
        monkeypatch.setattr(rerank, "PROMPT_PATH", prompt)
    elif change == "image":
        Path(shots[0].image_path).write_bytes(PNG + b"changed image bytes")
    else:
        path = next(rerank.CACHE_ROOT.rglob("*.json"))
        cached = json.loads(path.read_text())
        cached["identity"]["version"] = 1
        path.write_text(json.dumps(cached))
    rerank.rerank_shots(ctx, req, shots)
    assert len(fake.calls) == 2
    assert json.loads(fake.calls[-1][1]) == {"scene": SCENE}
    assert fake.calls[-1][0] == rerank.PROMPT_PATH.read_text()
    rerank.rerank_shots(ctx, req, shots)
    assert len(fake.calls) == 2


@pytest.mark.parametrize(("gate", "message"), [
    ("permission", "TYPECAST_ALLOW_VISION_UPLOAD=1"),
    ("enabled", "model reranking is disabled"),
    ("configured", "no configured vision provider"),
])
def test_warm_rerank_cache_still_requires_permission_and_configured_enabled_model(tmp_path, monkeypatch, gate, message):
    shots = shots_fixture(tmp_path, monkeypatch, count=1)
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "1")
    fake = FakeProvider()
    monkeypatch.setattr(rerank, "get_provider", lambda **kwargs: fake)
    events = []
    ctx, req = RunContext("test-warm-permission", emit=events.append), Requirements(scene=SCENE)
    assert rerank.rerank_shots(ctx, req, shots)[0].score == .85
    if gate == "permission":
        monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "0")
    elif gate == "enabled":
        monkeypatch.setenv("TYPECAST_ENABLE_VISION_RERANK", "0")
    else:
        fake.available = False
    monkeypatch.setattr(rerank, "_image_input", lambda *args: pytest.fail("Gated rerank loaded an image"))
    assert rerank.rerank_shots(ctx, req, shots) == shots
    assert len(fake.calls) == 1 and message in events[-1].text


def test_one_shot_timeout_keeps_original_score_and_batch_succeeds(tmp_path, monkeypatch):
    shots = shots_fixture(tmp_path, monkeypatch)
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "1")
    fake = FakeProvider(fail_call=1)
    monkeypatch.setattr(rerank, "get_provider", lambda **kwargs: fake)
    events = []
    ranked = rerank.rerank_shots(RunContext("t", emit=events.append), Requirements(scene=SCENE), shots)
    assert len(ranked) == 3 and len(fake.calls) == 3
    originals = {shot.shot_id: shot.score for shot in shots}
    unchanged = [shot for shot in ranked if shot.score == originals[shot.shot_id]]
    assert len(unchanged) == 1 and sum(shot.score == 0.85 for shot in ranked) == 2
    assert "1 failures" in events[-1].text and "private prompt" not in events[-1].text


def test_openai_adapter_uses_structured_schema_image_and_reasoning(monkeypatch):
    import openai
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.responses = SimpleNamespace(parse=self.parse)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def parse(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(output_parsed=rerank.VisualScore(score=0.9, reason="Visible era cues."))

    monkeypatch.setattr(openai, "OpenAI", Client)
    monkeypatch.setenv("VISION_API_KEY", "fake-test-key")
    monkeypatch.setenv("TYPECAST_VISION_MODEL", "configured-vision-model")
    monkeypatch.setenv("TYPECAST_REASONING_EFFORT", "high")
    provider = models.get_provider(vision=True)
    assert provider.configured() and not models.configured()
    result = provider.structured("instructions", "scene", rerank.VisualScore,
                                 image_url="data:image/png;base64,ZmFrZQ==", timeout=20)
    request = captured["request"]
    assert result.score == 0.9
    assert captured["client"]["max_retries"] == 0
    assert request["model"] == "configured-vision-model"
    assert request["reasoning"] == {"effort": "high"}
    assert request["text_format"] is rerank.VisualScore and request["store"] is False
    assert request["input"][0]["content"][1]["type"] == "input_image"


def test_provider_fallback_emits_sanitized_event(monkeypatch):
    for key, value in {"LLM_API_KEY": "fake-test-key", "TYPECAST_LLM_MODEL": "primary-model",
                       "TYPECAST_FALLBACK_PROVIDER": "anthropic", "TYPECAST_FALLBACK_MODEL": "backup-model",
                       "FALLBACK_API_KEY": "fake-backup-key"}.items():
        monkeypatch.setenv(key, value)
    events, calls = [], []
    provider = models.get_provider(emit=events.append)

    def call(name, model, key, instructions, text, output_model, image_url, timeout):
        calls.append((name, model, timeout))
        if name == "openai":
            raise TimeoutError("sensitive original prompt")
        return {"score": 0.7, "reason": "Visible period details."}

    monkeypatch.setattr(provider, "_call", call)
    result = provider.structured("private instructions", "private scene", rerank.VisualScore)
    assert result.score == 0.7
    assert [call[0] for call in calls] == ["openai", "anthropic"]
    assert calls[0][2] == 14 and 0 < calls[1][2] <= 20
    assert len(events) == 1 and events[0].type == "fallback"
    assert "TimeoutError" in events[0].text and "sensitive" not in events[0].text


def test_wall_clock_timeout_abandons_workers_without_late_side_effects(tmp_path, monkeypatch):
    shots = shots_fixture(tmp_path, monkeypatch, count=8)
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "1")
    monkeypatch.setattr(rerank, "SHOT_TIMEOUT_S", 0.05)
    release, stopped = threading.Event(), threading.Event()
    events = []

    class BlockingProvider:
        cache_identity = "blocking:test"

        def __init__(self):
            self.calls = self.active = self.max_active = 0
            self.lock = threading.Lock()

        def configured(self):
            return True

        def structured(self, instructions, text, output_model, **kwargs):
            with self.lock:
                self.calls += 1
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            try:
                release.wait()
                # Even a transport that emits after its timeout cannot reach ctx.
                self.emit(SimpleNamespace(type="fallback", text="late fallback"))
                return output_model(score=0.99, reason="A late successful response.")
            finally:
                with self.lock:
                    self.active -= 1
                    if not self.active:
                        stopped.set()

    fake = BlockingProvider()

    def provider(**kwargs):
        fake.emit = kwargs["emit"]
        return fake

    monkeypatch.setattr(rerank, "get_provider", provider)
    ctx, req = RunContext("blocked", emit=events.append), Requirements(scene=SCENE)
    try:
        started = time.monotonic()
        first = rerank.rerank_shots(ctx, req, shots)
        elapsed = time.monotonic() - started
        assert elapsed < 0.3 and not release.is_set()
        assert first == shots and fake.calls == 5 and fake.max_active == 5
        assert "8 failures" in events[-1].text
        # Abandoned calls hold the global slots: another batch cannot start
        # replacement requests while those first five are physically active.
        second = rerank.rerank_shots(ctx, req, shots)
        assert second == shots and fake.calls == 5 and fake.max_active == 5
        saved_events = list(events)
        assert not list(rerank.CACHE_ROOT.rglob("*.json"))
    finally:
        release.set()
        assert stopped.wait(timeout=1)
    assert events == saved_events
    assert not list(rerank.CACHE_ROOT.rglob("*.json"))


@pytest.mark.parametrize("fallback", [False, True])
def test_provider_rejects_success_after_shared_deadline(monkeypatch, fallback):
    monkeypatch.setenv("LLM_API_KEY", "fake-test-key")
    monkeypatch.setenv("TYPECAST_LLM_MODEL", "primary-model")
    if fallback:
        monkeypatch.setenv("TYPECAST_FALLBACK_PROVIDER", "anthropic")
        monkeypatch.setenv("TYPECAST_FALLBACK_MODEL", "backup-model")
        monkeypatch.setenv("FALLBACK_API_KEY", "fake-backup-key")
    clock = [0.0]
    monkeypatch.setattr(models, "monotonic", lambda: clock[0])
    provider = models.get_provider()

    def late_call(name, *args):
        if fallback and name == "openai":
            raise TimeoutError("primary failed")
        clock[0] = 0.02
        return {"score": 0.9, "reason": "Valid but too late."}

    monkeypatch.setattr(provider, "_call", late_call)
    with pytest.raises(TimeoutError, match="exceeded request deadline"):
        provider.structured("instructions", "scene", rerank.VisualScore, timeout=0.01)
