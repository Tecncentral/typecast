"""Cube-face panorama geometry and image registration for seam-aware dressing.

Horizon cube faces: face h covers yaw [h-45, h+45] left to right (the right edge of face h meets the left
edge of face h+90, checked on real scans), pitch +-45 at its centre. A face pixel (u, v) in [0, 1] has
x = 2u-1, y = 1-2v, yaw = h + atan(x), pitch = atan2(y, sqrt(1+x^2)). A perspective view with centre c and
half-tangents (th, tv) uses the same mapping with x, y scaled by th, tv.

Following the defurnishing paper's lesson that context matters, faces are dressed through wide (120 deg)
views so every wall sees its neighbours; outputs are registered back to their inputs with FFT phase
correlation before only the wall's own region is composited.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def _sample(img: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
    """Bilinear sample img (H, W, 3) at float pixel coords."""
    h, w = img.shape[:2]
    x0 = np.clip(np.floor(px).astype(np.int64), 0, w - 1)
    y0 = np.clip(np.floor(py).astype(np.int64), 0, h - 1)
    x1, y1 = np.clip(x0 + 1, 0, w - 1), np.clip(y0 + 1, 0, h - 1)
    fx, fy = (px - x0)[..., None], (py - y0)[..., None]
    top = img[y0, x0] * (1 - fx) + img[y0, x1] * fx
    bot = img[y1, x0] * (1 - fx) + img[y1, x1] * fx
    return top * (1 - fy) + bot * fy


def view_directions(center: float, hfov: float, w: int, h: int):
    th = math.tan(math.radians(hfov / 2))
    tv = th * h / w
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    x = (2 * u[None, :] - 1) * th
    y = (1 - 2 * v[:, None]) * tv
    x = np.broadcast_to(x, (h, w))
    y = np.broadcast_to(y, (h, w))
    yaw = center + np.degrees(np.arctan(x))
    pitch = np.degrees(np.arctan2(y, np.sqrt(1 + x * x)))
    return yaw, pitch


def render_view(faces: dict[int, np.ndarray], center: float, hfov: float, w: int, h: int):
    """Perspective view from horizon faces. Returns (image float32 HxWx3, valid bool HxW)."""
    yaw, pitch = view_directions(center, hfov, w, h)
    out = np.zeros((h, w, 3), np.float32)
    valid = np.zeros((h, w), bool)
    for heading, face in faces.items():
        a = _wrap(yaw - heading)
        inside = np.abs(a) <= 45.0001
        x = np.tan(np.radians(np.where(inside, a, 0)))
        y = np.tan(np.radians(pitch)) * np.sqrt(1 + x * x)
        ok = inside & (np.abs(y) <= 1)
        fs = face.shape[0]
        px = (x + 1) / 2 * fs - 0.5
        py = (1 - y) / 2 * fs - 0.5
        sel = ok & ~valid
        if sel.any():
            out[sel] = _sample(face, px[sel], py[sel])
            valid |= sel
    return out, valid


def fill_invalid(img: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Extend valid pixels vertically into the missing floor/ceiling bands so the model sees no black."""
    out = img.copy()
    h = img.shape[0]
    for col in range(img.shape[1]):
        ok = np.nonzero(valid[:, col])[0]
        if ok.size == 0:
            continue
        top, bot = ok[0], ok[-1]
        out[:top, col] = img[top, col]
        out[bot + 1:, col] = img[bot, col]
    return out


def view_to_face(view: np.ndarray, center: float, hfov: float, heading: int, size: int):
    """Resample a view back into face `heading`. Returns (face float32, covered bool)."""
    vh, vw = view.shape[:2]
    th = math.tan(math.radians(hfov / 2))
    tv = th * vh / vw
    u = (np.arange(size) + 0.5) / size
    x = np.broadcast_to(2 * u[None, :] - 1, (size, size))
    y = np.broadcast_to(1 - 2 * u[:, None], (size, size))
    yaw = heading + np.degrees(np.arctan(x))
    pitch = np.degrees(np.arctan2(y, np.sqrt(1 + x * x)))
    a = _wrap(yaw - center)
    xv = np.tan(np.radians(a)) / th
    yv = np.tan(np.radians(pitch)) * np.sqrt(1 + np.tan(np.radians(a)) ** 2) / tv
    covered = (np.abs(a) < 89) & (np.abs(xv) <= 1) & (np.abs(yv) <= 1)
    px = (xv + 1) / 2 * vw - 0.5
    py = (1 - yv) / 2 * vh - 0.5
    face = np.zeros((size, size, 3), np.float32)
    face[covered] = _sample(view, px[covered], py[covered])
    return face, covered


def band_mask(center: float, hfov: float, w: int, h: int, inner_half: float) -> np.ndarray:
    """True where the view's yaw is outside +-inner_half of its centre (the context bands)."""
    yaw, _ = view_directions(center, hfov, w, h)
    return np.abs(_wrap(yaw - center)) > inner_half


# ---------------------------------------------------------------- registration
def _edges(img: np.ndarray, size: int) -> np.ndarray:
    g = np.asarray(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("L").resize(
        (size, int(size * img.shape[0] / img.shape[1])), Image.BILINEAR), np.float32)
    gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
    gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    e = gx + gy
    return (e - e.mean()) / (e.std() + 1e-6)


def _phase_shift(a: np.ndarray, b: np.ndarray, weight: np.ndarray):
    win = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1])) * weight
    fa, fb = np.fft.fft2(a * win), np.fft.fft2(b * win)
    r = fa * np.conj(fb)
    r /= np.abs(r) + 1e-9
    corr = np.fft.ifft2(r).real
    iy, ix = np.unravel_index(np.argmax(corr), corr.shape)
    peak = corr[iy, ix] / (np.abs(corr).mean() + 1e-9)
    dy = iy if iy <= a.shape[0] // 2 else iy - a.shape[0]
    dx = ix if ix <= a.shape[1] // 2 else ix - a.shape[1]
    return float(dx), float(dy), float(peak)


def _scale_about_center(img: np.ndarray, s: float, dx: float = 0.0, dy: float = 0.0) -> np.ndarray:
    h, w = img.shape[:2]
    pil = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    # PIL affine maps output -> input: x_in = (x_out - cx - dx) / s + cx
    cx, cy = w / 2, h / 2
    coeffs = (1 / s, 0, cx - (cx + dx) / s, 0, 1 / s, cy - (cy + dy) / s)
    return np.asarray(pil.transform((w, h), Image.AFFINE, coeffs, resample=Image.BICUBIC), np.float32)


def register(reference: np.ndarray, moving: np.ndarray, weight: np.ndarray | None = None,
             scales=(0.97, 0.985, 1.0, 1.015, 1.03), max_shift=0.06):
    """Align `moving` to `reference` (same size): returns (aligned, info). Weighted toward `weight` regions."""
    h, w = reference.shape[:2]
    size = 640
    ref = _edges(reference, size)
    wmask = np.ones_like(ref)
    if weight is not None:
        wmask = np.asarray(Image.fromarray((weight * 255).astype(np.uint8)).resize(ref.shape[::-1], Image.BILINEAR),
                           np.float32) / 255.0 + 0.05
    best = None
    for s in scales:
        cand = _scale_about_center(moving, s) if s != 1.0 else moving
        dx, dy, peak = _phase_shift(ref, _edges(cand, size), wmask)
        if best is None or peak > best[3]:
            best = (s, dx, dy, peak)
    s, dx, dy, peak = best
    k = w / size
    dxp, dyp = dx * k, dy * k
    if abs(dxp) > max_shift * w or abs(dyp) > max_shift * h:
        return moving, {"applied": False, "scale": s, "dx": round(dxp, 1), "dy": round(dyp, 1), "peak": round(peak, 1)}
    aligned = _scale_about_center(moving, s, dxp, dyp)
    return aligned, {"applied": True, "scale": s, "dx": round(dxp, 1), "dy": round(dyp, 1), "peak": round(peak, 1)}
