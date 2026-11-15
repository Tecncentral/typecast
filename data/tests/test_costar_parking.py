import json

from data import costar_parking

TYPES = {"0": "Unknown", "1": "Surface", "2": "SurfaceTandem", "3": "Covered", "8": "Reserved"}


def test_recorded_spaces_sum_known_types_and_skip_fees_and_unknowns():
    record = {"parking": [{"parkingType": 1, "totalSpaces": 73}, {"parkingType": 2, "totalSpaces": 4},
                          {"parkingType": 3, "totalSpaces": 129}, {"parkingType": 1, "totalSpaces": 7},
                          {"parkingType": 8, "monthlyParkingFee": 25.0}, {"parkingType": 0, "totalSpaces": 9},
                          {"parkingType": 3, "totalSpaces": True}, {"parkingType": 3, "totalSpaces": -1}]}
    assert costar_parking.recorded_spaces(record, TYPES) == {"Surface": 80, "Surface tandem": 4, "Covered": 129}
    assert costar_parking.recorded_spaces({}, TYPES) == {}


def test_reader_is_optional_and_rejects_malformed_entries(tmp_path):
    costar_parking.recorded_parking.cache_clear()
    assert costar_parking.recorded_parking(tmp_path / "missing.json") == {}
    path = tmp_path / "parking.json"
    path.write_text(json.dumps({"240122": {"Surface": 73, "Covered": "x"}, "../x": {"Surface": 1}, "9": []}))
    assert costar_parking.recorded_parking(path) == {"240122": {"Surface": 73}}
    path.write_text("not json")
    costar_parking.recorded_parking.cache_clear()
    assert costar_parking.recorded_parking(path) == {}
    costar_parking.recorded_parking.cache_clear()
