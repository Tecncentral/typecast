"""Conservative geometry helpers for private aerial/OSM evidence.

GeoJSON and Shapely use lon/lat. Only the shared Logistics polygon uses lat/lon.
Areas and short distances use a property-centred equirectangular projection;
this is an estimate, suitable for the <=3 km searches here, not a survey.
"""
from __future__ import annotations

import heapq
import math
import base64
import io

import numpy as np
from PIL import Image

from shapely import from_wkt, transform
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point, Polygon, box, shape
from shapely.ops import polygonize, unary_union

EARTH_M = 6_371_008.8


def project(geometry, lat: float, lon: float):
    scale = math.cos(math.radians(lat))
    return transform(geometry, lambda x, y: (
        (x - lon) * math.pi / 180 * EARTH_M * scale,
        (y - lat) * math.pi / 180 * EARTH_M), interleaved=False)


def valid_geometry(value):
    try:
        g = from_wkt(value) if isinstance(value, str) else shape(value)
        return g if not g.is_empty and g.is_valid else None
    except (ValueError, TypeError, KeyError, GEOSException):
        return None


def segmented_parking(data: dict, lat: float, lon: float):
    """Trace actual binary mask cells, never return their geographic bbox.

    Vexcel returns a cropped PNG mask and its geographic/pixel bounding boxes.
    A <=2 pixel crop rounding discrepancy was observed live; the mask is scaled
    to its source bounding box and the result remains explicitly estimated.
    Reject unexpected mask layouts instead of guessing georeferencing.
    """
    geometries = []
    images = {image.get("image-id"): image for image in data.get("images", [])}
    for feature in data.get("features", []):
        if feature.get("properties", {}).get("label") != "parking lot":
            continue
        for detection in feature.get("properties", {}).get("detections", []):
            try:
                if float(detection.get("confidence", 0)) < .5:
                    continue
                image = images[detection["imageId"]]
                if str(image.get("metadata", {}).get("srid")) != "4326":
                    continue
                bounds = valid_geometry(detection.get("bbox"))
                if bounds is None or bounds.geom_type != "Polygon" or bounds.area <= 0:
                    continue
                west, south, east, north = bounds.bounds
                if not (-180 <= west < east <= 180 and -85 <= south < north <= 85):
                    continue
                encoded = detection["pixel-mask"]
                if not isinstance(encoded, str) or len(encoded) > 8 * 1024 * 1024:
                    continue
                mask_bytes = base64.b64decode(encoded, validate=True)
                with Image.open(io.BytesIO(mask_bytes)) as mask:
                    if mask.width * mask.height > 4_194_304 or mask.format != "PNG":
                        continue
                    bbox = detection.get("pixel-bbox", [])
                    if len(bbox) != 4 or any(abs(mask.size[i] - bbox[i+2]) > 2 for i in (0, 1)):
                        continue
                    pixels = np.asarray(mask.convert("L"))
                    binary = pixels > (0 if pixels.max(initial=0) <= 1 else 128)
                height, width = binary.shape
                runs = []
                for y, row in enumerate(binary):
                    changes = np.diff(np.r_[False, row, False].astype(np.int8))
                    for start, stop in zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)):
                        runs.append(box(west + start / width * (east-west), north - (y+1) / height * (north-south),
                                        west + stop / width * (east-west), north - y / height * (north-south)))
                    if len(runs) > 100_000:
                        raise ValueError("Complex segmentation exceeds bounded tracing limit")
                if runs:
                    geometry = unary_union(runs)
                    if geometry.is_valid:
                        geometries.append(geometry)
            except (ValueError, TypeError, KeyError, OSError, GEOSException):
                continue
    if not geometries:
        return None
    # Union before area calculation prevents duplicate detections from counting
    # the same asphalt twice. Select one nearby connected lot conservatively.
    combined = unary_union(geometries).simplify(0, preserve_topology=True)
    parts = [combined] if combined.geom_type == "Polygon" else list(combined.geoms)
    candidates = [(project(p, lat, lon).distance(Point(0, 0)), -project(p, lat, lon).area, p)
                  for p in parts if p.geom_type == "Polygon"]
    candidates = [item for item in candidates if item[0] <= 150 and 0 < -item[1] <= 1_000_000]
    return min(candidates, key=lambda x: x[:2])[2] if candidates else None


def osm_geometry(element):
    """Read actual source rings; do not invent polygons from bounding boxes."""
    if element.get("type") == "node":
        try:
            return Point(float(element["lon"]), float(element["lat"]))
        except (KeyError, TypeError, ValueError):
            return None
    if element.get("type") == "relation":
        roles = {"outer": [], "inner": []}
        for member in element.get("members", []):
            points = [(p["lon"], p["lat"]) for p in member.get("geometry", []) if p]
            if len(points) >= 2 and member.get("role", "outer") in roles:
                roles[member.get("role", "outer")].append(LineString(points))
        outer = list(polygonize(unary_union(roles["outer"])))
        if not outer:
            return None
        geometry = unary_union(outer)
        inner = list(polygonize(unary_union(roles["inner"])))
        if inner:
            geometry = geometry.difference(unary_union(inner))
    else:
        points = [(p["lon"], p["lat"]) for p in element.get("geometry", []) if p]
        if len(points) < 2:
            return None
        geometry = Polygon(points) if len(points) >= 4 and points[0] == points[-1] else LineString(points)
    return geometry if geometry.is_valid and not geometry.is_empty else None


def parcel_and_footprint(data: dict, lat: float, lon: float):
    """A nearest parcel is not a property match: require actual containment."""
    point = Point(lon, lat)
    matches = []
    for feature in data.get("features", []):
        geometry = valid_geometry(feature.get("geometry"))
        if geometry is not None and geometry.geom_type in {"Polygon", "MultiPolygon"} and geometry.covers(point):
            matches.append((feature, geometry))
    if len(matches) != 1:
        return None, None, None
    feature, parcel = matches[0]
    properties = feature.get("properties", {})
    footprints = []
    for structure in properties.get("structures") or []:
        geometry = valid_geometry(structure.get("footprint.wkt"))
        if geometry is not None and geometry.geom_type in {"Polygon", "MultiPolygon"} and geometry.covers(point):
            footprints.append(geometry)
    return parcel, footprints[0] if len(footprints) == 1 else None, properties


def parking_candidate(osm: dict, lat: float, lon: float):
    """Select one actual nearby surface-parking polygon; no double counting."""
    candidates = []
    for element in osm.get("elements", []):
        tags = element.get("tags", {})
        if tags.get("amenity") != "parking" or tags.get("parking") in {"underground", "multi-storey", "rooftop", "garage_boxes"}:
            continue
        geometry = osm_geometry(element)
        if geometry is None or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            continue
        polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
        for polygon in polygons:
            # The shared contract cannot represent holes: keep full geometry in
            # private provenance, but never return an outline that fills holes.
            projected = project(polygon, lat, lon)
            distance = projected.distance(Point(0, 0))
            if distance <= 150 and projected.area > 0:
                candidates.append((distance, -projected.area, str(element.get("id", "")), polygon, element))
    if not candidates:
        return None, None
    _, _, _, polygon, element = min(candidates, key=lambda x: x[:3])
    return polygon, element


def mapped_walk(osm: dict, parking, footprint, lat: float, lon: float):
    """Shortest mapped pedestrian path from inside the lot to a known entrance.

    Unmapped links are never invented. The route is an estimate: OSM cannot
    establish present-day access, permission or obstruction-free passage.
    """
    if parking is None or footprint is None:
        return None
    graph, points = {}, {}
    for element in osm.get("elements", []):
        tags = element.get("tags", {})
        if tags.get("highway") not in {"footway", "pedestrian", "path", "steps", "living_street"}:
            continue
        if tags.get("access") in {"no", "private"} or tags.get("foot") in {"no", "private"}:
            continue
        nodes, coordinates = element.get("nodes", []), element.get("geometry", [])
        if len(nodes) != len(coordinates):
            continue
        for node, coordinate in zip(nodes, coordinates):
            if coordinate:
                points[node] = Point(coordinate["lon"], coordinate["lat"])
        for a, b in zip(nodes, nodes[1:]):
            if a in points and b in points:
                distance = project(points[a], lat, lon).distance(project(points[b], lat, lon))
                graph.setdefault(a, []).append((b, distance))
                graph.setdefault(b, []).append((a, distance))
    destination_ids = set()
    projected_footprint = project(footprint, lat, lon)
    for element in osm.get("elements", []):
        tags = element.get("tags", {})
        if element.get("type") != "node" or tags.get("entrance") in {None, "no", "exit", "emergency"}:
            continue
        if tags.get("access") in {"no", "private"} or tags.get("foot") in {"no", "private"}:
            continue
        entrance = osm_geometry(element)
        if entrance is not None and projected_footprint.distance(project(entrance, lat, lon)) <= 2:
            if element.get("id") in graph:
                destination_ids.add(element["id"])
    starts = [node for node in graph if parking.covers(points[node])]
    if not starts or not destination_ids:
        return None
    distances = {node: 0.0 for node in starts}
    queue = [(0.0, node) for node in starts]
    heapq.heapify(queue)
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances.get(node):
            continue
        if node in destination_ids:
            return round(distance, 1)
        for neighbor, weight in graph.get(node, []):
            candidate = distance + weight
            if candidate < distances.get(neighbor, math.inf):
                distances[neighbor] = candidate
                heapq.heappush(queue, (candidate, neighbor))
    return None


def noise_flags(osm: dict, lat: float, lon: float) -> list[str]:
    nearest = {}
    for element in osm.get("elements", []):
        tags = element.get("tags", {})
        if tags.get("highway") in {"motorway", "motorway_link"}:
            category, threshold = "Freeway", 200
        elif tags.get("railway") in {"rail", "light_rail", "narrow_gauge", "tram"} and tags.get("tunnel") != "yes":
            category, threshold = "Rail", 300
        elif tags.get("aeroway") in {"aerodrome", "runway"}:
            category, threshold = "Airport/runway", 3000
        else:
            continue
        geometry = osm_geometry(element)
        if geometry is None:
            continue
        distance = project(geometry, lat, lon).distance(Point(0, 0))
        if distance <= threshold:
            nearest[category] = min(nearest.get(category, math.inf), distance)
    return [f"OSM: {category} about {distance:.0f} m from property coordinate; potential noise, not a sound measurement"
            for category, distance in sorted(nearest.items())]
