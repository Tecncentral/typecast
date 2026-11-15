"""Cost model behaviours. Pure functions; rent files are synthetic and live in a temp dir."""

import ast
import copy
import json
import math
from pathlib import Path

import pytest

from data import cost_model as cm
from data.cost_model import DEFAULT_ASSUMPTIONS as A
from data.cost_model import REIMAGINING_TABLE as T
from data.cost_model import cost_compare

PLACEHOLDER_KEYS = [
    "set_construction_per_sqft", "cgi_per_shot", "cgi_shots_per_scene",
    "scouting_trip_cost", "crew_day_rate", "crew_size",
]  # fmt: skip
SCENARIOS = ("found_location", "build_set", "standing_set", "cgi")


@pytest.fixture
def rent_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "RENT_DIR", tmp_path)
    return tmp_path


def write_rent(directory, pid, rate, tier="A", source="active lease listing"):
    record = {
        "property_id": pid, "tier": tier, "usd_per_sf_year": rate, "source": source,
        "date": "2026-08-01", "age_years": 0.3, "caveats": ["synthetic caveat"],
    }  # fmt: skip
    (directory / f"{pid}.json").write_text(json.dumps(record))


def lines(result, scenario):
    return {line["label"]: line for line in result[scenario]["lines"]}


def test_every_assumption_has_source_date_note_and_quality():
    for key, entry in A.items():
        assert all(
            entry[f] not in (None, "")
            for f in ("source", "date", "note", "quality", "unit")
        ), key
        assert entry["low"] <= entry["value"] <= entry["high"], key
    for method, entry in T.items():
        assert all(
            entry[f] not in (None, "")
            for f in ("source", "date", "note", "quality", "unit")
        ), method


def test_supplied_benchmarks_are_recorded_as_given():
    assert (A["location_day_rate"]["low"], A["location_day_rate"]["high"]) == (
        145 * 10,
        222 * 10,
    )
    assert A["location_day_rate"]["value"] == (145 + 222) / 2 * 10
    assert (A["agency_fee_rate"]["low"], A["agency_fee_rate"]["high"]) == (0.15, 0.30)
    assert (A["studio_day_rate"]["low"], A["studio_day_rate"]["high"]) == (1200, 2000)
    assert A["standing_set_day_rate"]["value"] == 1999
    assert (
        A["insurance_per_shoot_day"]["low"],
        A["insurance_per_shoot_day"]["high"],
    ) == (300, 1000)
    assert A["hours_per_day"]["value"] == 10


def test_placeholders_are_marked_needs_a_real_quote():
    for key in PLACEHOLDER_KEYS:
        assert (
            A[key]["quality"] == cm.PLACEHOLDER == "ASSUMPTION, needs a real quote"
        ), key
        assert "ASSUMPTION, needs a real quote" in A[key]["note"], key
    assert set(T) == {
        "paint",
        "flooring",
        "fixtures",
        "furniture_rental",
        "framing",
        "foam_plaster_piece",
        "printed_prop_3d",
    }
    assert all(
        entry["quality"] == cm.PLACEHOLDER and cm.PLACEHOLDER in entry["note"]
        for entry in T.values()
    )


def test_every_result_carries_the_scenario_label(rent_dir):
    result = cost_compare("p1", 1000, 2)
    assert result["label"] == "scenario estimate, not verified savings"
    assert all(result[name]["label"] == result["label"] for name in SCENARIOS)


def test_found_location_headline_is_the_benchmark_day_rate_times_days(rent_dir):
    result = cost_compare("p1", 1000, 3, scouting_trips=0)
    found = lines(result, "found_location")
    fee = found["Location fee (benchmark day rate x shoot days)"]
    assert fee["amount_usd"] == A["location_day_rate"]["value"] * 3
    assert found["Agency fee"]["amount_usd"] == pytest.approx(
        fee["amount_usd"] * A["agency_fee_rate"]["value"], abs=0.01
    )
    assert found["Insurance"]["amount_usd"] == A["insurance_per_shoot_day"]["value"] * 3
    assert "Scouting trips" not in found
    assert result["found_location"]["total_usd"] == pytest.approx(
        sum(l["amount_usd"] for l in found.values()), abs=0.01
    )


def test_rent_prorated_floor_is_a_separate_line_never_in_the_total(rent_dir):
    without = cost_compare("p1", 1000, 2)
    write_rent(rent_dir, "p1", 36.5)
    with_rent = cost_compare("p1", 1000, 2)
    floor = with_rent["found_location"]["rent_prorated_floor"]
    assert (
        floor["amount_usd"]
        == pytest.approx(1000 * 36.5 / 365 * 2, abs=0.005)
        == pytest.approx(200.0)
    )
    assert floor["included_in_total"] is False and floor["tier"] == "A"
    assert (
        floor["caveats"] == ["synthetic caveat"]
        and floor["quality"] == "kit-derived, tier A"
    )
    assert (
        with_rent["found_location"]["total_usd"]
        == without["found_location"]["total_usd"]
    )
    assert "rent_prorated_floor" not in {
        l["label"] for l in with_rent["found_location"]["lines"]
    }
    assert "rent_prorated_floor" not in with_rent["build_set"]


def test_missing_or_unpriced_rent_is_unknown_not_zero(rent_dir):
    missing = cost_compare("p1", 1000, 2)["found_location"]["rent_prorated_floor"]
    assert (
        missing["amount_usd"] is None
        and "run python -m data.rent_precompute" in missing["reason"]
    )
    write_rent(rent_dir, "p2", None, tier="C", source="no reliable price")
    unpriced = cost_compare("p2", 1000, 2)["found_location"]["rent_prorated_floor"]
    assert (
        unpriced["amount_usd"] is None
        and unpriced["tier"] == "C"
        and "no reliable price" in unpriced["reason"]
    )


def test_corrupt_rent_cache_is_an_explicit_error(rent_dir):
    (rent_dir / "p1.json").write_text("{not json")
    with pytest.raises(RuntimeError, match="rent cache is invalid"):
        cost_compare("p1", 1000, 2)
    (rent_dir / "p1.json").write_text(
        json.dumps({"property_id": "other", "tier": "A", "usd_per_sf_year": 1})
    )
    with pytest.raises(RuntimeError):
        cost_compare("p1", 1000, 2)


def test_other_scenarios_use_the_supplied_prices(rent_dir):
    result = cost_compare("p1", 1000, 4)
    insurance = A["insurance_per_shoot_day"]["value"] * 4
    standing = result["standing_set"]
    assert standing["total_usd"] == 1999 * 4 + insurance
    build = result["build_set"]
    assert (
        build["total_usd"]
        == A["studio_day_rate"]["value"] * 4
        + A["set_construction_per_sqft"]["value"] * 1000
        + insurance
    )
    cgi = result["cgi"]
    expected = (
        A["studio_day_rate"]["value"] * 4
        + A["cgi_per_shot"]["value"] * A["cgi_shots_per_scene"]["value"]
        + insurance
    )
    assert cgi["total_usd"] == expected


def test_scene_size_moves_the_build_set_only(rent_dir):
    small, large = cost_compare("p1", 500, 2), cost_compare("p1", 5000, 2)
    assert large["build_set"]["total_usd"] > small["build_set"]["total_usd"]
    for name in ("found_location", "standing_set", "cgi"):
        assert large[name]["total_usd"] == small[name]["total_usd"]


def test_change_list_is_priced_from_the_lookup_table(rent_dir):
    changes = [{"method": m, "quantity": 10} for m in T]
    found = lines(cost_compare("p1", 1000, 3, change_list=changes), "found_location")
    for method, entry in T.items():
        line = found[f"Change: {method.replace('_', ' ')}"]
        days = 3 if entry["per_shoot_day"] else 1
        assert line["amount_usd"] == pytest.approx(10 * entry["unit_cost"] * days), (
            method
        )
        assert line["inputs"][0] == f"reimagining.{method}"


def test_change_list_labels_and_defaults(rent_dir):
    base = cost_compare("p1", 1000, 1)["found_location"]["total_usd"]
    labelled = cost_compare(
        "p1",
        1000,
        1,
        change_list=[{"method": "paint", "quantity": 100, "label": "lobby walls"}],
    )
    assert "Change: lobby walls" in lines(labelled, "found_location")
    assert labelled["found_location"]["total_usd"] == pytest.approx(
        base + 100 * T["paint"]["unit_cost"], abs=0.01
    )
    assert (
        cost_compare("p1", 1000, 1, change_list=[])["found_location"]["total_usd"]
        == base
    )
    for other in ("build_set", "standing_set", "cgi"):
        assert (
            labelled[other]["total_usd"]
            == cost_compare("p1", 1000, 1)[other]["total_usd"]
        )


@pytest.mark.parametrize(
    "bad",
    [
        [{"method": "gold_plating", "quantity": 1}],
        [{"method": "paint", "quantity": -1}],
        [{"method": "paint"}],
        [{"method": "paint", "quantity": float("nan")}],
        ["paint"],
    ],
)
def test_bad_change_lists_are_rejected(rent_dir, bad):
    with pytest.raises(ValueError):
        cost_compare("p1", 1000, 1, change_list=bad)


def test_overrides_replace_values_and_are_tagged(rent_dir):
    before = copy.deepcopy(A)
    result = cost_compare(
        "p1", 1000, 2, scouting_trips=0,
        assumptions={"location_day_rate": 1000, "reimagining": {"paint": 4.0}},
        change_list=[{"method": "paint", "quantity": 50}],
    )  # fmt: skip
    found = lines(result, "found_location")
    assert found["Location fee (benchmark day rate x shoot days)"]["amount_usd"] == 2000
    assert found["Change: paint"]["amount_usd"] == 200.0
    used = result["found_location"]["inputs_used"]
    assert (
        used["location_day_rate"]["quality"]
        == used["reimagining.paint"]["quality"]
        == cm.OVERRIDE
    )
    assert (used["location_day_rate"]["low"], used["location_day_rate"]["high"]) == (
        1000,
        1000,
    )
    assert A == before and T["paint"]["unit_cost"] == 2.5, "defaults are never mutated"


@pytest.mark.parametrize(
    "overrides",
    [
        {"location_dayrate": 1},
        {"location_day_rate": -5},
        {"location_day_rate": "cheap"},
        {"reimagining": {"gilding": 1}},
    ],
)
def test_unknown_or_invalid_overrides_are_rejected(rent_dir, overrides):
    with pytest.raises(ValueError):
        cost_compare("p1", 1000, 1, assumptions=overrides)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"property_id": "../etc"}, {"property_id": ""}, {"property_id": 12},
        {"scene_sqft": 0}, {"scene_sqft": -1}, {"scene_sqft": math.inf}, {"scene_sqft": True},
        {"shoot_days": 0}, {"shoot_days": 1.5}, {"shoot_days": True},
        {"scouting_trips": -1}, {"crew": -2}, {"drive_minutes": -5}, {"drive_minutes": math.nan},
    ],
)  # fmt: skip
def test_bad_inputs_are_rejected(rent_dir, kwargs):
    arguments = {"property_id": "p1", "scene_sqft": 1000, "shoot_days": 1, **kwargs}
    with pytest.raises(ValueError):
        cost_compare(**arguments)


def test_travel_time_needs_drive_minutes_and_uses_the_crew_rate(rent_dir):
    without = cost_compare("p1", 1000, 2)
    assert not any("travel" in label for label in lines(without, "found_location"))
    with_drive = cost_compare("p1", 1000, 2, crew=4, drive_minutes=30)
    travel = next(
        l for l in with_drive["found_location"]["lines"] if "travel" in l["label"]
    )
    hourly = A["crew_day_rate"]["value"] / A["hours_per_day"]["value"]
    assert travel["amount_usd"] == pytest.approx(4 * 1.0 * hourly * 2, abs=0.01)
    assert with_drive["inputs"]["crew"]["quality"] == cm.USER_INPUT
    assert without["inputs"]["crew"]["quality"] == cm.PLACEHOLDER, (
        "the default crew size is a placeholder"
    )


def test_scouting_trips_scale_linearly(rent_dir):
    one, three = (
        cost_compare("p1", 1000, 1, scouting_trips=1),
        cost_compare("p1", 1000, 1, scouting_trips=3),
    )
    assert (
        lines(three, "found_location")["Scouting trips"]["amount_usd"]
        == 3 * A["scouting_trip_cost"]["value"]
    )
    assert (
        lines(one, "found_location")["Scouting trips"]["amount_usd"]
        == A["scouting_trip_cost"]["value"]
    )


def test_ranges_bracket_the_total_and_lines_sum_to_it(rent_dir):
    result = cost_compare(
        "p1",
        1000,
        2,
        change_list=[{"method": "flooring", "quantity": 300}],
        drive_minutes=20,
    )
    for name in SCENARIOS:
        scenario = result[name]
        assert (
            scenario["total_low_usd"]
            <= scenario["total_usd"]
            <= scenario["total_high_usd"]
        ), name
        assert scenario["total_usd"] == pytest.approx(
            sum(l["amount_usd"] for l in scenario["lines"]), abs=0.01
        ), name
        assert all(
            l["low_usd"] <= l["amount_usd"] <= l["high_usd"] for l in scenario["lines"]
        ), name
    standing = result["standing_set"]
    assert standing["lines"][0]["low_usd"] == standing["lines"][0]["high_usd"], (
        "a 'from' price has no upper bound to invent"
    )


def test_every_referenced_input_is_listed_with_a_quality_tag(rent_dir):
    result = cost_compare(
        "p1", 1000, 2, change_list=[{"method": "furniture_rental", "quantity": 2}], drive_minutes=15,
    )  # fmt: skip
    for name in SCENARIOS:
        scenario = result[name]
        referenced = {key for line in scenario["lines"] for key in line["inputs"]}
        assert referenced == set(scenario["inputs_used"]), name
        assert all(entry["quality"] for entry in scenario["inputs_used"].values()), name
    used = result["found_location"]["inputs_used"]
    assert used["shoot_days"]["quality"] == cm.USER_INPUT
    assert used["location_day_rate"]["quality"] == cm.BENCHMARK
    assert used["scouting_trip_cost"]["quality"] == cm.PLACEHOLDER
    assert used["location_day_rate"]["source"] and used["location_day_rate"]["date"]


def test_module_is_pure_no_network_and_no_kit_access():
    source = Path(cm.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert not imported & {
        "requests",
        "urllib",
        "http",
        "socket",
        "duckdb",
        "pyarrow",
        "data",
    }
    assert "costar-hackathon-kit" not in source and "join.parquet" not in source
