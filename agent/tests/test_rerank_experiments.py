"""Offline batching, context cache, promotion, concurrency and hard-stop checks."""
import base64
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from agent import models, rerank
from agent.interfaces import Requirements, RunContext
from contracts.schemas import Event, Shot

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII=")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    for name in ("TYPECAST_RERANK_POOL", "TYPECAST_VISION_CONCURRENCY", "TYPECAST_VISION_BATCH_SIZE",
                 "TYPECAST_RERANK_CACHE_DIR", "TYPECAST_FALLBACK_PROVIDER", "TYPECAST_FALLBACK_MODEL", "FALLBACK_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TYPECAST_ENABLE_VISION_RERANK", "1")
    monkeypatch.setenv("TYPECAST_VISION_BATCH_SIZE", "1")
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "1")
    monkeypatch.setenv("TYPECAST_LLM_PROVIDER", "openai")
    monkeypatch.setenv("TYPECAST_VISION_MODEL", "test-only-model")
    monkeypatch.setenv("VISION_API_KEY", "test-only-key")
    monkeypatch.setattr(rerank, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(rerank, "CACHE_ROOT", tmp_path / "cache")
    models.reset_rate_limit()
    yield
    models.reset_rate_limit()


def shots(count=45):
    rerank.CACHE_ROOT.mkdir(exist_ok=True)
    result = []
    for index in range(count):
        path = rerank.CACHE_ROOT / f"test-{index}.png"
        path.write_bytes(PNG + f"|{index}".encode())
        result.append(Shot(shot_id=f"test-{index}", property_id="test-property", model_id="test-model",
                           sweep_id=f"test-sweep-{index}", heading_deg=0, image_path=str(path), score=1 - index / 100))
    return result


class FakeVision:
    cache_identity = "fake:experiment"

    def __init__(self, invalid=None, delay=.002):
        self.calls, self.active, self.max_active = [], 0, 0
        self.lock = threading.Lock()
        self.invalid, self.delay = invalid, delay
        self.emit = lambda event: None

    def configured(self):
        return True

    def structured(self, instructions, text, output_model, **kwargs):
        images = kwargs.get("image_urls") or [kwargs["image_url"]]
        with self.lock:
            self.calls.append((text, list(images)))
            self.active += 1
            self.max_active = max(self.active, self.max_active)
        try:
            self.emit(Event(type="model_request", agent="models", text=json.dumps(
                {"provider_calls": 1, "images": len(images), "vision": True})))
            time.sleep(self.delay)
            if output_model is rerank.VisualScore:
                ordinal = int(base64.b64decode(images[0].split(",", 1)[1]).rsplit(b"|", 1)[1])
                return {"score": ordinal / 100, "reason": "Visible test cues."}
            assert json.loads(text)["images"] == [{"index": i} for i in range(len(images))]
            values = [{"index": i, "score": (i + 1) / (len(images) + 1), "reason": "Visible test cues."}
                      for i in reversed(range(len(images)))]
            return {"scores": self.invalid(values) if self.invalid else values}
        finally:
            with self.lock:
                self.active -= 1


def install(monkeypatch, provider):
    def get(**kwargs):
        provider.emit = kwargs["emit"]
        return provider
    monkeypatch.setattr(rerank, "get_provider", get)


def counters(events):
    return json.loads(events[-1].text.split("accounting=", 1)[1])


def test_selected_production_defaults_and_explicit_pool_override(monkeypatch):
    for name in ("TYPECAST_RERANK_POOL", "TYPECAST_VISION_CONCURRENCY", "TYPECAST_VISION_BATCH_SIZE"):
        monkeypatch.delenv(name, raising=False)
    assert rerank.configured_pool_size() == 20
    original, fake, events = shots(), FakeVision(), []
    install(monkeypatch, fake)
    ctx, req = RunContext("selected-defaults", emit=events.append), Requirements(scene="Selected visual brief")
    ranked = rerank.rerank_shots(ctx, req, original, k=rerank.configured_pool_size())
    stats = counters(events)
    assert (stats["pool"], stats["concurrency"], stats["batch_size"], stats["mode"]) == (20, 5, 5, "batch")
    assert stats["images_scored"] == 20 and stats["provider_calls"] == 4
    assert all(len(images) == 5 for _, images in fake.calls)
    assert ranked[20:] == original[20:]
    overridden = rerank.rerank_shots(ctx, req, original, k=10)
    assert counters(events)["pool"] == counters(events)["images_scored"] == 10
    assert overridden[10:] == original[10:]


@pytest.mark.parametrize("batch_size", [1, 5, 10])
def test_pool40_promotes_later_candidates_preserves_tail_and_reuses_cache(monkeypatch, batch_size):
    original = shots()
    fake = FakeVision()
    install(monkeypatch, fake)
    monkeypatch.setenv("TYPECAST_VISION_BATCH_SIZE", str(batch_size))
    events = []
    ctx, req = RunContext("batch-promotion", emit=events.append), Requirements(scene="Authored test visual scene")
    ranked = rerank.rerank_shots(ctx, req, original, k=40)
    stats = counters(events)
    assert stats["images_scored"] == stats["images_submitted"] == stats["provider_images"] == 40
    assert stats["structured_calls"] == stats["provider_calls"] == 40 // batch_size
    assert stats["cached"] == stats["failures"] == 0 and not stats["rate_limited"]
    assert {shot.shot_id for shot in ranked[:10]} & {shot.shot_id for shot in original[10:40]}
    assert ranked[40:] == original[40:] and len(ranked) == len(original)
    assert [shot.score for shot in original] == [1 - i / 100 for i in range(45)]
    before = len(fake.calls)
    assert rerank.rerank_shots(ctx, req, original, k=40) == ranked
    assert len(fake.calls) == before
    assert counters(events)["cached"] == 40 and counters(events)["provider_calls"] == 0


def test_batch_cache_separates_size_order_image_context_and_single_baseline(monkeypatch):
    original = shots(10)
    fake = FakeVision()
    install(monkeypatch, fake)
    ctx, req = RunContext("batch-context"), Requirements(scene="Same authored visual brief")
    rerank.rerank_shots(ctx, req, original, k=10)
    assert len(fake.calls) == 10
    monkeypatch.setenv("TYPECAST_VISION_BATCH_SIZE", "5")
    rerank.rerank_shots(ctx, req, original, k=10)
    assert len(fake.calls) == 12
    reordered = [original[1], original[0], *original[2:]]
    rerank.rerank_shots(ctx, req, reordered, k=10)
    assert len(fake.calls) == 13
    Path(reordered[0].image_path).write_bytes(PNG + b"|1|changed")
    rerank.rerank_shots(ctx, req, reordered, k=10)
    assert len(fake.calls) == 14
    monkeypatch.setenv("TYPECAST_VISION_BATCH_SIZE", "10")
    rerank.rerank_shots(ctx, req, reordered, k=10)
    assert len(fake.calls) == 15
    monkeypatch.setenv("TYPECAST_VISION_BATCH_SIZE", "1")
    rerank.rerank_shots(ctx, req, original[2:], k=8)
    assert len(fake.calls) == 15


@pytest.mark.parametrize("invalid", [
    lambda values: values[:-1],
    lambda values: [values[0], *values[1:-1], values[0]],
    lambda values: values + [{"index": 9, "score": .9, "reason": "Extra image"}],
    lambda values: [{**value, "index": str(value["index"])} for value in values],
    lambda values: [{**value, "score": float("nan")} for value in values],
    lambda values: [{**value, "reason": " "} for value in values],
])
def test_invalid_batch_rejected_without_cache_or_partial_scores(monkeypatch, invalid):
    original = shots(5)
    install(monkeypatch, FakeVision(invalid=invalid))
    monkeypatch.setenv("TYPECAST_VISION_BATCH_SIZE", "5")
    events = []
    assert rerank.rerank_shots(RunContext("invalid-batch", emit=events.append), Requirements(scene="test"), original, k=10) == original
    assert counters(events)["failures"] == 5 and counters(events)["images_scored"] == 0
    assert not list(rerank.CACHE_ROOT.rglob("*.json"))


@pytest.mark.parametrize("concurrency", [5, 10])
def test_configured_concurrency_is_real_and_bounded(monkeypatch, concurrency):
    fake = FakeVision(delay=.02)
    install(monkeypatch, fake)
    monkeypatch.setenv("TYPECAST_VISION_CONCURRENCY", str(concurrency))
    rerank.rerank_shots(RunContext("concurrency"), Requirements(scene="test"), shots(), k=40)
    assert fake.max_active == concurrency and fake.active == 0


@pytest.mark.parametrize(("name", "value"), [("TYPECAST_RERANK_POOL", "41"), ("TYPECAST_RERANK_POOL", "bad"),
    ("TYPECAST_VISION_CONCURRENCY", "11"), ("TYPECAST_VISION_BATCH_SIZE", "2")])
def test_invalid_settings_fail_before_model_calls(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(rerank, "get_provider", lambda **kwargs: pytest.fail("Invalid setting reached a provider"))
    with pytest.raises(ValueError):
        rerank.configured_pool_size() if name == "TYPECAST_RERANK_POOL" else rerank.rerank_shots(RunContext("invalid"), Requirements(), [], k=10)


def test_attempt_cache_is_private_and_isolated(monkeypatch, tmp_path):
    original = shots(1)
    fake = FakeVision()
    install(monkeypatch, fake)
    for attempt in ("attempt-a", "attempt-b", "attempt-a"):
        monkeypatch.setenv("TYPECAST_RERANK_CACHE_DIR", f"cache/experiments/{attempt}")
        rerank.rerank_shots(RunContext("cache-isolation"), Requirements(scene="test"), original, k=10)
    assert len(fake.calls) == 2
    monkeypatch.setenv("TYPECAST_RERANK_CACHE_DIR", str(tmp_path / "outside-cache"))
    with pytest.raises(ValueError, match="private cache"):
        rerank.rerank_shots(RunContext("invalid-cache"), Requirements(scene="test"), original, k=10)


@pytest.mark.parametrize("provider_name", ["openai", "anthropic"])
def test_installed_sdk_adapters_send_ordered_multi_image_blocks(monkeypatch, provider_name):
    import openai
    import anthropic
    seen, events = {}, []
    answer = rerank.BatchVisualScores(scores=[
        rerank.IndexedVisualScore(index=0, score=.2, reason="First view"),
        rerank.IndexedVisualScore(index=1, score=.9, reason="Second view")])

    class Client:
        def __init__(self, **kwargs):
            seen["client"] = kwargs
            self.responses = self.messages = SimpleNamespace(parse=self.parse)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def parse(self, **kwargs):
            seen["request"] = kwargs
            return SimpleNamespace(output_parsed=answer, parsed_output=answer)

    monkeypatch.setattr(openai, "OpenAI", Client)
    monkeypatch.setattr(anthropic, "Anthropic", Client)
    monkeypatch.setenv("TYPECAST_LLM_PROVIDER", provider_name)
    monkeypatch.setenv("TYPECAST_REASONING_EFFORT", "xhigh")
    images = ["data:image/png;base64,QQ==", "data:image/png;base64,Qg=="]
    result = models.get_provider(vision=True, emit=events.append).structured(
        "test instructions", "test scene", rerank.BatchVisualScores, image_urls=images)
    assert result == answer and seen["client"]["max_retries"] == 0
    request = seen["request"]
    content = request["input"][0]["content"] if provider_name == "openai" else request["messages"][0]["content"]
    assert len(content) == 3
    if provider_name == "openai":
        assert [block["image_url"] for block in content[1:]] == images
        assert request["reasoning"] == {"effort": "xhigh"} and request["store"] is False
    else:
        assert [block["source"]["data"] for block in content[1:]] == ["QQ==", "Qg=="]
    assert json.loads(events[0].text) == {"provider_calls": 1, "images": 2, "vision": True}


def test_sdk_rate_limit_latches_without_fallback_and_preserves_batch_budget_boundary(monkeypatch):
    import httpx2
    from openai import RateLimitError
    monkeypatch.setenv("TYPECAST_FALLBACK_PROVIDER", "anthropic")
    monkeypatch.setenv("TYPECAST_FALLBACK_MODEL", "fake-backup")
    monkeypatch.setenv("FALLBACK_API_KEY", "test-only-backup")
    seen, events = [], []
    provider = models.get_provider(vision=True, emit=events.append)
    api_error = RateLimitError("private provider text", response=httpx2.Response(
        429, request=httpx2.Request("POST", "https://example.invalid")), body=None)
    wrapped = RuntimeError("private wrapper text")
    wrapped.__cause__ = api_error
    def call(name, model, key, instructions, text, output_model, image_url, timeout):
        seen.append((name, image_url))
        raise wrapped
    monkeypatch.setattr(provider, "_call", call)
    for _ in range(2):
        with pytest.raises(models.ModelRateLimitError) as error:
            provider.structured("test", "test", rerank.BatchVisualScores, image_urls=["image-a", "image-b"])
        assert "private" not in str(error.value)
    assert seen == [("openai", ["image-a", "image-b"])] and models.rate_limit_seen()
    assert len(events) == 1 and events[0].type == "rate_limit" and "rate_limited=1" in events[0].text


@pytest.mark.parametrize("batch_size", [1, 5, 10])
def test_first429_stops_queue_and_abandons_active_calls_without_late_cache(monkeypatch, batch_size):
    release = threading.Event()
    idle = threading.Event()
    class Limited(FakeVision):
        def structured(self, instructions, text, output_model, **kwargs):
            images = kwargs.get("image_urls") or [kwargs["image_url"]]
            with self.lock:
                self.calls.append((text, images))
                number = len(self.calls)
                self.active += 1
            try:
                self.emit(Event(type="model_request", agent="models", text=json.dumps(
                    {"provider_calls": 1, "images": len(images), "vision": True})))
                if number == 1:
                    time.sleep(.015)
                    raise models.ModelRateLimitError("controlled rate limit")
                release.wait(1)
                return {"score": .9, "reason": "Late result"} if batch_size == 1 else {
                    "scores": [{"index": i, "score": .9, "reason": "Late result"} for i in range(len(images))]}
            finally:
                with self.lock:
                    self.active -= 1
                    if not self.active: idle.set()
    fake = Limited()
    install(monkeypatch, fake)
    monkeypatch.setenv("TYPECAST_VISION_BATCH_SIZE", str(batch_size))
    events = []
    original, ctx, req = shots(), RunContext("rate-limit", emit=events.append), Requirements(scene="test")
    try:
        with pytest.raises(rerank.VisionRateLimitError) as error:
            rerank.rerank_shots(ctx, req, original, k=40)
        assert models.rate_limit_seen() and error.value.accounting["rate_limited"]
        count = len(fake.calls)
        assert count <= min(5, 40 // batch_size)
        assert any(event.type == "rate_limit" for event in events)
        assert counters(events)["rate_limited"]
        with pytest.raises(rerank.VisionRateLimitError):
            rerank.rerank_shots(ctx, req, original, k=40)
        assert len(fake.calls) == count
        saved = list(events)
    finally:
        release.set()
        assert idle.wait(1)
    assert events == saved and not list(rerank.CACHE_ROOT.rglob("*.json"))


def test_ten_abandoned_physical_calls_block_a_later_five_call_run(monkeypatch):
    release, idle = threading.Event(), threading.Event()
    class Blocking(FakeVision):
        def structured(self, *args, **kwargs):
            with self.lock:
                self.calls.append(1)
                self.active += 1
            try:
                release.wait(1)
                return {"score": .9, "reason": "Late result"}
            finally:
                with self.lock:
                    self.active -= 1
                    if not self.active: idle.set()
    fake = Blocking()
    install(monkeypatch, fake)
    monkeypatch.setattr(rerank, "SHOT_TIMEOUT_S", .04)
    monkeypatch.setenv("TYPECAST_VISION_CONCURRENCY", "10")
    original, ctx, req = shots(), RunContext("abandoned-ten"), Requirements(scene="test")
    try:
        assert rerank.rerank_shots(ctx, req, original, k=40) == original
        assert len(fake.calls) == fake.active == 10
        monkeypatch.setenv("TYPECAST_VISION_CONCURRENCY", "5")
        assert rerank.rerank_shots(ctx, req, original, k=40) == original
        assert len(fake.calls) == 10
    finally:
        release.set()
        assert idle.wait(1)
    assert not list(rerank.CACHE_ROOT.rglob("*.json"))


def test_pre_cancelled_outer_run_starts_no_vision_calls_or_cache_writes(monkeypatch):
    original = shots()
    fake = FakeVision()
    install(monkeypatch, fake)
    ctx = RunContext("pre-cancelled")
    ctx.cancelled.set()
    assert rerank.rerank_shots(ctx, Requirements(scene="test"), original, k=40) == original
    assert not fake.calls and not list(rerank.CACHE_ROOT.rglob("*.json"))


@pytest.mark.parametrize("batch_size", [1, 5])
def test_outer_cancellation_during_wave_stops_queue_and_late_cache_writes(monkeypatch, batch_size):
    started, release = threading.Event(), threading.Event()
    class Blocking(FakeVision):
        def structured(self, instructions, text, output_model, **kwargs):
            images = kwargs.get("image_urls") or [kwargs["image_url"]]
            with self.lock:
                self.calls.append((text, images))
                if len(self.calls) == 5:
                    started.set()
            release.wait(1)
            if batch_size == 1:
                return {"score": .9, "reason": "Completed after cancellation"}
            return {"scores": [{"index": i, "score": .9, "reason": "Completed after cancellation"}
                                for i in range(len(images))]}
    fake = Blocking()
    install(monkeypatch, fake)
    monkeypatch.setenv("TYPECAST_VISION_BATCH_SIZE", str(batch_size))
    original, ctx = shots(), RunContext("cancel-active-wave")
    outcome = {}
    def run():
        try:
            outcome["ranked"] = rerank.rerank_shots(ctx, Requirements(scene="test"), original, k=40)
        except BaseException as error:
            outcome["error"] = error
    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert started.wait(1)
        ctx.cancelled.set()
    finally:
        release.set()
        worker.join(1)
    assert not worker.is_alive() and "error" not in outcome
    assert outcome["ranked"] == original and len(fake.calls) == 5
    assert not list(rerank.CACHE_ROOT.rglob("*.json"))
