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
from threading import BoundedSemaphore, Event as ThreadEvent, Thread
from time import monotonic
from urllib.parse import unquote, urlparse
import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator
from agent.interfaces import Requirements, RunContext
from agent.models import enabled, get_provider
from contracts.schemas import Event, Shot

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = REPO_ROOT / "cache"
PROMPT_PATH = Path(__file__).with_name("prompts") / "rerank.md"
MAX_CONCURRENCY = 5
# Abandoned calls retain their slot until they really finish, even across scouts.
_VISION_SLOTS = BoundedSemaphore(MAX_CONCURRENCY)
SHOT_TIMEOUT_S = 20.0
MAX_IMAGE_BYTES = 20 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
CACHE_VERSION = 1


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


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _cache_file(scene: str, shot_id: str) -> Path:
    safe_id = shot_id if re.fullmatch(r"[\w.-]+", shot_id) and shot_id not in {".", ".."} else _digest(shot_id)
    return CACHE_ROOT / "rerank" / _digest(scene) / f"{safe_id}.json"


def _local_image(image_path: str) -> Path | None:
    parsed = urlparse(image_path)
    if not parsed.scheme and image_path.startswith(("cache/", "/cache/")):
        candidate = CACHE_ROOT / unquote(image_path).lstrip("/").removeprefix("cache/")
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


def _read_cached(path: Path, identity: dict) -> VisualScore | None:
    try:
        cached = json.loads(path.read_text())
        if cached.get("identity") == identity:
            return VisualScore.model_validate(cached["result"])
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
    # Workers can only enqueue provider events. Only this caller emits or writes
    # cache files, so an abandoned worker cannot mutate the finished run.
    provider_events = SimpleQueue()
    provider = get_provider(vision=True, emit=provider_events.put)
    if not provider.configured():
        event("Vision rerank skipped: no configured vision provider; kept embedding order.")
        return original
    limit = min(max(0, k), 20, len(original))
    if not limit:
        return original
    try:
        instructions = PROMPT_PATH.read_text()
    except OSError:
        event("Vision rerank skipped: prompt unavailable; kept embedding order.")
        return original
    text = json.dumps(req.model_dump(exclude={"explicit_fields", "parsed_with_model", "parse_note"}), sort_keys=True)
    fingerprint = _digest(instructions + text)
    provider_id = getattr(provider, "cache_identity", type(provider).__name__)
    results, pending = {}, []
    failures, cached_count, cache_write_failures = 0, 0, 0
    for index, shot in enumerate(original[:limit]):
        try:
            identity = {"version": CACHE_VERSION, "request": fingerprint, "provider": provider_id,
                        "image": _image_identity(shot.image_path)}
            path = _cache_file(req.scene, shot.shot_id)
            cached = _read_cached(path, identity)
            if cached is not None:
                results[index] = cached
                cached_count += 1
            else:
                pending.append((index, shot, path, identity))
        except Exception:
            failures += 1

    abandoned = ThreadEvent()

    def score(item, deadline):
        index, shot, path, identity = item
        remaining = max(0.0, deadline - monotonic())
        if not _VISION_SLOTS.acquire(timeout=remaining):
            raise TimeoutError("Vision concurrency wait exceeded shot deadline")
        try:
            remaining = deadline - monotonic()
            if abandoned.is_set() or remaining <= 0:
                raise TimeoutError("Shot deadline expired before image load")
            image = _image_input(shot.image_path, remaining)
            remaining = deadline - monotonic()
            if abandoned.is_set() or remaining <= 0:
                raise TimeoutError("Image load exceeded shot deadline")
            result = provider.structured(instructions, text, VisualScore, image_url=image, timeout=remaining)
            result = VisualScore.model_validate(result)
            if monotonic() > deadline:
                raise TimeoutError("Vision call exceeded shot deadline")
            return index, result, path, identity
        finally:
            _VISION_SLOTS.release()

    def drain_provider_events():
        while True:
            try:
                ctx.event(provider_events.get_nowait())
            except Empty:
                break

    queued = deque(pending)
    active, expired = {}, set()

    def launch(item):
        future = Future()
        deadline = monotonic() + SHOT_TIMEOUT_S
        active[future] = deadline

        def run():
            if not future.set_running_or_notify_cancel():
                return
            try:
                future.set_result(score(item, deadline))
            except BaseException as exc:
                future.set_exception(exc)

        # Daemon workers do not block shutdown if a transport ignores timeout.
        # A replacement starts only once its predecessor has actually finished.
        Thread(target=run, name="typecast-rerank", daemon=True).start()

    try:
        for _ in range(min(MAX_CONCURRENCY, len(queued))):
            launch(queued.popleft())
        while active:
            live = [future for future in active if future not in expired]
            if not live:
                # Every remaining physical worker is stalled. Do not replace
                # them or start queued uploads after returning to the caller.
                failures += len(queued)
                break
            remaining = max(0.0, min(active[future] for future in live) - monotonic())
            done, _ = wait(active, timeout=remaining, return_when=FIRST_COMPLETED)
            for future in done:
                deadline = active.pop(future)
                if future in expired:
                    expired.remove(future)
                elif monotonic() > deadline:
                    failures += 1
                else:
                    try:
                        index, result, path, identity = future.result()
                        results[index] = result
                        try:
                            _write_cached(path, identity, result)
                        except OSError:
                            cache_write_failures += 1
                    except Exception:
                        failures += 1
                if queued:
                    launch(queued.popleft())
            now = monotonic()
            for future, deadline in active.items():
                if future not in expired and now >= deadline:
                    expired.add(future)
                    failures += 1
            drain_provider_events()
    finally:
        abandoned.set()
    drain_provider_events()
    ranked = [shot.model_copy(update=results[index].model_dump()) if index in results else shot
              for index, shot in enumerate(original[:limit])]
    ranked.sort(key=lambda shot: -(shot.score if shot.score is not None else 0.0))
    event(f"Vision rerank: {len(results)} of {limit} views scored ({cached_count} cached); "
          f"{failures} failures kept original scores; {cache_write_failures} cache writes failed.")
    return ranked + original[limit:]
