"""Offline-safe Matterport skybox horizon ingestion for Owner 1 (Typecast).

Fetches panorama locations and 2k skybox cube faces from Matterport's GraphQL API,
downloads only the four horizon faces (indices 1..4) via a separate unauthenticated
HTTPS session with SSRF redirect guards, verifies local image decoding via Pillow,
and atomically writes cache/matterport/source_manifest.json.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import time
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
from PIL import Image, UnidentifiedImageError
import httpx


MATTERPORT_GRAPH_ENDPOINT = "https://api.matterport.com/api/models/graph"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "cache/matterport"
SOURCE_MANIFEST_FILENAME = "source_manifest.json"
IMAGES_SUBDIR = "images"

DEFAULT_MAX_MODELS = 20
DEFAULT_MAX_SWEEPS = 12
DEFAULT_TIMEOUT_SEC = 15.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SEC = 0.5
MAX_IMAGE_BYTES = 32 * 1024 * 1024  # 32 MiB ceiling per cube face
MAX_REDIRECTS = 3

# Cube face indices: 0=up, 1..4=horizon, 5=down.
# Headings are cube-local relative directions, never true compass bearings.
HORIZON_FACE_HEADINGS: dict[int, float] = {
    1: 0.0,
    2: 90.0,
    3: 180.0,
    4: 270.0,
}

ORIENTATION_CAVEAT = (
    "heading_deg values (0, 90, 180, 270) are cube-local relative horizon face "
    "directions (children indices 1..4), not true compass bearings or north-aligned azimuths."
)

PANOS_GRAPHQL_QUERY = (
    'query Panos($id: ID!) { model(id:$id) { panoLocations { id label '
    'position {x y z} skybox(resolution:"2k") {status children} } } }'
)

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


class MatterportIngestionError(RuntimeError):
    """Raised when Matterport ingestion encounters a fatal configuration or protocol error."""


class HttpResponseLike(Protocol):
    status_code: int
    headers: Mapping[str, str]
    content: bytes

    def json(self) -> Any: ...


class HttpSessionLike(Protocol):
    def post(
        self,
        url: str,
        *,
        json: Any = None,
        auth: tuple[str, str] | None = None,
        timeout: float | tuple[float, float] = ...,
        follow_redirects: bool = ...,
    ) -> HttpResponseLike: ...

    def get(
        self,
        url: str,
        *,
        timeout: float | tuple[float, float] = ...,
        follow_redirects: bool = ...,
        stream: bool = ...,
    ) -> HttpResponseLike: ...


@dataclass(frozen=True)
class ModelPropertyPair:
    model_id: str
    property_id: str


@dataclass
class IngestionReport:
    models_requested: int = 0
    models_succeeded: int = 0
    models_failed: int = 0
    sweeps_seen: int = 0
    sweeps_skipped: int = 0
    shots_written: int = 0
    shots_resumed: int = 0
    shots_failed: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "models_requested": self.models_requested,
            "models_succeeded": self.models_succeeded,
            "models_failed": self.models_failed,
            "sweeps_seen": self.sweeps_seen,
            "sweeps_skipped": self.sweeps_skipped,
            "shots_written": self.shots_written,
            "shots_resumed": self.shots_resumed,
            "shots_failed": self.shots_failed,
            "errors": list(self.errors),
        }


def validate_identifier(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID_RE.match(value):
        raise MatterportIngestionError(
            f"Invalid {field_name}: must match {_SAFE_ID_RE.pattern!r}"
        )
    return value


def resolve_safe_subpath(base_dir: Path, *parts: str) -> Path:
    resolved_base = base_dir.resolve()
    candidate = resolved_base.joinpath(*parts).resolve()
    if resolved_base != candidate and resolved_base not in candidate.parents:
        raise MatterportIngestionError("Path traversal detected outside output directory")
    return candidate


def _is_non_public_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def validate_public_https_url(
    raw_url: str,
    *,
    resolver: Callable[[str], Sequence[str]] | None = None,
) -> str:
    """Ensure URL is strict HTTPS and does not target localhost or private/reserved IPs."""
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise MatterportIngestionError("Signed image URL is empty")
    parsed = urlparse(raw_url.strip())
    if parsed.scheme.lower() != "https":
        raise MatterportIngestionError("Refusing non-HTTPS image URL")
    if parsed.username or parsed.password:
        raise MatterportIngestionError("Refusing URL containing embedded userinfo")
    hostname = parsed.hostname
    if not hostname:
        raise MatterportIngestionError("Refusing image URL without hostname")
    lower_host = hostname.lower()
    if lower_host == "localhost" or lower_host.endswith(".localhost") or lower_host.endswith(".local"):
        raise MatterportIngestionError("Refusing localhost/local domain image URL")

    # Direct IP literal check
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        ips = _default_dns_resolve(hostname) if resolver is None else list(resolver(hostname))
        if not ips:
            raise MatterportIngestionError("Failed to resolve image host")
        for ip_item in ips:
            if _is_non_public_ip(ip_item):
                raise MatterportIngestionError("Refusing image URL resolving to private/local IP")
    else:
        if _is_non_public_ip(hostname):
            raise MatterportIngestionError("Refusing image URL targeting private/local IP")

    return raw_url.strip()


def _default_dns_resolve(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise MatterportIngestionError("DNS resolution failed for CDN host") from exc
    ips: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr and isinstance(sockaddr[0], str):
            ips.append(sockaddr[0])
    return ips


def load_model_property_pairs(models_path: str | Path, *, max_models: int) -> list[ModelPropertyPair]:
    if max_models <= 0:
        raise MatterportIngestionError("--max-models must be >= 1")
    path = Path(models_path)
    if not path.is_file():
        raise MatterportIngestionError(f"Models input file not found: '{path}'")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MatterportIngestionError(f"Invalid JSON in models input '{path}': {exc}") from exc

    if isinstance(raw, dict) and isinstance(raw.get("models"), list):
        entries = raw["models"]
    elif isinstance(raw, list):
        entries = raw
    else:
        raise MatterportIngestionError(
            "Models JSON must be a list of {model_id, property_id} objects or {'models': [...]}"
        )

    pairs: list[ModelPropertyPair] = []
    seen_models: set[str] = set()
    for idx, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise MatterportIngestionError(f"Models entry at index {idx} must be an object")
        model_id = validate_identifier(entry.get("model_id"), field_name=f"models[{idx}].model_id")
        property_id = validate_identifier(
            entry.get("property_id"), field_name=f"models[{idx}].property_id"
        )
        if model_id in seen_models:
            raise MatterportIngestionError(f"Duplicate model_id '{model_id}' in models input")
        seen_models.add(model_id)
        pairs.append(ModelPropertyPair(model_id=model_id, property_id=property_id))

    if not pairs:
        raise MatterportIngestionError("Models input contains zero model/property pairs")
    return pairs[:max_models]


def load_matterport_credentials(env_path: str | Path | None = None) -> tuple[str, str]:
    """Load MATTERPORT_API_KEY and MATTERPORT_API_TOKEN via dotenv without logging values."""
    if env_path is not None:
        load_dotenv(dotenv_path=Path(env_path), override=False)
    else:
        load_dotenv(override=False)

    api_key = os.environ.get("MATTERPORT_API_KEY", "").strip()
    api_token = os.environ.get("MATTERPORT_API_TOKEN", "").strip()
    if not api_key or not api_token:
        raise MatterportIngestionError(
            "Missing MATTERPORT_API_KEY or MATTERPORT_API_TOKEN in environment/.env"
        )
    return api_key, api_token


def is_valid_local_image(path: Path) -> bool:
    """Verify file exists, is non-empty, and decodes cleanly via Pillow."""
    if not path.is_file():
        return False
    try:
        if path.stat().st_size <= 0:
            return False
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            img.load()
            width, height = img.size
        return width > 0 and height > 0
    except (OSError, UnidentifiedImageError, ValueError):
        return False


def validate_and_decode_image_bytes(data: bytes) -> None:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise MatterportIngestionError("Downloaded image payload empty or exceeds size limit")
    try:
        with Image.open(BytesIO(data)) as img:
            img.verify()
        with Image.open(BytesIO(data)) as img:
            img.load()
            w, h = img.size
        if w <= 0 or h <= 0:
            raise MatterportIngestionError("Decoded image has non-positive dimensions")
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise MatterportIngestionError("Downloaded payload is not a valid decodable image") from exc


def atomic_write_bytes(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def atomic_write_json(target: Path, data: Any) -> None:
    encoded = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_bytes(target, encoded)


def _sleep_backoff(attempt: int, base_sec: float, sleep_fn: Callable[[float], None]) -> None:
    delay = base_sec * (2**attempt)
    if delay > 0:
        sleep_fn(delay)


def fetch_model_panos(
    session: HttpSessionLike,
    *,
    model_id: str,
    auth: tuple[str, str],
    endpoint: str = MATTERPORT_GRAPH_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE_SEC,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Query Matterport GraphQL API for panoLocations without leaking auth or signed URLs."""
    if endpoint != MATTERPORT_GRAPH_ENDPOINT:
        raise MatterportIngestionError("Credentials may only be sent to the official Matterport endpoint")
    payload = {
        "query": PANOS_GRAPHQL_QUERY,
        "variables": {"id": model_id},
    }

    last_error: str = "unknown error"
    for attempt in range(max_retries + 1):
        try:
            resp = session.post(
                endpoint,
                json=payload,
                auth=auth,
                timeout=timeout,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            last_error = f"GraphQL transport error ({type(exc).__name__})"
            if attempt < max_retries:
                _sleep_backoff(attempt, backoff_base, sleep_fn)
                continue
            raise MatterportIngestionError(
                f"GraphQL request failed for model '{model_id}': {last_error}"
            ) from exc

        status = int(resp.status_code)
        if 300 <= status < 400:
            raise MatterportIngestionError(
                f"GraphQL endpoint returned unexpected redirect (HTTP {status}) for model '{model_id}'"
            )
        if status in _RETRYABLE_STATUS_CODES and attempt < max_retries:
            last_error = f"HTTP {status}"
            _sleep_backoff(attempt, backoff_base, sleep_fn)
            continue
        if status != 200:
            raise MatterportIngestionError(
                f"GraphQL request failed for model '{model_id}' with HTTP {status}"
            )

        try:
            body = resp.json()
        except ValueError as exc:
            raise MatterportIngestionError(
                f"GraphQL response for model '{model_id}' was not valid JSON"
            ) from exc

        if not isinstance(body, Mapping):
            raise MatterportIngestionError(
                f"GraphQL response for model '{model_id}' must be a JSON object"
            )

        errors = body.get("errors")
        if errors:
            # Sanitize: report only high-level message/code without echoing raw extensions/URLs.
            msg = "Provider rejected query; inspect schema or permissions privately"
            raise MatterportIngestionError(f"GraphQL error for model '{model_id}': {msg}")

        data = body.get("data")
        model_obj = data.get("model") if isinstance(data, Mapping) else None
        if not isinstance(model_obj, Mapping):
            raise MatterportIngestionError(
                f"GraphQL response missing data.model for model '{model_id}'"
            )
        panos = model_obj.get("panoLocations")
        if not isinstance(panos, list):
            raise MatterportIngestionError(
                f"GraphQL response missing panoLocations list for model '{model_id}'"
            )
        return [p for p in panos if isinstance(p, dict)]

    raise MatterportIngestionError(
        f"GraphQL request exhausted retries for model '{model_id}': {last_error}"
    )


def download_cdn_image_bytes(
    cdn_session: HttpSessionLike,
    signed_url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE_SEC,
    sleep_fn: Callable[[float], None] = time.sleep,
    dns_resolver: Callable[[str], Sequence[str]] | None = None,
) -> bytes:
    """Download a signed CDN image using an unauthenticated session with strict HTTPS/SSRF checks."""
    current_url = validate_public_https_url(signed_url, resolver=dns_resolver)

    for attempt in range(max_retries + 1):
        try:
            url_to_fetch = current_url
            redirects_followed = 0
            while True:
                validate_public_https_url(url_to_fetch, resolver=dns_resolver)
                resp = cdn_session.get(
                    url_to_fetch,
                    timeout=timeout,
                    follow_redirects=False,

                )
                status = int(resp.status_code)
                if status in {301, 302, 303, 307, 308}:
                    if redirects_followed >= MAX_REDIRECTS:
                        raise MatterportIngestionError("Too many CDN redirects")
                    location = resp.headers.get("Location") or resp.headers.get("location")
                    if not location:
                        raise MatterportIngestionError("CDN redirect missing Location header")
                    next_url = urljoin(url_to_fetch, location)
                    validate_public_https_url(next_url, resolver=dns_resolver)
                    url_to_fetch = next_url
                    redirects_followed += 1
                    continue
                break
        except MatterportIngestionError:
            raise
        except httpx.HTTPError as exc:
            if attempt < max_retries:
                _sleep_backoff(attempt, backoff_base, sleep_fn)
                continue
            raise MatterportIngestionError(
                f"CDN download transport error ({type(exc).__name__})"
            ) from exc

        status = int(resp.status_code)
        if status in _RETRYABLE_STATUS_CODES and attempt < max_retries:
            _sleep_backoff(attempt, backoff_base, sleep_fn)
            continue
        if status != 200:
            raise MatterportIngestionError(f"CDN download failed with HTTP {status}")

        payload = resp.content
        validate_and_decode_image_bytes(payload)
        return payload

    raise MatterportIngestionError("CDN download exhausted retries")


def _extract_position(pano: Mapping[str, Any]) -> dict[str, float] | None:
    pos = pano.get("position")
    if not isinstance(pos, Mapping):
        return None
    out: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        val = pos.get(axis)
        if val is None:
            return None
        try:
            fval = float(val)
        except (TypeError, ValueError):
            return None
        if fval != fval or fval in (float("inf"), float("-inf")):
            return None
        out[axis] = fval
    return out


def _validate_skybox_children(pano: Mapping[str, Any], *, model_id: str, sweep_id: str) -> list[str]:
    skybox = pano.get("skybox")
    if not isinstance(skybox, Mapping):
        raise MatterportIngestionError(
            f"Sweep '{sweep_id}' in model '{model_id}' missing skybox object"
        )
    status = skybox.get("status")
    if not isinstance(status, str) or status.lower() not in {"available", "ready", "complete", "completed", "ok"}:
        raise MatterportIngestionError(
            f"Sweep '{sweep_id}' in model '{model_id}' has non-ready skybox status '{status}'"
        )
    children = skybox.get("children")
    if not isinstance(children, list) or len(children) != 6:
        raise MatterportIngestionError(
            f"Sweep '{sweep_id}' in model '{model_id}' must have exactly 6 skybox children"
        )
    urls: list[str] = []
    for idx, child in enumerate(children):
        if not isinstance(child, str) or not child.strip():
            raise MatterportIngestionError(
                f"Sweep '{sweep_id}' in model '{model_id}' has empty skybox child at index {idx}"
            )
        urls.append(child.strip())
    return urls


def ingest_matterport(
    *,
    models_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    max_models: int = DEFAULT_MAX_MODELS,
    max_sweeps: int = DEFAULT_MAX_SWEEPS,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE_SEC,
    endpoint: str = MATTERPORT_GRAPH_ENDPOINT,
    auth: tuple[str, str] | None = None,
    graph_session: HttpSessionLike | None = None,
    cdn_session: HttpSessionLike | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    dns_resolver: Callable[[str], Sequence[str]] | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> tuple[dict[str, Any], IngestionReport]:
    """Run Matterport ingestion and write cache/matterport/source_manifest.json atomically."""
    if max_sweeps <= 0:
        raise MatterportIngestionError("--max-sweeps must be >= 1")
    if timeout <= 0:
        raise MatterportIngestionError("--timeout must be > 0")
    if max_retries < 0:
        raise MatterportIngestionError("--max-retries must be >= 0")

    credentials = auth if auth is not None else load_matterport_credentials()
    pairs = load_model_property_pairs(models_path, max_models=max_models)

    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    images_root = out_root / IMAGES_SUBDIR
    images_root.mkdir(parents=True, exist_ok=True)

    # Strict separation: graph_session handles Basic Auth to Matterport GraphQL;
    # cdn_session never receives auth credentials.
    own_graph = graph_session is None
    own_cdn = cdn_session is None
    g_sess: HttpSessionLike = httpx.Client() if graph_session is None else graph_session
    c_sess: HttpSessionLike = httpx.Client() if cdn_session is None else cdn_session

    clock = now_fn or (lambda: datetime.now(timezone.utc))
    report = IngestionReport(models_requested=len(pairs))
    records: list[dict[str, Any]] = []

    try:
        for pair in pairs:
            try:
                panos = fetch_model_panos(
                    g_sess,
                    model_id=pair.model_id,
                    auth=credentials,
                    endpoint=endpoint,
                    timeout=timeout,
                    max_retries=max_retries,
                    backoff_base=backoff_base,
                    sleep_fn=sleep_fn,
                )
            except MatterportIngestionError as exc:
                report.models_failed += 1
                report.errors.append(str(exc))
                continue

            report.models_succeeded += 1
            bounded_panos = panos[:max_sweeps]

            for pano in bounded_panos:
                report.sweeps_seen += 1
                raw_sweep_id = pano.get("id")
                try:
                    sweep_id = validate_identifier(raw_sweep_id, field_name="pano.id")
                    children = _validate_skybox_children(
                        pano, model_id=pair.model_id, sweep_id=sweep_id
                    )
                except MatterportIngestionError as exc:
                    report.sweeps_skipped += 1
                    report.errors.append(str(exc))
                    continue

                position = _extract_position(pano)
                raw_label = pano.get("label")
                sweep_label = raw_label.strip() if isinstance(raw_label, str) and raw_label.strip() else None

                for face_idx, heading_deg in HORIZON_FACE_HEADINGS.items():
                    face_url = children[face_idx]
                    rel_image_path = Path(IMAGES_SUBDIR) / pair.model_id / f"{sweep_id}_face{face_idx}.jpg"
                    abs_image_path = resolve_safe_subpath(
                        out_root, IMAGES_SUBDIR, pair.model_id, f"{sweep_id}_face{face_idx}.jpg"
                    )

                    fetched_at = clock().isoformat()
                    if is_valid_local_image(abs_image_path):
                        report.shots_resumed += 1
                        source_state = "resumed_local"
                    else:
                        try:
                            img_bytes = download_cdn_image_bytes(
                                c_sess,
                                face_url,
                                timeout=timeout,
                                max_retries=max_retries,
                                backoff_base=backoff_base,
                                sleep_fn=sleep_fn,
                                dns_resolver=dns_resolver,
                            )
                            atomic_write_bytes(abs_image_path, img_bytes)
                            report.shots_written += 1
                            source_state = "downloaded"
                        except MatterportIngestionError as exc:
                            report.shots_failed += 1
                            report.errors.append(
                                f"Face {face_idx} failed for {pair.model_id}/{sweep_id}: {exc}"
                            )
                            continue

                    shot_id = f"{pair.model_id}__{sweep_id}__f{face_idx}"
                    records.append(
                        {
                            "shot_id": shot_id,
                            "model_id": pair.model_id,
                            "sweep_id": sweep_id,
                            "property_id": pair.property_id,
                            "image_path": rel_image_path.as_posix(),
                            "format": "perspective",
                            "heading_deg": heading_deg,
                            "room_area_m2": None,
                            "ceiling_m": None,
                            "depth_m": None,
                            "measure_on_site": True,
                            "provenance": {
                                "source": "matterport_skybox_2k",
                                "cube_face_index": face_idx,
                                "position_m": position,
                                "sweep_label": sweep_label,
                                "fetched_at": fetched_at,
                                "ingest_status": source_state,
                                "orientation_caveat": ORIENTATION_CAVEAT,
                            },
                        }
                    )
    finally:
        if own_graph and hasattr(g_sess, "close"):
            g_sess.close()  # type: ignore[attr-defined]
        if own_cdn and hasattr(c_sess, "close"):
            c_sess.close()  # type: ignore[attr-defined]

    manifest_payload: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": clock().isoformat(),
        "orientation_caveat": ORIENTATION_CAVEAT,
        "summary": report.to_dict(),
        "records": records,
    }
    manifest_path = out_root / SOURCE_MANIFEST_FILENAME
    atomic_write_json(manifest_path, manifest_payload)

    if not records:
        raise MatterportIngestionError(
            "Ingestion produced zero valid perspective shots; see summary report in source_manifest.json"
        )

    return manifest_payload, report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest Matterport 2k skybox horizon faces into cache/matterport/source_manifest.json."
    )
    parser.add_argument(
        "--models",
        required=True,
        help="Path to JSON file containing explicit {model_id, property_id} pairs.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Private cache directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--max-models",
        type=int,
        default=DEFAULT_MAX_MODELS,
        help=f"Maximum models to process (default: {DEFAULT_MAX_MODELS}).",
    )
    parser.add_argument(
        "--max-sweeps",
        type=int,
        default=DEFAULT_MAX_SWEEPS,
        help=f"Maximum sweeps per model (default: {DEFAULT_MAX_SWEEPS}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SEC,
        help=f"Per-request timeout in seconds (default: {DEFAULT_TIMEOUT_SEC}).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Maximum retry attempts on transient errors (default: {DEFAULT_MAX_RETRIES}).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        if not Path(args.output_dir).resolve().is_relative_to((ROOT / 'cache').resolve()):
            raise MatterportIngestionError("CLI output must remain inside ignored cache/")
        _, report = ingest_matterport(
            models_path=args.models,
            output_dir=args.output_dir,
            max_models=args.max_models,
            max_sweeps=args.max_sweeps,
            timeout=args.timeout,
            max_retries=args.max_retries,
        )
    except MatterportIngestionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
