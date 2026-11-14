"""Guard the browser check's privacy boundary and grouping assertions."""
import argparse
from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import time

import pytest

SPEC = importlib.util.spec_from_file_location("check_judge_path", Path(__file__).with_name("check_judge_path.py"))
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


@pytest.mark.parametrize("value", ["http://localhost:8000", "http://127.0.0.1:8000/", "http://[::1]:8000"])
def test_local_origin_allowed(value):
    assert CHECK.local_base(value) == value.rstrip("/")


@pytest.mark.parametrize("value", ["https://example.org", "http://localhost.example.org", "file:///tmp/app",
                                  "http://user:secret@localhost", "http://localhost/app", "http://localhost?key=secret"])
def test_remote_or_credentialled_origin_rejected(value):
    with pytest.raises(argparse.ArgumentTypeError):
        CHECK.local_base(value)


def test_private_evidence_cannot_escape_cache_through_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr(CHECK, "ROOT", tmp_path)
    (tmp_path / "cache").mkdir()
    outside = tmp_path / "public"
    outside.mkdir()
    (tmp_path / "cache/escape").symlink_to(outside, target_is_directory=True)
    assert CHECK.private_path(tmp_path / "cache/screens/real.png")
    with pytest.raises(AssertionError):
        CHECK.private_path(tmp_path / "cache/escape/real.png")


def test_optional_absence_does_not_hide_broken_dressing_assets_or_other_errors():
    assert CHECK.optional_absence("http://localhost:8000/api/dressed/fixture-shot", 404)
    assert not CHECK.optional_absence("http://localhost:8000/api/dressed/fixture-shot", 500)
    assert not CHECK.optional_absence("http://localhost:8000/cache/worlds/fixture.jpg", 404)
    assert not CHECK.optional_absence("http://localhost:8000/api/sweep/fixture-shot", 404)


def test_only_cancelled_map_tiles_are_classified_as_motion_cleanup():
    assert CHECK.map_tile_cancelled("https://tile.openstreetmap.org/12/1/2.png", "net::ERR_ABORTED")
    assert not CHECK.map_tile_cancelled("https://tile.openstreetmap.org/12/1/2.png", "net::ERR_FAILED")
    assert not CHECK.map_tile_cancelled("http://localhost:8000/cache/views/fixture.jpg", "net::ERR_ABORTED")


@pytest.mark.parametrize("data", [None, [], {}, {"faces": []}, {"faces": [None]}, {"faces": [{}]},
                                 {"faces": [{"dressed_url": ""}]}, {"faces": [{"dressed_url": 1}]}])
def test_successful_but_malformed_dressing_is_not_optional_absence(data):
    with pytest.raises(AssertionError):
        CHECK.dressing_urls(data)


def test_recording_requires_a_nonempty_file_without_cleanup_errors(tmp_path):
    path = tmp_path / "recording.webm"
    assert not CHECK.recording_saved(path, {})
    path.touch()
    assert not CHECK.recording_saved(path, {})
    path.write_bytes(b"fixture-video")
    assert CHECK.recording_saved(path, {})
    assert not CHECK.recording_saved(path, {"cleanup_error": "encoder failed"})


def test_director_honesty_respects_rendered_uppercase_but_requires_both_caveats():
    assert CHECK.director_honesty("UNCALIBRATED SCREEN-SPACE REHEARSAL\nGEOMETRIC FIT: UNKNOWN")
    assert CHECK.director_honesty("Uncalibrated screen-space rehearsal Geometric fit: unknown")
    assert not CHECK.director_honesty("Uncalibrated screen-space rehearsal")
    assert not CHECK.director_honesty("Geometric fit: verified")


def test_grouping_rejects_partial_duplicate_and_false_count_plans():
    plan = {"locations": 1, "company_moves": 0, "uncovered_scene_ids": [],
            "assignments": [{"scene_id": f"s{i}", "property_id": "fixture-one"} for i in range(3)]}
    assert CHECK.grouping(plan, 3)
    assert not CHECK.grouping(plan, 4)
    for key, value in [("locations", 2), ("company_moves", 1), ("uncovered_scene_ids", ["s2"])]:
        changed = {**plan, key: value}
        assert not CHECK.grouping(changed, 3)
    split = deepcopy(plan)
    split["assignments"][2]["property_id"] = "fixture-two"
    assert not CHECK.grouping(split, 3)
    duplicate = deepcopy(plan)
    duplicate["assignments"][2]["scene_id"] = "s0"
    assert not CHECK.grouping(duplicate, 3)


@pytest.mark.skipif(os.environ.get("TYPECAST_CHECK_BROWSER") != "1", reason="Opt-in isolated Chromium regression")
def test_lazy_corrupt_and_pending_images_in_browser():
    from playwright.sync_api import sync_playwright

    fixture = (Path(__file__).resolve().parents[1] / "mocks/img/mock-p2-s1.jpg").read_bytes()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("TYPECAST_BROWSER_EXECUTABLE"))
        page = browser.new_page()
        page.route("https://fixture.invalid/good.jpg", lambda r: r.fulfill(content_type="image/jpeg", body=fixture))
        page.route("https://fixture.invalid/bad.jpg", lambda r: r.fulfill(content_type="image/jpeg", body=b"corrupt"))
        page.route("https://fixture.invalid/pending.jpg", lambda r: None)
        try:
            page.set_content('<img loading="lazy" style="margin-top:100000px" src="https://fixture.invalid/good.jpg">',
                             wait_until="domcontentloaded")
            assert CHECK.check_images(page, 2000) == 1
            page.set_content('<img src="https://fixture.invalid/bad.jpg">', wait_until="domcontentloaded")
            with pytest.raises(AssertionError):
                CHECK.check_images(page, 2000)
            page.set_content('<img src="https://fixture.invalid/pending.jpg">', wait_until="domcontentloaded")
            started = time.monotonic()
            with pytest.raises(AssertionError):
                CHECK.check_images(page, 250)
            assert time.monotonic() - started < 2
            assert CHECK.decode_urls(page, ["https://fixture.invalid/good.jpg", "https://fixture.invalid/bad.jpg"], 2000) == [True, False]
        finally:
            browser.close()
