"""Private ID-map validation uses temporary synthetic Parquet only."""
import pytest

from index import production_join


def parquet(tmp_path, definition, rows):
    import duckdb

    path = tmp_path / "property_models.parquet"
    with duckdb.connect(":memory:") as connection:
        connection.execute(f"CREATE TABLE fixture ({definition})")
        if rows:
            placeholders = ",".join("?" for _ in rows[0])
            connection.executemany(f"INSERT INTO fixture VALUES ({placeholders})", rows)
        connection.execute("COPY fixture TO ? (FORMAT PARQUET)", [str(path)])
    return path


def test_integer_identifiers_normalized_to_exact_strings(tmp_path):
    path = parquet(tmp_path, "property_id BIGINT, model_id BIGINT", [(101, 202), (101, 202), (102, 203)])
    assert production_join.load_property_model_pairs(path) == {("101", "202"), ("102", "203")}


def test_string_identifiers_trimmed_without_losing_leading_zeroes(tmp_path):
    path = parquet(tmp_path, "property_id VARCHAR, model_id VARCHAR", [(" 00101 ", " model-a ")])
    assert production_join.load_property_model_pairs(path) == {("00101", "model-a")}


def test_missing_corrupt_and_wrong_schema_are_unavailable(tmp_path):
    path = tmp_path / "missing.parquet"
    assert production_join.load_property_model_pairs(path) is None
    path.write_bytes(b"not a parquet file; PRIVATE_SYNTHETIC_SENTINEL")
    assert production_join.load_property_model_pairs(path) is None
    wrong_schema = parquet(tmp_path, "wrong_property_id VARCHAR, model_id VARCHAR", [("p1", "m1")])
    assert production_join.load_property_model_pairs(wrong_schema) is None


@pytest.mark.parametrize("definition,rows", [
    ("property_id VARCHAR, model_id VARCHAR", [("p1", "m1"), (None, "m2")]),
    ("property_id VARCHAR, model_id VARCHAR", [("p1", "   ")]),
    ("property_id DOUBLE, model_id VARCHAR", [(1.5, "m1")]),
    ("property_id BOOLEAN, model_id VARCHAR", [(True, "m1")]),
])
def test_invalid_identifier_invalidates_mapping_instead_of_partial_confirmation(tmp_path, definition, rows):
    path = parquet(tmp_path, definition, rows)
    assert production_join.load_property_model_pairs(path) is None


def test_empty_mapping_is_valid_but_contains_no_confirmed_pairs(tmp_path):
    path = parquet(tmp_path, "property_id VARCHAR, model_id VARCHAR", [])
    assert production_join.load_property_model_pairs(path) == set()


def test_mapping_row_limit_rejects_oversize_instead_of_using_truncated_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(production_join, "MAX_PROPERTY_MODEL_ROWS", 2)
    path = parquet(tmp_path, "property_id VARCHAR, model_id VARCHAR",
                   [("p1", "m1"), ("p2", "m2"), ("p3", "m3")])
    assert production_join.load_property_model_pairs(path) is None
