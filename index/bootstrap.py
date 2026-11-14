"""Reproducible end-to-end Matterport cache bootstrap for Owner 1."""
from __future__ import annotations

import argparse, csv, io, json, os, sys, tempfile
from pathlib import Path
from typing import Any, Sequence
import httpx, numpy as np
from PIL import Image

from index.build import prepare, cache_path, encode_incremental
from index.matterport import (atomic_write_json, fetch_model_record, ingest_matterport,
                             load_matterport_credentials, load_model_property_pairs)
from index.rooms import ROOMS_GRAPHQL_QUERY, enrich_source_manifest
from index.store import DEFAULT_MODEL, ROOT, encoder, save_index

CATALOG_URL = "https://static.matterport.com/hackathon/26.15.39-main-39-gef8d668/assets/quickstart/models_index.csv"
CACHE_DIR = ROOT / "cache/matterport"
REQUIRED_HEADERS = ("sid", "city", "costar_property_id", "pano_count")
MAX_CSV_BYTES = 10 * 1024 * 1024
ENCODE_BATCH_SIZE = 16


class BootstrapError(RuntimeError):
    """Raised when catalog download, selection, or index bootstrap fails."""


def _atomic_write_text(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def select_catalog_models(csv_text: str, *, city: str = "Los Angeles", max_models: int = 20) -> list[dict[str, str]]:
    if not 1 <= max_models <= 20:
        raise BootstrapError("max_models must be between 1 and 20")
    reader = csv.DictReader(io.StringIO(csv_text))
    headers = reader.fieldnames or []
    if len(headers) != len(set(headers)) or not set(REQUIRED_HEADERS).issubset(headers):
        raise BootstrapError('Invalid CSV headers: required sponsor columns missing or duplicated')
    target_city = city.strip().casefold()
    eligible: list[tuple[str, str]] = []
    for row in reader:
        if any(row.get(col) is None for col in REQUIRED_HEADERS):
            raise BootstrapError("Malformed CSV row with missing columns")
        sid, row_city = row["sid"].strip(), row["city"].strip()
        prop_id = row["costar_property_id"].strip()
        try:
            panos = int(row["pano_count"].strip() or '0')
        except ValueError as exc:
            raise BootstrapError(f"Invalid pano_count for sid {sid!r}") from exc
        if sid and prop_id and row_city.casefold() == target_city and panos >= 8:
            eligible.append((sid, prop_id))
    selected: list[dict[str, str]] = []
    seen_props: set[str] = set()
    for sid, prop_id in sorted(eligible, key=lambda item: item[0]):
        if prop_id in seen_props:
            continue
        seen_props.add(prop_id)
        selected.append({"model_id": sid, "property_id": prop_id})
        if len(selected) >= max_models:
            break
    if not selected:
        raise BootstrapError(f"No eligible models found for city={city!r} with pano_count>=8")
    return selected


def fetch_catalog_csv(url: str = CATALOG_URL, *, timeout: float = 15.0) -> str:
    if not url.startswith("https://"):
        raise BootstrapError("Catalog URL must use HTTPS")
    buf = bytearray()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    raise BootstrapError(f"Catalog download failed with HTTP {resp.status_code}")
                for chunk in resp.iter_bytes():
                    buf.extend(chunk)
                    if len(buf) > MAX_CSV_BYTES:
                        raise BootstrapError("Catalog CSV exceeds 10MB limit")
    except httpx.HTTPError as exc:
        raise BootstrapError(f"Catalog download transport error ({type(exc).__name__})") from exc
    return buf.decode("utf-8")


def _encode_shot_images(shots: Sequence[Any], model_name: str) -> np.ndarray:
    from index.store import load_index
    try:
        old_shots, old_vectors, old_model = load_index()
    except RuntimeError:
        old_shots, old_vectors, old_model = (), None, model_name
    if old_vectors is not None and old_model == model_name:
        return encode_incremental(shots, previous_shots=old_shots,
            previous_vectors=old_vectors, model_name=model_name, batch_size=ENCODE_BATCH_SIZE)
    encode_fn = encoder(model_name)
    batches: list[np.ndarray] = []
    for start in range(0, len(shots), ENCODE_BATCH_SIZE):
        imgs = []
        for shot in shots[start : start + ENCODE_BATCH_SIZE]:
            img_path = cache_path(shot.image_path.lstrip('/'))
            with Image.open(img_path) as im:
                imgs.append(im.convert("RGB"))
        batches.append(np.asarray(encode_fn.encode(imgs, batch_size=16,
            convert_to_numpy=True, normalize_embeddings=True), dtype=np.float32))
        for image in imgs:
            image.close()
    return np.vstack(batches).astype(np.float32)


def run_bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    if args.max_models < 1 or not 1 <= args.max_sweeps <= 12:
        raise BootstrapError("--max-models must be positive and --max-sweeps must be 1..12")
    if not args.models and args.max_models > 20:
        raise BootstrapError("Automatic city samples are capped at 20; use --models or index.bulk for explicit larger coverage")
    auth = load_matterport_credentials(ROOT / '.env')
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if args.models:
        models_path = cache_path(args.models)
        if not models_path.is_file():
            raise BootstrapError(f"Explicit --models file not found: {models_path}")
    else:
        csv_path = CACHE_DIR / "models_index.csv"
        if args.reuse_catalog:
            if not csv_path.is_file():
                raise BootstrapError(f"--reuse-catalog set but {csv_path} does not exist")
            csv_text = csv_path.read_text(encoding="utf-8")
        else:
            csv_text = fetch_catalog_csv()
            _atomic_write_text(csv_path, csv_text)
        selected = select_catalog_models(csv_text, city=args.city, max_models=args.max_models)
        models_path = CACHE_DIR / "selected_models.json"
        atomic_write_json(models_path, selected)

    previous_path = CACHE_DIR / 'source_manifest.json'
    previous_rows = json.loads(previous_path.read_text()).get('records', []) if previous_path.is_file() else []
    def record_key(row):
        return (row.get('property_id'), row.get('model_id'), row.get('sweep_id'), row.get('heading_deg'))
    previous_by_key = {record_key(row): row for row in previous_rows}
    manifest, report = ingest_matterport(models_path=models_path, output_dir=CACHE_DIR, max_models=args.max_models, max_sweeps=args.max_sweeps)
    requested_ids = {p.model_id for p in load_model_property_pairs(models_path, max_models=args.max_models)}
    model_ids = sorted({r["model_id"] for r in manifest.get("records") or []
                        if r.get("model_id") in requested_ids})
    rooms_by_model: dict[str, Any] = {}
    room_failures = 0
    with httpx.Client(timeout=15.0, follow_redirects=False) as client:
        for mid in model_ids:
            try:
                rooms_by_model[mid] = {"data": {"model": fetch_model_record(client,
                    model_id=mid, auth=auth, query=ROOMS_GRAPHQL_QUERY)}}
            except Exception:
                room_failures += 1
    from index.planning import room_plans
    plans_path = CACHE_DIR / 'room-plans.json'
    plans = json.loads(plans_path.read_text()) if plans_path.is_file() else {}
    plans.update(room_plans(rooms_by_model))
    atomic_write_json(plans_path, plans)
    current_records = [r for r in manifest['records'] if r.get('model_id') in rooms_by_model]
    untouched = []
    for row in manifest['records']:
        if row.get('model_id') in rooms_by_model:
            continue
        old = previous_by_key.get(record_key(row))
        resumed = (row.get('provenance') or {}).get('ingest_status') == 'resumed_local'
        untouched.append(old if old is not None and resumed else row)
    enriched = {**manifest, 'records': untouched + enrich_source_manifest(
        {'records': current_records}, rooms_by_model)['records']}
    manifest_path = CACHE_DIR / "source_manifest.json"
    atomic_write_json(manifest_path, enriched)

    shots = prepare(manifest_path)
    if not shots:
        raise BootstrapError("prepare() produced zero shots")
    stage_summary: dict[str, Any] = {
        "ingest": {"models_succeeded": getattr(report, "models_succeeded", len(model_ids)), "shots_written": getattr(report, "shots_written", 0), "shots_resumed": getattr(report, "shots_resumed", 0)},
        "rooms_enriched": len(rooms_by_model),
        "room_failures": room_failures,
        "shots_prepared": len(shots),
        "index_saved": False,
    }
    if not args.prepare_only:
        vectors = _encode_shot_images(shots, DEFAULT_MODEL)
        save_index(shots, vectors)
        stage_summary["index_saved"] = True
        stage_summary["index_root"] = str(ROOT)
    return stage_summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Matterport local shot index.")
    parser.add_argument("--models", default=None, help="Existing private models JSON path.")
    parser.add_argument("--city", default="Los Angeles", help="City filter for models_index.csv.")
    parser.add_argument("--max-models", type=int, default=20, help="Max models (explicit --models has no 20-model cap).")
    parser.add_argument("--max-sweeps", type=int, default=8, help="Max sweeps per model (1..12).")
    parser.add_argument("--reuse-catalog", action="store_true", help="Reuse cached models_index.csv without downloading.")
    parser.add_argument("--prepare-only", action="store_true", help="Skip CLIP image encoding and save_index.")
    try:
        summary = run_bootstrap(parser.parse_args(argv))
    except Exception as exc:
        # Provider exception bodies can contain private URLs; expose type only.
        message = str(exc) if isinstance(exc, BootstrapError) else type(exc).__name__
        print(json.dumps({"ok": False, "error": message,
            "help": "Check private .env, optional index requirements and cache inputs."}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "stages": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
