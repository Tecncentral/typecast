import math
import pytest
from index.planning import plan_camera, ray_distance

ROOM = {'ring': [[0, 0], [12, 0], [12, 8], [0, 8]]}


def test_lens_geometry_and_manual_clearance_remain_unverified():
    result = plan_camera(ROOM, {'x': 2, 'y': 4}, focal_mm=24.9, frame_width_m=3)
    assert result['camera_distance_m'] == pytest.approx(3)
    assert result['forward_m'] == 10 and result['backward_m'] == 2
    assert result['estimated_clearance'] is True
    assert result['status'] == 'unknown'
    assert result['orientation'] == 'manual_floor_plan_heading'
    assert plan_camera(ROOM, {'x': 2, 'y': 4}, focal_mm=100)['estimated_clearance'] is False


def test_concave_wall_is_first_hit_not_far_wall():
    ring = [[0,0],[6,0],[6,2],[2,2],[2,6],[0,6]]
    assert ray_distance([1,3], 0, ring) == 1
    assert ray_distance([1,3], 180, ring) == pytest.approx(1)
    assert plan_camera({'ring':ring}, {'x':1,'y':3})['estimated_clearance'] is False


def test_edge_and_unknown_positions_cannot_claim_clearance():
    for position in [None, {'x':0,'y':3}, {'x':20,'y':3}, {'x':True,'y':3}]:
        result = plan_camera(ROOM, position)
        assert result['estimated_clearance'] is None and result['ring'] is None
    for focal in [True, math.nan, 0, -1]:
        with pytest.raises(ValueError):
            plan_camera(None, None, focal_mm=focal)


def test_frame_edges_can_fail_even_when_center_ray_clears():
    result = plan_camera(ROOM, {'x':2,'y':.2}, focal_mm=10, frame_width_m=4)
    assert result['forward_m'] > result['camera_distance_m']+2
    assert result['estimated_clearance'] is False
