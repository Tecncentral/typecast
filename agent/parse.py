"""Validated scene extraction with an independent deterministic fallback."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Callable, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from agent.interfaces import Requirements
from agent.models import enabled, get_provider
from contracts.schemas import Event

PROMPT_PATH = Path(__file__).with_name("prompts") / "parse_scene.md"
ERAS = {"1950s": (None, 1962), "1960s": (None, 1972), "1970s": (None, 1982),
        "1980s": (None, 1992), "1990s": (None, 2002), "modern": (2005, None)}
SceneField = Literal["city", "era_label", "year_min", "year_max", "trucks", "cars",
                     "min_area_m2", "min_ceiling_m", "focal_mm", "frame_width_m",
                     "look", "mood", "time_of_day"]


class SceneFields(BaseModel):
    """Use a list for provider JSON Schema, rather than uniqueItems from a set."""
    model_config = ConfigDict(extra="forbid")
    city: str = "Los Angeles"
    era_label: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    trucks: int = Field(default=0, ge=0)
    cars: int = Field(default=0, ge=0)
    min_area_m2: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    min_ceiling_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    focal_mm: float = Field(default=24.0, gt=0, allow_inf_nan=False)
    frame_width_m: float = Field(default=6.0, gt=0, allow_inf_nan=False)
    look: str | None = None
    mood: str | None = None
    time_of_day: str | None = None
    explicit_fields: list[SceneField] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_year_range(self):
        if self.year_min is not None and self.year_max is not None and self.year_min > self.year_max:
            raise ValueError("Reversed year range")
        return self


def rule_parse_scene(scene: str) -> Requirements:
    """Original pipeline regex parser, extended for explicit zero and units."""
    s = scene.lower()
    req = Requirements(scene=scene, city="Houston" if "houston" in s else "Los Angeles")
    explicit = req.explicit_fields
    if re.search(r"\b(?:houston|los angeles|l\.?a\.?)\b", s):
        explicit.add("city")
    counts = {"zero": 0, "no": 0, "one": 1, "two": 2, "three": 3, "four": 4,
              "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    number = r"(?:\d+|" + "|".join(counts) + ")"
    for field, noun in (("trucks", "trucks?"), ("cars", r"(?:crew\s*)?cars?")):
        matches = list(re.finditer(rf"\b({number})\s*{noun}\b", s))
        if matches:
            value = matches[-1].group(1)
            setattr(req, field, int(value) if value.isdigit() else counts[value])
            explicit.add(field)
    for era, (lo, hi) in ERAS.items():
        if era in s:
            req.era_label, req.year_min, req.year_max = era, lo, hi
            explicit.update({"era_label", "year_min", "year_max"})
    if m := re.search(r"\b(\d+(?:\.\d+)?)\s*(?:mm|millimet(?:er|re)s?)\b", s):
        req.focal_mm = float(m.group(1)) or 24.0
        explicit.add("focal_mm")
    area_unit = r"(?:m2|m²|sq\.?\s*m|square\s*met(?:er|re)s?|sq\.?\s*ft|square\s*feet|sqft)"
    if m := re.search(rf"\b(\d+(?:\.\d+)?)\s*({area_unit})\b", s):
        req.min_area_m2 = float(m.group(1)) * (0.09290304 if re.search(r"ft|feet", m.group(2)) else 1)
        explicit.add("min_area_m2")
    unit = r"(?:m|met(?:er|re)s?|ft|feet|foot)"
    ceiling = re.search(rf"\b(\d+(?:\.\d+)?)\s*({unit})\s*(?:high\s+)?ceilings?\b", s)
    ceiling = ceiling or re.search(rf"\bceilings?\s*(?:height\s*)?(?:of\s*|at least\s*|[:=]\s*)?(\d+(?:\.\d+)?)\s*({unit})\b", s)
    if ceiling:
        req.min_ceiling_m = float(ceiling.group(1)) * (0.3048 if ceiling.group(2) in {"ft", "feet", "foot"} else 1)
        explicit.add("min_ceiling_m")
    width = re.search(rf"\bframe\s*(?:width\s*)?(?:of\s*|[:=]\s*)?(\d+(?:\.\d+)?)\s*({unit})\b", s)
    width = width or re.search(rf"\b(\d+(?:\.\d+)?)\s*({unit})\s*(?:wide\s*)?frame\b", s)
    if width:
        req.frame_width_m = float(width.group(1)) * (0.3048 if width.group(2) in {"ft", "feet", "foot"} else 1) or 6.0
        explicit.add("frame_width_m")
    looks = [term for term in ("drop ceiling", "fluorescent", "exposed brick", "industrial", "open room", "wood paneling") if term in s]
    if looks:
        req.look = ", ".join(looks)
        explicit.add("look")
    if m := re.search(r"\b(noir|gritty|tense|warm|moody|bright|dark|cheerful|ominous)\b", s):
        req.mood = m.group(1)
        explicit.add("mood")
    if m := re.search(r"\b(night|day|dawn|dusk|evening|morning|afternoon|noon)\b", s):
        req.time_of_day = m.group(1)
        explicit.add("time_of_day")
    return Requirements.model_validate(req.model_dump())


def parse_scene(scene: str, *, emit: Callable[[Event], None] | None = None) -> Requirements:
    fallback = rule_parse_scene(scene)
    if not enabled("TYPECAST_ENABLE_MODEL_PARSE"):
        fallback.parse_note = "Parsed without a model: model parsing is disabled."
        return fallback
    provider_events = []

    def on_event(event: Event):
        provider_events.append(event)
        if emit:
            emit(event)

    provider = get_provider(emit=on_event)
    if not provider.configured():
        fallback.parse_note = "Parsed without a model: no configured text provider."
        return fallback
    try:
        parsed = provider.structured(PROMPT_PATH.read_text(), scene, SceneFields, timeout=20.0)
        values = SceneFields.model_validate(parsed).model_dump()
        explicit = set(values.pop("explicit_fields"))
        for field in ("trucks", "cars"):
            if field in fallback.explicit_fields:
                values[field] = getattr(fallback, field)
                explicit.add(field)
        return Requirements(scene=scene, **values, explicit_fields=explicit,
                            parsed_with_model=True,
                            parse_note=" ".join(event.text for event in provider_events) or None)
    except Exception as exc:
        note = f"Parsed without a model: structured extraction failed ({type(exc).__name__})."
        fallback.parse_note = " ".join([*(event.text for event in provider_events), note])
        return fallback
