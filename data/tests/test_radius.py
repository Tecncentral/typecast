"""Radius filter behaviours. Wholly synthetic points; no network, no kit."""

import ast
import math
from pathlib import Path

import pytest

from data import radius
from data.radius import haversine_km, within_radius

BASE = {"lat": 34.0, "lon": -118.0}


def row(pid, lat, lon):
    return {"property_id": pid, "lat": lat, "lon": lon}


def ids(result):
    return [r["property_id"] for r in result["results"]]


def test_known_distances():
    assert haversine_km(0, 0, 1, 0) == pytest.approx(111.195, abs=0.001)
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.195, abs=0.001)
    assert haversine_km(40.7128, -74.0060, 51.5074, -0.1278) == pytest.approx(
        5570, abs=15
    )
    assert haversine_km(0, 179.9, 0, -179.9) == pytest.approx(22.24, abs=0.01), (
        "across the antimeridian"
    )
    assert haversine_km(34.0, -118.0, 34.0, -118.0) == 0
    assert haversine_km(1, 2, 3, 4) == pytest.approx(haversine_km(3, 4, 1, 2))


def test_result_shape_label_and_rounded_distance():
    result = within_radius({"lat": 0, "lon": 0}, 200, [row("a", 1, 0)])
    assert result["label"] == "straight-line distance, not drive time" == radius.LABEL
    assert result["results"] == [{"property_id": "a", "distance_km": 111.195}]
    assert result["excluded_missing_coordinates"] == 0
    assert result["base"] == {"lat": 0.0, "lon": 0.0} and result["max_km"] == 200


def test_results_are_nearest_first_whatever_the_input_order():
    rows = [
        row("far", 34.05, -118.0),
        row("near", 34.001, -118.0),
        row("mid", 34.02, -118.0),
    ]
    assert ids(within_radius(BASE, 20, rows)) == ["near", "mid", "far"]
    assert ids(within_radius(BASE, 20, rows[::-1])) == ["near", "mid", "far"]
    distances = [r["distance_km"] for r in within_radius(BASE, 20, rows)["results"]]
    assert distances == sorted(distances)


def test_ties_are_ordered_by_property_id():
    rows = [row("b", 34.01, -118.0), row("a", 34.01, -118.0), row("c", 34.01, -118.0)]
    assert ids(within_radius(BASE, 5, rows)) == ["a", "b", "c"]


def test_radius_is_inclusive_and_drops_rows_outside_it():
    edge = haversine_km(34.0, -118.0, 34.1, -118.0)
    rows = [row("on_edge", 34.1, -118.0), row("outside", 34.2, -118.0)]
    assert ids(within_radius(BASE, edge, rows)) == ["on_edge"]
    assert ids(within_radius(BASE, edge - 0.001, rows)) == []
    assert ids(
        within_radius(
            BASE, 0, [row("same", 34.0, -118.0), row("other", 34.001, -118.0)]
        )
    ) == ["same"]


@pytest.mark.parametrize(
    "bad",
    [
        {"property_id": "p", "lat": None, "lon": -118.0},
        {"property_id": "p", "lon": -118.0},
        {"property_id": "p", "lat": 34.0},
        {"property_id": "p", "lat": float("nan"), "lon": -118.0},
        {"property_id": "p", "lat": 34.0, "lon": float("inf")},
        {"property_id": "p", "lat": "34.0", "lon": -118.0},
        {"property_id": "p", "lat": True, "lon": -118.0},
        {"property_id": "p", "lat": 91.0, "lon": -118.0},
        {"property_id": "p", "lat": 34.0, "lon": 181.0},
    ],
)
def test_rows_with_missing_or_invalid_coordinates_are_excluded_and_counted(bad):
    result = within_radius(BASE, 50, [row("good", 34.01, -118.0), bad])
    assert ids(result) == ["good"] and result["excluded_missing_coordinates"] == 1


def test_excluded_count_is_separate_from_rows_that_are_merely_out_of_range():
    rows = [
        row("in", 34.01, -118.0),
        row("out_of_range", 40.0, -100.0),
        {"property_id": "no_coords"},
        {"property_id": "none", "lat": None, "lon": None},
    ]
    result = within_radius(BASE, 10, rows)
    assert ids(result) == ["in"] and result["excluded_missing_coordinates"] == 2


def test_empty_and_generator_inputs():
    empty = within_radius(BASE, 10, [])
    assert empty["results"] == [] and empty["excluded_missing_coordinates"] == 0
    result = within_radius(
        BASE, 10, (row(str(i), 34.0 + i / 1000, -118.0) for i in range(3))
    )
    assert ids(result) == ["0", "1", "2"]


def test_rows_are_not_mutated_and_property_ids_become_text():
    rows = [row(123, 34.01, -118.0)]
    snapshot = [dict(r) for r in rows]
    assert ids(within_radius(BASE, 10, rows)) == ["123"]
    assert rows == snapshot


@pytest.mark.parametrize(
    "base",
    [None, "34,-118", {}, {"lat": 34.0}, {"lat": None, "lon": -118.0}, {"lat": 91, "lon": 0}, {"lat": 0, "lon": 181},
     {"lat": float("nan"), "lon": 0}, {"lat": True, "lon": 0}],
)  # fmt: skip
def test_a_bad_base_is_an_error(base):
    with pytest.raises(ValueError, match="base"):
        within_radius(base, 10, [row("a", 34.0, -118.0)])


@pytest.mark.parametrize("max_km", [-1, float("nan"), float("inf"), True, "5", None])
def test_a_bad_radius_is_an_error(max_km):
    with pytest.raises(ValueError, match="max_km"):
        within_radius(BASE, max_km, [row("a", 34.0, -118.0)])


@pytest.mark.parametrize(
    "bad",
    [
        {"lat": 34.0, "lon": -118.0},
        {"property_id": "", "lat": 1, "lon": 1},
        "not a dict",
    ],
)
def test_a_row_without_a_property_id_is_an_error(bad):
    with pytest.raises(ValueError, match="property_id"):
        within_radius(BASE, 10, [bad])


def test_poles_and_dateline_inputs_are_accepted():
    result = within_radius(
        {"lat": 90, "lon": 0}, 500, [row("p", 89.0, 120.0), row("q", 0, 0)]
    )
    assert ids(result) == ["p"] and math.isclose(
        result["results"][0]["distance_km"], 111.195, abs_tol=0.01
    )


def test_module_has_no_network_or_kit_access():
    source = Path(radius.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported == {"__future__", "math"}
    assert not any(
        word in source
        for word in ("open(", "read_text", "cache/", "requests", "httpx", "socket")
    )
