import numpy as np

from strike import seams


def _view(step: float = 0.0) -> np.ndarray:
    h, w = 400, 600
    x = np.linspace(0, 120, w, dtype=np.float32)
    rng = np.random.default_rng(3)
    img = np.repeat((x[None, :] + rng.normal(0, 4, (h, w))).astype(np.float32)[..., None], 3, axis=2)
    img[:, w // 2:] += step
    return img


def test_seam_step_is_about_one_without_a_seam_and_large_with_one():
    assert seams.seam_step(_view()) < 1.3
    assert seams.seam_step(_view(step=60.0)) > 3.0


def test_min_cut_follows_the_lowest_error_column():
    err = np.full((50, 20), 10.0)
    err[:25, 4] = 0.0
    err[25:, 6] = 0.0
    path = seams.min_cut(err)
    assert list(path[:23]) == [4] * 23 and list(path[27:]) == [6] * 23
    assert np.all(np.abs(np.diff(path)) <= 1)


def test_repaint_is_used_inside_the_strip_and_the_original_outside():
    rng = np.random.default_rng(1)
    view = rng.uniform(0, 255, (seams.VIEW_H, seams.VIEW_W, 3)).astype(np.float32)
    out = view.copy()
    edit = seams._edit_mask(45.0)
    out[edit] = 255 - out[edit]  # the model changed only its strip
    weight, error, worst = seams.cut_weight(view, out, 45.0)
    middle = seams.VIEW_W // 2
    assert weight[:, middle].min() == 1.0
    assert weight[:, 0].max() == 0.0 and weight[:, -1].max() == 0.0
    # Where the copies agree (just outside the strip) the cut costs almost nothing.
    assert error < 40 and worst >= error
