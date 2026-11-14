"""Metric floor-plan estimates with explicit manual orientation; no tour-pose claims."""
import math
from dataclasses import asdict
from index.rooms import parse_rooms_model, _point_in_ring, _segments_intersect


def room_plans(payloads):
    """Retain validated polygons only, without signed image URLs or credentials."""
    return {mid: [asdict(room) for room in parse_rooms_model(payload)[1]]
            for mid, payload in payloads.items()}


def _number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + ' must be finite')
    if positive and value <= 0:
        raise ValueError(name + ' must be positive')
    return float(value)


def ray_distance(origin, angle_deg, ring):
    """First forward boundary intersection; works for concave simple polygons."""
    d = (math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg)))
    cross = lambda a, b: a[0]*b[1]-a[1]*b[0]
    hits = []
    for a, b in zip(ring, ring[1:] + ring[:1]):
        edge = (b[0]-a[0], b[1]-a[1])
        denom = cross(d, edge)
        if abs(denom) < 1e-9:
            continue
        offset = (a[0]-origin[0], a[1]-origin[1])
        t, u = cross(offset, edge)/denom, cross(offset, d)/denom
        if t >= 0 and -1e-9 <= u <= 1+1e-9:
            hits.append(t)
    return min(hits) if hits else None


def plan_camera(room, position, *, heading_deg=0., focal_mm=24., sensor_width_mm=24.9,
                frame_width_m=3., actor_back_m=2., operator_back_m=1.):
    """A selected plan heading is independent of the panorama's cube-local heading."""
    heading = _number(heading_deg, 'heading') % 360
    focal = _number(focal_mm, 'focal', True)
    sensor = _number(sensor_width_mm, 'sensor', True)
    width = _number(frame_width_m, 'frame width', True)
    actor = _number(actor_back_m, 'actor clearance', True)
    operator = _number(operator_back_m, 'operator clearance', True)
    distance = width * focal / sensor
    fov = math.degrees(2*math.atan(sensor/(2*focal)))
    result = dict(status='unknown', orientation='manual_floor_plan_heading',
        heading_deg=heading, focal_mm=focal, sensor_width_mm=sensor,
        frame_width_m=width, horizontal_fov_deg=fov, camera_distance_m=distance,
        actor_back_m=actor, operator_back_m=operator, ring=None, position=None,
        forward_m=None, backward_m=None, estimated_clearance=None,
        note='Missing validated room boundary or scan position. Measure on site.')
    if not room or not position:
        return result
    try:
        origin = [_number(position['x'], 'x'), _number(position['y'], 'y')]
        ring = [list(p) for p in room['ring']]
        if len(ring) < 3 or any(len(p) != 2 for p in ring):
            return result
        for p in ring:
            for v in p:
                _number(v, 'boundary coordinate')
        if _point_in_ring(tuple(origin), ring) != 'inside':
            return result
    except (KeyError, TypeError, ValueError):
        return result
    forward = ray_distance(origin, heading, ring)
    backward = ray_distance(origin, heading+180, ring)
    # Test the complete subject-width segment, not just the central sightline.
    angle = math.radians(heading)
    center = [origin[0]+distance*math.cos(angle), origin[1]+distance*math.sin(angle)]
    endpoints = [[center[0]+sign*width/2*(-math.sin(angle)),
                  center[1]+sign*width/2*math.cos(angle)] for sign in (-1, 1)]
    visible = True
    for point in endpoints:
        delta = [point[0]-origin[0], point[1]-origin[1]]
        reach = ray_distance(origin, math.degrees(math.atan2(delta[1], delta[0])), ring)
        if reach is None or reach <= math.hypot(*delta):
            visible = False
    if any(_segments_intersect(endpoints[0], endpoints[1], a, b)
           for a, b in zip(ring, ring[1:] + ring[:1])):
        visible = False
    clears = (visible and forward is not None and backward is not None
              and forward >= distance+actor and backward >= operator)
    result.update(ring=ring, position=origin, forward_m=forward, backward_m=backward,
        subject_endpoints=endpoints, estimated_clearance=bool(clears),
        note=('Estimated plan clearance available.' if clears else 'Selected setup exceeds estimated plan clearance.')
             + ' Manual heading; walls, furniture, access and ceiling require site verification.')
    return result
