"""Precompute private aerial/logistics evidence; runtime never calls providers.

Run TYPECAST_USE_MOCKS=0 python -m data.vexcel_precompute after building the
CoStar join and Matterport shot index. Stdout contains aggregate counts only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import time

from PIL import Image, ImageDraw
from shapely.geometry import Point, mapping

from contracts.schemas import Evidence, Logistics, Property
from data.vexcel_client import VexcelClient, ProviderError, atomic_json, atomic_bytes
from data.vexcel_geometry import (mapped_walk, noise_flags, osm_geometry,
                                 parcel_and_footprint, parking_candidate, project, segmented_parking)

ROOT = Path(__file__).resolve().parents[1]
CACHE_VERSION = 1


def property_directory(property_id: str, cache_root: Path | None = None) -> Path:
    if not isinstance(property_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", property_id):
        raise ValueError("Invalid property identifier")
    root = (cache_root or ROOT / "cache").resolve()
    output = (root / "vexcel" / property_id).resolve()
    if not output.is_relative_to(root / "vexcel"):
        raise ValueError("Vexcel cache path escapes private cache")
    return output


def indexed_property_ids(index_path: Path) -> list[str]:
    index_path = index_path.resolve()
    current = index_path / "CURRENT"
    if current.is_file():
        generation = current.read_text().strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]+", generation):
            raise ValueError("Invalid index generation")
        source = (index_path / generation / "shots.json").resolve()
        if not source.is_relative_to(index_path):
            raise ValueError("Index generation escapes private cache")
    else:
        source = index_path / "shots.json"
    if not source.is_file():
        raise RuntimeError("Private shot index missing; bootstrap interiors first")
    rows = json.loads(source.read_text())
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Private shot index contains no shots")
    ids = sorted({row["property_id"] for row in rows})
    for property_id in ids:
        property_directory(property_id)
    return ids


def draw_parking(source: Path, target: Path, geometry, extent: list[float]):
    """Render source geometry on the georeferenced extract, including holes."""
    west, south, east, north = extent
    radius = 6_378_137.0
    with Image.open(source) as image:
        output = image.convert("RGBA")
        overlay = Image.new("RGBA", output.size)
        draw = ImageDraw.Draw(overlay)

        def pixel(coordinate):
            lon, lat = coordinate[:2]
            x = radius * math.radians(lon)
            y = radius * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
            return ((x-west)/(east-west)*image.width, (north-y)/(north-south)*image.height)

        if geometry is not None:
            draw.polygon([pixel(p) for p in geometry.exterior.coords], fill=(255, 191, 64, 55), outline=(255, 191, 64, 255), width=4)
            for hole in geometry.interiors:
                draw.polygon([pixel(p) for p in hole.coords], fill=(0, 0, 0, 0), outline=(255, 191, 64, 255), width=3)
        output = Image.alpha_composite(output, overlay)
        # Keep provider attribution visible. Caption is a source interpretation,
        # not an assertion of ownership, availability, access or truck clearance.
        draw = ImageDraw.Draw(output)
        caption = "Source parking boundary; capacity estimated; access unverified" if geometry is not None else "Parking outline unavailable; capacity unknown"
        draw.rectangle((0, 0, image.width, 27), fill=(10, 10, 10, 225))
        draw.text((10, 8), caption, fill="white")
        import io
        stream = io.BytesIO()
        output.convert("RGB").save(stream, format="PNG")
        atomic_bytes(target, stream.getvalue())


def derive_logistics(property: Property, source: dict, aerial_path: str | None):
    lat, lon = property.lat, property.lon
    osm = source.get("osm")
    vexcel_property = source.get("property", {})
    parcel, footprint, attributes = parcel_and_footprint(vexcel_property, lat, lon)
    notes = ["Parking is a nearby candidate area; permission, current availability and truck clearance require confirmation.",
             "Area uses a local metric projection; capacities use floor(area / 30 m²), with one truck consuming four car equivalents."]
    evidence = []
    for name, value in sorted(property.parking_flags.items()):
        evidence.append(Evidence(source="costar", status="measured", claim=f"CoStar parking flag {name}={str(value).lower()} (recorded provider attribute)."))
    parking = segmented_parking(source.get("detection", {}), lat, lon)
    parking_source = "Vexcel SAM3 segmented"
    parking_element = None
    if parking is None:
        parking, parking_element = parking_candidate(osm or {}, lat, lon)
        parking_source = "OSM mapped"
    # A mapped building containing the exact property coordinate is usable;
    # nearest-building association is never silently promoted to identity.
    if footprint is None and osm:
        containing = []
        for element in osm.get("elements", []):
            if not element.get("tags", {}).get("building"):
                continue
            geometry = osm_geometry(element)
            if geometry is not None and geometry.geom_type in {"Polygon", "MultiPolygon"} and geometry.covers(Point(lon, lat)):
                containing.append(geometry)
        if len(containing) == 1:
            footprint = containing[0]
    area, polygon, capacity = None, [], None
    if parking is not None:
        area = math.floor(project(parking, lat, lon).area * 10) / 10
        capacity = int(area // 30)
        if not parking.interiors:
            polygon = [[lat, lon] for lon, lat in parking.exterior.coords]
        else:
            notes.append("Parking has interior holes; full source geometry and image preserve them. The single-ring response outline is omitted.")
        if parking_element:
            access = parking_element.get("tags", {}).get("access", "unspecified")
            notes.append(f"OSM surface-parking polygon; mapped access={access}; may be a different parcel from the building.")
        else:
            notes.append("Vexcel SAM3 parking segmentation: traced actual mask pixels, unioned overlapping detections and selected the nearest connected lot within 150 m. Up to two pixels of crop rounding are rescaled to the source bbox.")
        evidence.append(Evidence(source="vexcel", status="estimated", claim=f"{parking_source} nearby surface-parking area about {area:g} m², overlaid on the Vexcel aerial; about {capacity} car equivalents before truck allocation. Access is unverified."))
    else:
        evidence.append(Evidence(source="vexcel", status="unknown", claim="No usable mapped parking polygon; parking capacity and outline remain unknown."))
    if attributes:
        hardscapes = attributes.get("hardscapes.area")
        if isinstance(hardscapes, (float, int)) and not isinstance(hardscapes, bool) and math.isfinite(hardscapes) and hardscapes >= 0:
            evidence.append(Evidence(source="vexcel", status="estimated", claim=f"Vexcel detected {hardscapes:g} m² of parcel hardscape. Hardscape can include non-parking surfaces, so this is not parking capacity."))
        notes.append("Vexcel parcel containment was checked; parcel and building geometry stay in private provenance.")
        capture = attributes.get("metadata.ortho-date-estimate")
        if capture:
            notes.append(f"Vexcel property source imagery estimate-date: {capture}.")
    else:
        notes.append("Vexcel property response did not uniquely contain the CoStar coordinate; nearest parcels were not joined.")
    semantic = source.get("search")
    if semantic is not None:
        notes.append(f"Vexcel semantic search returned {len(semantic.get('features', []))} candidate imagery tiles; tile footprints are not parking boundaries.")
    walk = mapped_walk(osm or {}, parking, footprint, lat, lon)
    if walk is None:
        notes.append("Walking distance unknown: no connected mapped pedestrian route from the candidate lot to a building-associated entrance.")
    else:
        notes.append("Walking distance estimates the shortest mapped pedestrian route from inside the lot to a source entrance; present-day passage remains unverified.")
    flags = noise_flags(osm, lat, lon) if osm else []
    evidence.append(Evidence(source="vexcel", status="estimated" if osm is not None else "unknown",
        claim=("OSM proximity screen: freeways within 200 m, rail within 300 m, airports/runways within 3 km of property coordinate. "
               + ("; ".join(flags) if flags else "No mapped sources found within those thresholds. This does not establish quiet conditions."))
              if osm is not None else "OSM noise-source lookup unavailable; noise is unknown."))
    for name, failure in source.get("failures", {}).items():
        notes.append(f"{name} unavailable: {failure}")
    logistics = Logistics(property_id=property.property_id, car_spaces=capacity,
        truck_spaces=0 if capacity is not None else None, parking_area_m2=area,
        parking_polygon=polygon, parking_geometry=mapping(parking) if parking is not None else None,
        parking_status="estimated" if capacity is not None else "unknown",
        walk_m=walk, walk_status="estimated" if walk is not None else "unknown", noise_flags=flags,
        noise_status="estimated" if osm is not None else "unknown", aerial_image_path=aerial_path,
        estimated=True, source_notes=notes, source_evidence=evidence)
    geometry = {"parking": mapping(parking) if parking is not None else None,
                "footprint": mapping(footprint) if footprint is not None else None,
                "parcel": mapping(parcel) if parcel is not None else None}
    return logistics, geometry, parking


def precompute_property(property: Property, client: VexcelClient | None, *, cache_root: Path | None = None,
                        refresh: bool = False, offline: bool = False, skip_osm_reason: str | None = None):
    root = (cache_root or ROOT / "cache").resolve()
    directory = property_directory(property.property_id, root)
    directory.mkdir(parents=True, exist_ok=True)
    binding = directory / "source-coordinates.json"
    coordinates = [property.lat, property.lon]
    if binding.is_file() and json.loads(binding.read_text()) != coordinates and not refresh:
        raise RuntimeError("Property coordinates changed; explicit --refresh required for source caches")
    atomic_json(binding, coordinates)
    sources = {"failures": {}}
    for name, filename, method in (("property", "property.json", "property"),
                                   ("search", "search.json", "semantic_search"),
                                   ("detection", "detection.json", "parking_detection"),
                                   ("osm", "osm.json", "osm")):
        target = directory / filename
        if target.is_file() and not refresh:
            try:
                value = json.loads(target.read_text())
                required = "elements" if name == "osm" else "features"
                if not isinstance(value.get(required), list) or (name == "osm" and value.get("remark")):
                    raise ValueError
                sources[name] = value
                continue
            except (ValueError, AttributeError):
                sources["failures"][name] = "Cached source is invalid"
        if name == "osm" and skip_osm_reason:
            sources["failures"][name] = skip_osm_reason
            continue
        if offline:
            sources["failures"][name] = "Source cache missing; offline mode"
            continue
        try:
            value = getattr(client, method)(property.lat, property.lon)
            atomic_json(target, value)
            sources[name] = value
            sources["failures"].pop(name, None)
        except ProviderError as error:
            sources["failures"][name] = str(error)
    aerial, extent_path = directory / "aerial.png", directory / "aerial-extent.json"
    image_ok, extent = False, None
    if aerial.is_file() and extent_path.is_file() and not refresh:
        try:
            extent = json.loads(extent_path.read_text())
            if len(extent) != 4 or not all(math.isfinite(v) for v in extent) or extent[0] >= extent[2] or extent[1] >= extent[3]:
                raise ValueError
            with Image.open(aerial) as image:
                image.verify()
            image_ok = True
        except (OSError, ValueError, TypeError):
            pass
    if not image_ok and not offline:
        try:
            content, extent = client.aerial(property.lat, property.lon)
            atomic_bytes(aerial, content)
            atomic_json(extent_path, extent)
            image_ok = True
        except ProviderError as error:
            sources["failures"]["aerial"] = str(error)
    if not image_ok:
        sources["failures"].setdefault("aerial", "Image or georeferencing unavailable")
    relative_image = None
    if image_ok:
        relative_image = f"cache/vexcel/{property.property_id}/aerial-logistics.png"
    logistics, geometry, parking = derive_logistics(property, sources, relative_image)
    if image_ok:
        draw_parking(aerial, directory / "aerial-logistics.png", parking, extent)
    record = {"schema_version": CACHE_VERSION, "property_id": property.property_id,
              "coordinates": [property.lat, property.lon], "prepared_at": datetime.now(timezone.utc).isoformat(),
              "logistics": logistics.model_dump(mode="json"), "geometry": geometry,
              "sources": {name: name in sources for name in ("property", "search", "detection", "osm")},
              "failures": sources["failures"]}
    atomic_json(directory / "logistics.json", record)
    return record


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=ROOT / "cache/shot-index")
    parser.add_argument("--property-id", action="append", help="Explicit private property id; default is every indexed property")
    parser.add_argument("--refresh", action="store_true", help="Explicitly refresh successful provider caches")
    parser.add_argument("--offline", action="store_true", help="Re-derive using existing private source caches only")
    parser.add_argument("--without-osm", action="store_true", help="Record OSM unavailable without retrying a known service outage")
    args = parser.parse_args(argv)
    if os.getenv("TYPECAST_USE_MOCKS", "1") != "0":
        parser.error("Set TYPECAST_USE_MOCKS=0 explicitly; live precompute never uses fixture properties")
    from data.costar_tools import get_property
    ids = sorted(set(args.property_id or indexed_property_ids(args.index)))
    client = None if args.offline else VexcelClient()
    summary = {"indexed_properties": len(ids), "cached": 0, "aerials": 0, "parking_estimated": 0,
               "walk_estimated": 0, "noise_screened": 0, "provider_failures": 0, "property_missing": 0,
               "property_attributes": 0, "semantic_searches": 0, "segmentations": 0}
    skip_osm_reason = "OSM service unavailable; explicitly skipped for this batch" if args.without_osm else None
    for property_id in ids:
        try:
            property = get_property(property_id)
        except KeyError:
            summary["property_missing"] += 1
            continue
        record = precompute_property(property, client, refresh=args.refresh, offline=args.offline,
                                     skip_osm_reason=skip_osm_reason)
        if "osm" in record["failures"]:
            skip_osm_reason = "OSM unavailable earlier in this batch; further requests suppressed"
        logistics = record["logistics"]
        summary["cached"] += 1
        summary["aerials"] += bool(logistics["aerial_image_path"])
        summary["parking_estimated"] += logistics["parking_status"] == "estimated"
        summary["walk_estimated"] += logistics["walk_status"] == "estimated"
        summary["noise_screened"] += logistics["noise_status"] == "estimated"
        summary["provider_failures"] += len(record["failures"])
        summary["property_attributes"] += record["sources"]["property"]
        summary["semantic_searches"] += record["sources"]["search"]
        summary["segmentations"] += record["sources"]["detection"]
        # Sequential bounded source access; no live provider calls occur in API requests.
        if not args.offline:
            time.sleep(1)
    atomic_json(ROOT / "cache/vexcel/coverage.json", {"prepared_at": datetime.now(timezone.utc).isoformat(), **summary})
    print(json.dumps(summary, sort_keys=True))
    return int(bool(summary["property_missing"] or summary["aerials"] != len(ids) or summary["provider_failures"]))


if __name__ == "__main__":
    raise SystemExit(main())
