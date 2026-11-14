"""Crew parking and noise from explicit fixtures or precomputed private evidence.

Live requests only read cache/vexcel/<property_id>/logistics.json. Run
``TYPECAST_USE_MOCKS=0 python -m data.vexcel_precompute`` before the demo.
No missing source is replaced with fixture data or a fabricated zero.
"""
import json
import math
import os
import pathlib
import re
from contracts.schemas import Logistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
USE_MOCKS = os.getenv("TYPECAST_USE_MOCKS", "1") == "1"
M2_PER_CAR = 30.0        # stall plus aisle
CARS_PER_TRUCK = 4


class VexcelUnavailable(FileNotFoundError):
    """Private evidence is absent; the pipeline can skip this candidate."""


def spaces_from_area(area_m2: float) -> int:
    if isinstance(area_m2, bool) or not math.isfinite(area_m2) or area_m2 < 0:
        raise ValueError("Parking area must be finite and nonnegative")
    return int(area_m2 // M2_PER_CAR)


def plan_logistics(property_id: str, trucks: int = 3, cars: int = 30) -> Logistics:
    _vehicles(trucks, cars)
    if USE_MOCKS:
        for l in json.loads((ROOT / "mocks/logistics.json").read_text()):
            if l["property_id"] == property_id:
                return Logistics(**l)
        raise KeyError(property_id)
    if not isinstance(property_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", property_id):
        raise ValueError("Invalid property identifier")
    root = (ROOT / "cache/vexcel").resolve()
    directory = (root / property_id).resolve()
    if not directory.is_relative_to(root):
        raise ValueError("Vexcel cache path escapes private cache")
    target = directory / "logistics.json"
    if not target.is_file():
        raise VexcelUnavailable("Private Vexcel logistics missing; run python -m data.vexcel_precompute. Live mode does not use fixtures.")
    try:
        record = json.loads(target.read_text())
        if record.get("schema_version") != 1 or record.get("property_id") != property_id:
            raise ValueError
        logistics = Logistics(**record["logistics"])
        if logistics.property_id != property_id:
            raise ValueError
        if logistics.aerial_image_path:
            expected = f"cache/vexcel/{property_id}/aerial-logistics.png"
            if logistics.aerial_image_path != expected:
                raise ValueError
            image = (ROOT / expected).resolve()
            if not image.is_relative_to(directory):
                raise ValueError
            if not image.is_file():
                logistics = logistics.model_copy(update={"aerial_image_path": None,
                    "source_notes": [*logistics.source_notes, "Cached aerial image is missing."]})
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("Private Vexcel logistics cache is invalid; rerun python -m data.vexcel_precompute.") from None
    return allocate_parking(logistics, trucks)


def aerial_image(property_id: str) -> str | None:
    return plan_logistics(property_id).aerial_image_path


def _vehicles(trucks: int, cars: int = 0):
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (trucks, cars)):
        raise ValueError("Vehicle requirements must be nonnegative integers")


def allocate_parking(logistics: Logistics, trucks: int) -> Logistics:
    """Allocate a shared area to requested trucks and leave the rest for cars.

    Legacy fixtures have no area and preserve their supplied independent counts.
    Changing the requested crew never mutates a cached source record.
    """
    _vehicles(trucks)
    if logistics.parking_area_m2 is None or logistics.parking_status == "unknown":
        return logistics.model_copy(deep=True)
    capacity = spaces_from_area(logistics.parking_area_m2)
    allocated = min(trucks, capacity // CARS_PER_TRUCK)
    return logistics.model_copy(update={"truck_spaces": allocated,
        "car_spaces": capacity - allocated * CARS_PER_TRUCK}, deep=True)


def enough_parking(l: Logistics, trucks: int, cars: int) -> bool:
    _vehicles(trucks, cars)
    if l.parking_status == "unknown" or l.truck_spaces is None or l.car_spaces is None:
        return False
    if l.parking_area_m2 is not None:
        return trucks * CARS_PER_TRUCK + cars <= spaces_from_area(l.parking_area_m2)
    return l.truck_spaces >= trucks and l.car_spaces >= cars
