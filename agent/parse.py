"""Requirement parser interface."""
from agent.interfaces import Requirements


def parse_scene(scene: str) -> Requirements:
    from agent.pipeline import parse_scene as legacy_parse
    data = legacy_parse(scene)
    return Requirements(**data, explicit_fields={key for key in ("trucks", "cars") if data[key]})
