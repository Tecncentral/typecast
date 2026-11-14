"""Private thread working memory, with a six-hour in-memory lifetime."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
from pathlib import Path
import re
from threading import RLock
from time import monotonic
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / "cache"
TTL_SECONDS = 6 * 60 * 60
THREAD_ID_PATTERN = r"^[a-z0-9-]{4,40}$"
_thread_id_re = re.compile(THREAD_ID_PATTERN)
_memory: dict[str, dict[str, Any]] = {}
_expires: dict[str, float] = {}
_lock = RLock()
_pending: ContextVar[tuple[str, dict[str, Any]] | None] = ContextVar("thread_writes", default=None)
_aliases = {"req": "requirements", "shots": "candidates"}
_files = {"requirements": "requirements.json", "candidates": "candidates.json",
          "shortlist": "shortlist.json", "skeptic": "skeptic.md", "sources": "sources.json"}


class UnknownThread(KeyError):
    """A thread is absent from the index or its working memory has expired."""


def validate_thread_id(thread_id: str) -> str:
    if not isinstance(thread_id, str) or not _thread_id_re.fullmatch(thread_id):
        raise ValueError("thread_id must contain 4–40 lowercase letters, digits, or hyphens")
    return thread_id


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _existing(thread_id: str) -> dict[str, Any]:
    if thread_id not in _memory or _expires.get(thread_id, 0) <= monotonic():
        _memory.pop(thread_id, None)
        _expires.pop(thread_id, None)
        raise UnknownThread("Unknown or expired thread; run a new scout first.")
    return _memory[thread_id]


def save(thread_id: str, name: str, obj: Any) -> None:
    validate_thread_id(thread_id)
    name = _aliases.get(name, name)
    if name not in _files:
        raise ValueError("Unsupported working-memory file")
    pending = _pending.get()
    if pending is not None and pending[0] == thread_id:
        pending[1][name] = obj
        return
    content = str(obj) if name == "skeptic" else json.dumps(_jsonable(obj), indent=2)
    with _lock:
        directory = CACHE_ROOT / "threads" / thread_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / _files[name]
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        if _expires.get(thread_id, 0) <= monotonic():
            _memory.pop(thread_id, None)
        _memory.setdefault(thread_id, {})[name] = obj
        _expires[thread_id] = monotonic() + TTL_SECONDS


def get_thread(thread_id: str) -> dict[str, Any]:
    validate_thread_id(thread_id)
    pending = _pending.get()
    with _lock:
        try:
            record = dict(_existing(thread_id))
        except UnknownThread:
            if pending is None or pending[0] != thread_id or not pending[1]:
                raise
            record = {}
        if pending is not None and pending[0] == thread_id:
            record.update(pending[1])
    for alias, name in _aliases.items():
        if name in record:
            record[alias] = record[name]
    return record


def load(thread_id: str, name: str) -> Any:
    return get_thread(thread_id)[_aliases.get(name, name)]


@contextmanager
def stage_writes(thread_id: str):
    """Keep an engine attempt private until runtime accepts its result."""
    validate_thread_id(thread_id)
    pending: dict[str, Any] = {}
    token = _pending.set((thread_id, pending))
    try:
        yield pending
    finally:
        _pending.reset(token)


def commit(thread_id: str, pending: dict[str, Any]) -> None:
    for name, obj in pending.items():
        save(thread_id, name, obj)


def record_run(thread_id: str, *, engine: str, source_mode: str, timings: dict[str, float],
               notes: list[str] | None = None) -> None:
    with _lock:
        _existing(validate_thread_id(thread_id))["runtime"] = {
            "engine": engine, "source_mode": source_mode, "timings": dict(timings),
            "notes": list(notes or []),
        }


def save_draft(thread_id: str, rank: int, text: str) -> Path:
    get_thread(thread_id)
    directory = CACHE_ROOT / "outbox"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{thread_id}-{rank}.md"
    path.write_text(text, encoding="utf-8")
    return path
