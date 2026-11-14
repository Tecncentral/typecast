import numpy as np, pytest
from index.geometry import needed_depth_m, horizontal_fov_deg, check_fit
from index.cut_views import perspective_view, cut_all
from index.search import search_shots, check_shot


def test_lens_maths_matches_plan():
    assert round(horizontal_fov_deg(24)) == 55
    assert abs(needed_depth_m(24, 6) - 8.78) < 0.05      # about 9 m


def test_fit_and_missing_depth():
    assert check_fit(10, 3.0).fits and not check_fit(6, 3.0).fits
    assert "measure on site" in check_fit(None, 3.0).note.lower()
    assert "rig lights" in check_fit(10, 2.4).note


def test_view_looks_where_asked():
    H, W = 200, 400
    pano = np.zeros((H, W, 3), dtype=np.uint8)
    pano[:, :, 0] = (np.arange(W) * 255 // W)[None, :]          # red encodes longitude
    for yaw in (0, 90, -90, 135):
        v = perspective_view(pano, yaw, out_w=64, out_h=48)
        assert v.shape == (48, 64, 3)
        want = ((yaw / 360 + 0.5) * W) % W * 255 // W
        assert abs(int(v[24, 32, 0]) - int(want)) <= 2
    assert len(cut_all(pano, out_w=32, out_h=24)) == 8


def test_search_filters():
    assert search_shots(query_text="office")[0].score >= search_shots(query_text="office")[-1].score
    assert all(s.depth_m >= 9 for s in search_shots(query_text="x", min_depth_m=9))
    assert all(s.property_id == "mock-p2" for s in search_shots(query_text="x", property_ids=["mock-p2"]))
    with pytest.raises(ValueError):
        search_shots()
    assert check_shot("mock-p5-s0").needed_depth_m > 8
