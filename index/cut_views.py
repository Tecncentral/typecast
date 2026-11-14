"""Cut flat camera views out of a 360-degree (equirectangular) panorama."""
import numpy as np


def perspective_view(pano: np.ndarray, yaw_deg: float, fov_deg: float = 70.0,
                     out_w: int = 768, out_h: int = 512, pitch_deg: float = 0.0) -> np.ndarray:
    """pano: H x W x C equirectangular image, yaw 0 at the image centre column.
    Returns an out_h x out_w x C view looking along yaw_deg (nearest-pixel sampling)."""
    H, W = pano.shape[:2]
    f = (out_w / 2) / np.tan(np.radians(fov_deg) / 2)
    xs = np.arange(out_w) - (out_w - 1) / 2
    ys = np.arange(out_h) - (out_h - 1) / 2
    x, y = np.meshgrid(xs, ys)
    z = np.full_like(x, f, dtype=float)
    d = np.stack([x, -y, z], axis=-1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    p, yw = np.radians(pitch_deg), np.radians(yaw_deg)
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    ry = np.array([[np.cos(yw), 0, np.sin(yw)], [0, 1, 0], [-np.sin(yw), 0, np.cos(yw)]])
    d = d @ rx.T @ ry.T
    lon = np.arctan2(d[..., 0], d[..., 2])          # -pi..pi
    lat = np.arcsin(np.clip(d[..., 1], -1, 1))      # -pi/2..pi/2
    u = ((lon / (2 * np.pi) + 0.5) * W).astype(int) % W
    v = np.clip(((0.5 - lat / np.pi) * H).astype(int), 0, H - 1)
    return pano[v, u]


def cut_all(pano: np.ndarray, n: int = 8, **kw) -> list[tuple[float, np.ndarray]]:
    """n level views spaced evenly; returns (heading_deg, image) pairs."""
    return [(i * 360.0 / n, perspective_view(pano, i * 360.0 / n, **kw)) for i in range(n)]
