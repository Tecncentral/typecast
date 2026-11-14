"""Does the shot fit the room? Pure maths, no data access."""
import math
from contracts.schemas import ShotFit

SENSOR_WIDTH_MM = 24.9      # Super 35
BEHIND_ACTORS_M = 2.0
OPERATOR_M = 1.0
MIN_RIG_CEILING_M = 2.7     # below this, little room to rig lights


def horizontal_fov_deg(focal_mm: float) -> float:
    return math.degrees(2 * math.atan(SENSOR_WIDTH_MM / (2 * focal_mm)))


def camera_distance_m(focal_mm: float, frame_width_m: float) -> float:
    half = math.radians(horizontal_fov_deg(focal_mm)) / 2
    return (frame_width_m / 2) / math.tan(half)


def needed_depth_m(focal_mm: float, frame_width_m: float) -> float:
    return camera_distance_m(focal_mm, frame_width_m) + BEHIND_ACTORS_M + OPERATOR_M


def check_fit(depth_m, ceiling_m, focal_mm=24.0, frame_width_m=6.0, measure_on_site=False) -> ShotFit:
    need = round(needed_depth_m(focal_mm, frame_width_m), 2)
    if depth_m is None:
        return ShotFit(fits=False, needed_depth_m=need, have_depth_m=None, ceiling_m=ceiling_m,
                       note="No depth for this view: measure on site.")
    fits = depth_m >= need
    parts = [f"{focal_mm:g} mm lens framing {frame_width_m:g} m needs {need} m; room has {depth_m:g} m."]
    if ceiling_m is not None and ceiling_m < MIN_RIG_CEILING_M:
        parts.append(f"Ceiling {ceiling_m:g} m leaves little room to rig lights.")
    if measure_on_site:
        parts.append("Geometry estimated: measure on site.")
    return ShotFit(fits=fits, needed_depth_m=need, have_depth_m=depth_m, ceiling_m=ceiling_m, note=" ".join(parts))
