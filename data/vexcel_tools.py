"""Owner 2. Crew parking and noise from aerial imagery. Mock data until Vexcel is wired in."""
import json, os, pathlib
from contracts.schemas import Logistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
USE_MOCKS = os.getenv("TYPECAST_USE_MOCKS", "1") == "1"
M2_PER_CAR = 30.0        # stall plus aisle
CARS_PER_TRUCK = 4


def spaces_from_area(area_m2: float) -> int:
    return int(area_m2 // M2_PER_CAR)


def plan_logistics(property_id: str, trucks: int = 3, cars: int = 30) -> Logistics:
    if USE_MOCKS:
        for l in json.loads((ROOT / "mocks/logistics.json").read_text()):
            if l["property_id"] == property_id:
                return Logistics(**l)
        raise KeyError(property_id)
    raise NotImplementedError("Owner 2: call Vexcel here and cache the result")


def enough_parking(l: Logistics, trucks: int, cars: int) -> bool:
    return l.truck_spaces >= trucks and l.car_spaces >= cars
