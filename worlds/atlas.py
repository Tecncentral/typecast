"""World Labs Atlas Developer API client (https://docs.atlas.worldlabs.ai).

Base https://api.atlas.worldlabs.ai/api/v2, header WLT-Api-Key. The key is only ever sent to
that host, never logged, and redirects are refused. Task outputs are signed read URLs that
download without the key. 1,000 credits = $1. Only posedImages2Splats has a published price
(5,000 credits refined); other tasks follow the account's rate card, so callers record each
operation and the human checks the balance in the Atlas console.
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import requests

ATLAS_BASE = "https://api.atlas.worldlabs.ai/api/v2"
MAX_DOWNLOAD = 400 * 1024 * 1024


class AtlasError(RuntimeError):
    """Sanitized: never contains the key, request bodies or image data."""


@dataclass
class AtlasClient:
    api_key: Optional[str] = None
    session: Any = None
    timeout_s: float = 2400.0
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self):
        self.api_key = (self.api_key or os.getenv("WORLDLABS_API_KEY") or "").strip()
        if not self.api_key:
            raise AtlasError("WORLDLABS_API_KEY is not set")
        self.session = self.session or requests.Session()

    def _request(self, method: str, path: str, body: Optional[dict] = None,
                 idempotency_key: Optional[str] = None, timeout: float = 120) -> dict:
        headers = {"WLT-Api-Key": self.api_key, "Content-Type": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:128]
        try:
            response = self.session.request(method, ATLAS_BASE + path, headers=headers,
                                            data=None if body is None else json.dumps(body),
                                            timeout=(10, timeout), allow_redirects=False)
        except requests.RequestException as error:
            raise AtlasError(f"Atlas network failure ({type(error).__name__})") from None
        if response.status_code >= 300:
            code, message = "", ""
            try:
                payload = response.json()
                code = str(payload.get("code") or (payload.get("error") or {}).get("code") or "")
                message = str(payload.get("message") or (payload.get("error") or {}).get("message")
                              or payload.get("detail") or "")
            except (ValueError, AttributeError):
                pass
            message = message[:240].replace(self.api_key, "<key>")
            raise AtlasError(f"Atlas HTTP {response.status_code} on {method} {path.split('?')[0]}"
                             + (f" [{code}]" if code else "") + (f": {message}" if message else ""))
        try:
            return response.json()
        except ValueError:
            raise AtlasError("Atlas returned non-JSON") from None

    # ---- assets ----
    def upload_image(self, path: pathlib.Path) -> str:
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return self.upload_bytes(pathlib.Path(path).read_bytes(), mime, path.name)

    def read_bytes(self, asset_id: str, limit: int = 64 * 1024 * 1024) -> bytes:
        """An asset's content, through a short-lived read URL that is fetched without the key."""
        url = self._request("POST", f"/assets/{asset_id}:createReadUrl", {}).get("readUrl") or ""
        if urlparse(url).scheme != "https":
            raise AtlasError("Atlas did not return an HTTPS read URL")
        try:
            with self.session.get(url, timeout=(10, 300), stream=True) as response:
                if response.status_code != 200:
                    raise AtlasError(f"Asset download HTTP {response.status_code}")
                data = b""
                for chunk in response.iter_content(1 << 16):
                    data += chunk
                    if len(data) > limit:
                        raise AtlasError("Asset larger than the copy limit")
        except requests.RequestException as error:
            raise AtlasError(f"Asset download failed ({type(error).__name__})") from None
        return data

    def upload_bytes(self, data: bytes, mime: str, name: str) -> str:
        if len(data) >= 10 * 1024 * 1024:
            raise AtlasError("Image is over the 10 MiB inline limit")
        body = {"asset": {"displayName": name[:120],
                          "base64": f"data:{mime};base64," + base64.b64encode(data).decode("ascii")}}
        asset = self._request("POST", "/assets", body)
        asset = asset.get("asset", asset)
        asset_id = asset.get("id") or str(asset.get("name", "")).split("/")[-1]
        if not asset_id:
            raise AtlasError("Atlas did not return an asset id")
        return asset_id

    # ---- tasks and operations ----
    def submit(self, task: str, body: dict, idempotency_key: Optional[str] = None) -> dict:
        return self._request("POST", f"/tasks:{task}", body, idempotency_key)

    def wait(self, operation: dict, on_poll: Callable[[dict], None] | None = None) -> dict:
        op_id = operation.get("id") or str(operation.get("name", "")).split("/")[-1]
        if not op_id:
            raise AtlasError("Atlas did not return an operation id")
        deadline = time.monotonic() + self.timeout_s
        op = operation
        while not op.get("done"):
            if time.monotonic() > deadline:
                raise AtlasError(f"Operation {op_id} still running after {self.timeout_s:.0f} s")
            try:
                op = self._request("POST", f"/operations/{op_id}:wait", {"timeoutSecs": 30}, timeout=75)
            except AtlasError as error:
                if "HTTP 504" not in str(error):
                    raise
                op = self._request("GET", f"/operations/{op_id}")
            if on_poll:
                on_poll(op)
        if op.get("error"):
            err = op["error"] or {}
            reasons = ",".join(str(d.get("reason")) for d in (err.get("details") or []) if isinstance(d, dict))
            raise AtlasError(f"Operation {op_id} failed" + (f" [{reasons}]" if reasons else "")
                             + (f": {str(err.get('message'))[:200]}" if err.get("message") else ""))
        return op

    def download(self, url: str, dest: pathlib.Path) -> pathlib.Path:
        """Task output URLs are signed and are fetched without the key."""
        if urlparse(url).scheme != "https":
            raise AtlasError("Refusing a non-HTTPS asset URL")
        try:
            with self.session.get(url, timeout=(10, 300), stream=True) as response:
                if response.status_code != 200:
                    raise AtlasError(f"Asset download HTTP {response.status_code}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_suffix(dest.suffix + ".part")
                size = 0
                with tmp.open("wb") as handle:
                    for chunk in response.iter_content(1 << 16):
                        size += len(chunk)
                        if size > MAX_DOWNLOAD:
                            raise AtlasError("Asset larger than the cache limit")
                        handle.write(chunk)
                tmp.replace(dest)
        except requests.RequestException as error:
            raise AtlasError(f"Asset download failed ({type(error).__name__})") from None
        return dest
