import math
import pytest
from index.geometry import check_fit, needed_depth_m


def test_estimated_depth_is_never_verified_fit():
    result = check_fit(30, 3.5, measure_on_site=True)
    assert result.fits is False
    assert result.status == 'unknown'
    assert "unverified" in result.note


def test_display_rounding_does_not_create_false_pass():
    exact = needed_depth_m(24, 6)
    assert round(exact, 2) < exact
    assert check_fit(round(exact, 2), 3).fits is False
    assert check_fit(exact, 3).fits is True


@pytest.mark.parametrize("bad", [True, False, 0, -1, math.nan, math.inf])
@pytest.mark.parametrize("field", ["depth_m", "ceiling_m", "focal_mm", "frame_width_m"])
def test_reject_invalid_physical_inputs(field, bad):
    values = dict(depth_m=10, ceiling_m=3, focal_mm=24, frame_width_m=6)
    values[field] = bad
    with pytest.raises(ValueError):
        check_fit(**values)


def test_missing_geometry_preserves_uncertainty():
    assert not check_fit(None, None).fits
    assert "Ceiling unknown" in check_fit(10, None).note
