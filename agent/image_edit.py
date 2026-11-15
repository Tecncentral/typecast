"""One image edit for the reimagine chats, with OpenAI or Google Gemini ("Nano Banana").

TYPECAST_IMAGE_PROVIDER picks the provider: "openai" (default) uses TYPECAST_OBLIQUE_IMAGE_MODEL at
TYPECAST_OBLIQUE_IMAGE_QUALITY; "gemini" uses TYPECAST_GEMINI_IMAGE_MODEL with GEMINI_API_KEY: default gemini-3.1-flash-lite-image
("Nano Banana 2 Lite", ~4 s, cheapest) for testing; gemini-3-pro-image ("Nano Banana Pro", ~18 s) for
the demo. Gemini edits keep the untouched parts of the photo intact. Keys go only to their provider, with
redirects disabled; errors never carry keys or response bodies.
"""
from __future__ import annotations

import base64
import os

import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ASPECTS = {"1536x1024": "3:2", "1024x1536": "2:3", "1024x1024": "1:1"}


class ImageEditError(RuntimeError):
    """Sanitized: never contains a key or a provider response body."""


def provider() -> str:
    return "gemini" if os.getenv("TYPECAST_IMAGE_PROVIDER", "").strip().lower() == "gemini" else "openai"


def describe() -> tuple[str, str]:
    """(model, quality-or-provider) for labels and notes."""
    if provider() == "gemini":
        return os.getenv("TYPECAST_GEMINI_IMAGE_MODEL", "gemini-3.1-flash-lite-image").strip(), "gemini"
    return (os.getenv("TYPECAST_OBLIQUE_IMAGE_MODEL", "gpt-image-1-mini").strip(),
            os.getenv("TYPECAST_OBLIQUE_IMAGE_QUALITY", "low").strip())


def _gemini(png: bytes, prompt: str, size: str, model: str) -> bytes:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ImageEditError("GEMINI_API_KEY is not set on this machine")
    body = {"contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(png).decode()}},
                {"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"],
                                 "imageConfig": {"aspectRatio": ASPECTS.get(size, "3:2")}}}
    try:
        r = requests.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": key}, json=body,
                          timeout=(10, 240), allow_redirects=False)
    except requests.RequestException as error:
        raise ImageEditError(f"Gemini network failure ({type(error).__name__})") from None
    if r.status_code != 200:
        raise ImageEditError(f"Gemini HTTP {r.status_code}")
    for candidate in r.json().get("candidates", []):
        for part in (candidate.get("content") or {}).get("parts", []):
            data = (part.get("inlineData") or part.get("inline_data") or {}).get("data")
            if data:
                return base64.b64decode(data)
    raise ImageEditError("Gemini returned no image (it may have declined the request)")


def edit_image(png: bytes, prompt: str, size: str, *, client=None) -> tuple[bytes, str, str]:
    """Edit a PNG; returns (image bytes, model, quality-or-provider)."""
    model, quality = describe()
    if provider() == "gemini":
        return _gemini(png, prompt, size, model), model, quality
    if client is None:
        from strike.core import OpenAIClient
        client = OpenAIClient()
    body = client._post("/images/edits", files={"image": ("image.png", png, "image/png")},
                        data={"model": model, "prompt": prompt, "size": size, "quality": quality, "n": "1"},
                        timeout=300)
    try:
        return base64.b64decode(body["data"][0]["b64_json"]), model, quality
    except (KeyError, IndexError, TypeError, ValueError):
        raise ImageEditError("The image model returned no image") from None
