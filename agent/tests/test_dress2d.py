"""Image-model dressing: prompts, refusal to touch Atlas walk sets, the gate and the viewer record format."""
import json

import numpy as np
from PIL import Image

from strike import dress
from strike import core


class _Client:
    def __init__(self, kept=(0.9,), fits=(0.9,)):
        self.kept, self.fits, self.edits = list(kept), list(fits), 0

    def predicates(self, images, questions):
        return [self.kept.pop(0) if len(self.kept) > 1 else self.kept[0], self.fits.pop(0) if len(self.fits) > 1 else self.fits[0]]


def _img():
    return Image.fromarray((np.random.default_rng(0).random((64, 64, 3)) * 255).astype(np.uint8))


def test_prompt_keeps_architecture_and_drops_logistics():
    p = dress.prompt_for("INT. WAREHOUSE - DAY. Two couriers meet. Parking for 2 trucks and 10 crew cars.", "pallets")
    assert "Parking" not in p and "pallets" in p and "No people" in p and "Keep the architecture" in p


def test_gate_retries_once_then_rejects(monkeypatch):
    monkeypatch.setattr(dress, "edit", lambda client, image, prompt: _img())
    ok = dress.dress_face(_Client(), _img(), _img(), "INT. ROOM - DAY. Talk.", "p")
    assert ok["status"] == "dressed" and ok["attempts"] == 1 and ok["image"] is not None
    retry = dress.dress_face(_Client(kept=(0.2, 0.9)), _img(), _img(), "INT. ROOM - DAY. Talk.", "p")
    assert retry["status"] == "dressed" and retry["attempts"] == 2
    bad = dress.dress_face(_Client(kept=(0.1,)), _img(), _img(), "INT. ROOM - DAY. Talk.", "p")
    assert bad["status"] == "rejected" and bad["image"] is None


def test_refuses_scan_points_with_an_atlas_walk(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPECAST_WORLDS_DIR", str(tmp_path))
    d = tmp_path / "m1" / "s1" / "dressed"
    d.mkdir(parents=True)
    (d / "dressed.json").write_text(json.dumps({"model_id": "m1", "sweep_id": "s1", "splat": {"file": "a.spz"}}))
    try:
        dress.dress_scan_point({"model_id": "m1", "sweep_id": "s1", "scene_id": "la-warehouse-handoff", "scene": "x"}, _Client())
    except core.StrikeError as error:
        assert "walkable" in str(error)
    else:
        raise AssertionError("an Atlas walk set must never be replaced")
