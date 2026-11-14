"""Shared execution and requirement contracts for both scouting engines."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from threading import RLock
from typing import Callable, Literal

from pydantic import BaseModel, Field
from contracts.schemas import Event

Emit = Callable[[Event], None]


def null_emit(event: Event) -> None:
    pass


@dataclass
class RunContext:
    thread_id: str
    emit: Emit = null_emit
    engine: Literal["fixed", "deep"] = "fixed"
    source_mode: Literal["mock", "live"] = "mock"
    timings: dict[str, float] = field(default_factory=dict)
    started_at: float = field(default_factory=perf_counter)
    _event_lock: object = field(default_factory=RLock, repr=False)

    def event(self, event: Event) -> None:
        with self._event_lock:
            event.ts = max(0.0, perf_counter() - self.started_at)
            event.engine = self.engine
            self.emit(event)


class Requirements(BaseModel):
    scene: str = ""
    city: str = "Los Angeles"
    era_label: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    trucks: int = Field(default=0, ge=0)
    cars: int = Field(default=0, ge=0)
    min_area_m2: float | None = Field(default=None, ge=0)
    min_ceiling_m: float | None = Field(default=None, ge=0)
    focal_mm: float = Field(default=24.0, gt=0)
    frame_width_m: float = Field(default=6.0, gt=0)
    look: str | None = None
    mood: str | None = None
    time_of_day: str | None = None
    explicit_fields: set[str] = Field(default_factory=set)
    parsed_with_model: bool = False
    parse_note: str | None = None

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)


@contextmanager
def timed(ctx: RunContext, name: str):
    started = perf_counter()
    try:
        yield
    finally:
        ms = (perf_counter() - started) * 1000
        with ctx._event_lock:
            ctx.timings[name] = ctx.timings.get(name, 0.0) + ms
            ctx.event(Event(type="tool", agent=name, ms=ms))
