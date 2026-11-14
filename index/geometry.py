"""Conservative shot-depth feasibility; this is not a site safety certification."""
import math
from contracts.schemas import ShotFit

SENSOR_WIDTH_MM = 24.9
BEHIND_ACTORS_M = 2.0
OPERATOR_M = 1.0
MIN_RIG_CEILING_M = 2.7


def _positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def horizontal_fov_deg(focal_mm: float) -> float:
    _positive(focal_mm, "focal_mm")
    return math.degrees(2 * math.atan(SENSOR_WIDTH_MM / (2 * focal_mm)))


def camera_distance_m(focal_mm: float, frame_width_m: float) -> float:
    _positive(frame_width_m, "frame_width_m")
    half = math.radians(horizontal_fov_deg(focal_mm)) / 2
    return (frame_width_m / 2) / math.tan(half)


def needed_depth_m(focal_mm: float, frame_width_m: float) -> float:
    return camera_distance_m(focal_mm, frame_width_m) + BEHIND_ACTORS_M + OPERATOR_M


def check_fit(depth_m, ceiling_m, focal_mm=24.0, frame_width_m=6.0, measure_on_site=False) -> ShotFit:
    exact_need = needed_depth_m(focal_mm, frame_width_m)
    need = round(exact_need, 2)
    if depth_m is not None:
        _positive(depth_m, "depth_m")
    if ceiling_m is not None:
        _positive(ceiling_m, "ceiling_m")
    if depth_m is None:
        return ShotFit(fits=False, needed_depth_m=need, have_depth_m=None,
                       ceiling_m=ceiling_m, note="No depth for this view: measure on site.")
    # Compare unrounded quantities: display rounding must not create a false pass.
    fits = depth_m >= exact_need and not measure_on_site
    parts = [f"{focal_mm:g} mm lens framing {frame_width_m:g} m needs {need} m; room has {depth_m:g} m."]
    if ceiling_m is not None and ceiling_m < MIN_RIG_CEILING_M:
        parts.append(f"Ceiling {ceiling_m:g} m leaves little room to rig lights.")
    if ceiling_m is None:
        parts.append("Ceiling unknown: confirm rig clearance on site.")
    if measure_on_site:
        parts.append("Geometry estimated: fit unverified; measure on site.")
    else:
        parts.append("Depth feasibility only; verify access, obstructions and rig clearance on site.")
    return ShotFit(fits=fits, needed_depth_m=need, have_depth_m=depth_m,
                   ceiling_m=ceiling_m, note=" ".join(parts))
