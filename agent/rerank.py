"""Permission-gated visual reranking with cached results and bounded requests."""
from __future__ import annotations
import base64
from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, wait
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import tempfile
from queue import Empty, SimpleQueue
from threading import Condition, Event as ThreadEvent, Lock, Thread
from time import monotonic
from urllib.parse import unquote, urlparse
import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator
from agent.interfaces import Requirements, RunContext
from agent import models
from agent.models import enabled, get_provider
from contracts.schemas import Event, Shot

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = REPO_ROOT / "cache"
PROMPT_PATH = Path(__file__).with_name("prompts") / "rerank.md"
BATCH_PROMPT_PATH = Path(__file__).with_name("prompts") / "rerank_batch.md"
MAX_CONCURRENCY = 5


class _VisionSlots:
    """Physical calls retain their global slot after a caller abandons them."""
    def __init__(self):
        self.condition = Condition()
        self.active = 0

    def acquire(self, *, timeout, limit):
        deadline = monotonic() + timeout
        with self.condition:
            while self.active >= limit:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False
                self.condition.wait(remaining)
            self.active += 1
            return True

    def release(self):
        with self.condition:
            self.active -= 1
            self.condition.notify_all()


_VISION_SLOTS = _VisionSlots()
SHOT_TIMEOUT_S = 20.0
MAX_IMAGE_BYTES = 20 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
CACHE_VERSION = 2


def _choice(name, default, choices):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise ValueError(f"{name} must be one of {sorted(choices)}") from None
    if value not in choices:
        raise ValueError(f"{name} must be one of {sorted(choices)}")
    return value


def configured_pool_size() -> int:
    return _choice("TYPECAST_RERANK_POOL", 10, {10, 20, 30, 40})


class VisionRateLimitError(RuntimeError):
    status_code = 429

    def __init__(self, accounting):
        super().__init__("Vision rate limit reached; further requests stopped")
        self.accounting = accounting


class VisualScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=240)

    @field_validator("reason")
    @classmethod
    def one_line(cls, reason: str) -> str:
        reason = " ".join(reason.split())
        if not reason:
            raise ValueError("A visual reason is required")
        return reason


class IndexedVisualScore(VisualScore):
    index: int = Field(ge=0, le=9, strict=True)


class BatchVisualScores(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scores: list[IndexedVisualScore] = Field(min_length=1, max_length=10)


def _batch_results(value, count):
    result = BatchVisualScores.model_validate(value)
    if len(result.scores) != count or {score.index for score in result.scores} != set(range(count)):
        raise ValueError("Batch must score every supplied image exactly once, with no extra indices")
    return [VisualScore(score=score.score, reason=score.reason)
            for score in sorted(result.scores, key=lambda score: score.index)]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _cache_file(scene: str, shot_id: str) -> Path:
    safe_id = shot_id if re.fullmatch(r"[\w.-]+", shot_id) and shot_id not in {".", ".."} else _digest(shot_id)
    return _score_cache_root() / _digest(scene) / f"{safe_id}.json"


def _score_cache_root() -> Path:
    value = os.getenv("TYPECAST_RERANK_CACHE_DIR")
    if not value:
        return CACHE_ROOT / "rerank"
    directory = (REPO_ROOT / value).resolve()
    if not directory.is_relative_to(CACHE_ROOT.resolve()):
        raise ValueError("TYPECAST_RERANK_CACHE_DIR must remain inside private cache/")
    return directory


def _local_image(image_path: str) -> Path | None:
    parsed = urlparse(image_path)
    if not parsed.scheme and image_path.startswith(("cache/", "/cache/")):
        candidate = CACHE_ROOT / unquote(image_path).lstrip("/").removeprefix("cache/")
    elif Path(image_path).is_absolute():
        # Windows drive letters (C:) are filesystem paths, not URL schemes.
        candidate = Path(image_path)
    elif parsed.scheme:
        return None
    else:
        candidate = Path(image_path)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(CACHE_ROOT.resolve()):
        raise ValueError("Local rerank images must be under cache/")
    return candidate


def _image_input(image_path: str, timeout: float) -> str:
    local = _local_image(image_path)
    if local is not None:
        if local.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError("Image exceeds the local upload limit")
        data = local.read_bytes()
        media_type = mimetypes.guess_type(local.name)[0]
    else:
        if urlparse(image_path).scheme not in {"http", "https"}:
            raise ValueError("Unsupported image URL")
        # Avoid passing private/signed/localhost URLs to the provider.
        with httpx.stream("GET", image_path, timeout=timeout, follow_redirects=False) as response:
            response.raise_for_status()
            media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise ValueError("Image exceeds the local upload limit")
                chunks.append(chunk)
            data = b"".join(chunks)
    if not data or media_type not in IMAGE_TYPES:
        raise ValueError("Expected a supported nonempty image")
    return f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"


def _image_identity(image_path: str) -> str:
    local = _local_image(image_path)
    if local is not None:
        stat = local.stat()
        return _digest(f"{local}:{stat.st_size}:{stat.st_mtime_ns}")
    return _digest(image_path)


def _read_cached(path: Path, identity: dict, output_model=VisualScore):
    try:
        cached = json.loads(path.read_text())
        if cached.get("identity") == identity:
            return output_model.model_validate(cached["result"])
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def _write_cached(path: Path, identity: dict, result: VisualScore) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump({"identity": identity, "result": result.model_dump()}, handle)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def rerank_shots(ctx: RunContext, req: Requirements, shots, k: int = 20) -> list[Shot]:
    original = list(shots)

    def event(text: str):
        ctx.event(Event(type="rerank", agent="interior_scout", text=text))

    if not enabled("TYPECAST_ENABLE_VISION_RERANK"):
        event("Vision rerank skipped: model reranking is disabled; kept embedding order.")
        return original
    if os.getenv("TYPECAST_ALLOW_VISION_UPLOAD", "").strip() != "1":
        event("Vision rerank skipped: TYPECAST_ALLOW_VISION_UPLOAD=1 is required for sponsor-permitted image uploads; kept embedding order.")
        return original
    if isinstance(k, bool) or not isinstance(k, int) or not 0 <= k <= 40:
        raise ValueError("Vision rerank k must be an integer in 0..40")
    concurrency = _choice("TYPECAST_VISION_CONCURRENCY", 5, {5, 10})
    batch_size = _choice("TYPECAST_VISION_BATCH_SIZE", 1, {1, 5, 10})
    cache_root = _score_cache_root()
    mode = "single" if batch_size == 1 else "batch"
    provider_events = SimpleQueue()
    provider = get_provider(vision=True, emit=provider_events.put)
    if not provider.configured():
        event("Vision rerank skipped: no configured vision provider; kept embedding order.")
        return original
    limit = min(k, len(original))
    if not limit:
        return original
    try:
        instructions = (PROMPT_PATH if batch_size == 1 else BATCH_PROMPT_PATH).read_text()
    except OSError:
        event("Vision rerank skipped: prompt unavailable; kept embedding order.")
        return original
    provider_id = getattr(provider, "cache_identity", type(provider).__name__)
    results, pending = {}, []
    cached_count, cache_write_failures = 0, 0
    accounting = {"mode": mode, "pool": k, "candidate_count": limit, "concurrency": concurrency,
                  "batch_size": batch_size, "structured_calls": 0, "images_submitted": 0,
                  "provider_calls": 0, "provider_images": 0}
    counter_lock = Lock()
    for start in range(0, limit, batch_size):
        group = original[start:min(start + batch_size, limit)]
        try:
            if batch_size == 1:
                # Preserve every byte of the valid v2 single-image cache identity.
                text = json.dumps({"scene": req.scene}, sort_keys=True)
                identity = {"version": CACHE_VERSION, "request": _digest(instructions + text),
                            "provider": provider_id, "image": _image_identity(group[0].image_path)}
                path = _cache_file(req.scene, group[0].shot_id)
                cached = _read_cached(path, identity)
                values = [cached] if cached is not None else None
            else:
                text = json.dumps({"scene": req.scene,
                                   "images": [{"index": i} for i in range(len(group))]}, sort_keys=True)
                identity = {"version": 1, "mode": "batch", "batch_size": batch_size,
                            "request": _digest(instructions + text), "provider": provider_id,
                            "members": [{"shot_id": shot.shot_id, "image": _image_identity(shot.image_path)}
                                        for shot in group]}
                path = cache_root / "batch-v1" / _digest(req.scene) / (_digest(json.dumps(identity, sort_keys=True)) + ".json")
                cached = _read_cached(path, identity, BatchVisualScores)
                try:
                    values = _batch_results(cached, len(group)) if cached is not None else None
                except ValueError:
                    values = None
            if values is not None:
                results.update((start + i, value) for i, value in enumerate(values))
                cached_count += len(group)
            else:
                pending.append({"start": start, "shots": group, "path": path,
                                "identity": identity, "text": text})
        except (OSError, ValueError):
            # A missing image invalidates its complete batch context; never quietly
            # send fewer images under a cache key describing the original members.
            continue

    abandoned, rate_limited = ThreadEvent(), ThreadEvent()
    if models.rate_limit_seen():
        rate_limited.set()

    def stopped():
        return (ctx.cancelled.is_set() or abandoned.is_set()
                or rate_limited.is_set() or models.rate_limit_seen())

    def score(job, deadline):
        remaining = max(0.0, deadline - monotonic())
        if not _VISION_SLOTS.acquire(timeout=remaining, limit=concurrency):
            raise TimeoutError("Vision concurrency wait exceeded request deadline")
        try:
            images = []
            for shot in job["shots"]:
                remaining = deadline - monotonic()
                if stopped() or remaining <= 0:
                    raise TimeoutError("Vision request stopped before image load")
                images.append(_image_input(shot.image_path, remaining))
            remaining = deadline - monotonic()
            if stopped() or remaining <= 0:
                raise TimeoutError("Vision request stopped before provider call")
            with counter_lock:
                accounting["structured_calls"] += 1
                accounting["images_submitted"] += len(images)
            kwargs = {"image_url": images[0]} if batch_size == 1 else {"image_urls": images}
            result = provider.structured(instructions, job["text"],
                VisualScore if batch_size == 1 else BatchVisualScores, timeout=remaining, **kwargs)
            if monotonic() > deadline:
                raise TimeoutError("Vision call exceeded request deadline")
            if batch_size == 1:
                result = VisualScore.model_validate(result)
                values = [result]
            else:
                result = BatchVisualScores.model_validate(result)
                values = _batch_results(result, len(images))
            return job, result, values
        except BaseException as error:
            if models.is_rate_limit_error(error):
                models.mark_rate_limit()
                rate_limited.set()
            raise
        finally:
            _VISION_SLOTS.release()

    def drain_provider_events():
        while True:
            try:
                item = provider_events.get_nowait()
            except Empty:
                break
            if item.type == "model_request":
                counts = json.loads(item.text)
                accounting["provider_calls"] += counts["provider_calls"]
                accounting["provider_images"] += counts["images"]
            ctx.event(item)

    queued, active, expired = deque(pending), {}, set()

    def launch(job):
        if stopped():
            return
        future = Future()
        deadline = monotonic() + SHOT_TIMEOUT_S
        active[future] = deadline

        def run():
            if not future.set_running_or_notify_cancel():
                return
            try:
                future.set_result(score(job, deadline))
            except BaseException as error:
                future.set_exception(error)

        Thread(target=run, name="typecast-rerank", daemon=True).start()

    fatal = None
    try:
        while queued and len(active) < concurrency and not stopped():
            launch(queued.popleft())
        while active and not stopped():
            live = [future for future in active if future not in expired]
            if not live:
                break
            remaining = max(0.0, min(active[future] for future in live) - monotonic())
            done, _ = wait(active, timeout=remaining, return_when=FIRST_COMPLETED)
            for future in done:
                deadline = active.pop(future)
                if future in expired:
                    expired.remove(future)
                    continue
                try:
                    job, result, values = future.result()
                    if monotonic() <= deadline and not stopped():
                        results.update((job["start"] + i, value) for i, value in enumerate(values))
                        try:
                            _write_cached(job["path"], job["identity"], result)
                        except OSError:
                            cache_write_failures += 1
                except BaseException as error:
                    if models.is_rate_limit_error(error):
                        rate_limited.set()
                    elif not isinstance(error, Exception):
                        fatal = error
            now = monotonic()
            expired.update(future for future, deadline in active.items() if now >= deadline)
            drain_provider_events()
            if fatal is not None:
                break
            while queued and len(active) < concurrency and not stopped():
                launch(queued.popleft())
    finally:
        abandoned.set()
    drain_provider_events()
    limited = rate_limited.is_set() or models.rate_limit_seen()
    accounting.update(images_attempted=accounting["images_submitted"], images_scored=len(results),
                      cached=cached_count, failures=limit - len(results), rate_limited=limited,
                      cache_write_failures=cache_write_failures)
    if limited:
        ctx.event(Event(type="rate_limit", agent="interior_scout",
                        text="Vision rate_limited=1; no further calls scheduled."))
    event(f"Vision rerank: {len(results)} of {limit} views scored ({cached_count} cached); "
          f"{limit - len(results)} failures kept original scores; {cache_write_failures} cache writes failed. "
          f"mode={mode} pool={k} concurrency={concurrency} batch_size={batch_size} rate_limited={int(limited)}; "
          f"accounting={json.dumps(accounting, sort_keys=True)}")
    if limited:
        raise VisionRateLimitError(dict(accounting))
    if fatal is not None:
        raise fatal
    ranked = [shot.model_copy(update=results[index].model_dump()) if index in results else shot
              for index, shot in enumerate(original[:limit])]
    ranked.sort(key=lambda shot: -(shot.score if shot.score is not None else 0.0))
    return ranked + original[limit:]
