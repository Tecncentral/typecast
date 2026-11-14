"""Run and optionally record the real local judging path, without replaying results.

Requires cache/browser-venv's Playwright and an already-running LIVE server. Each
invocation spends one Warehouse scout and one refinement, then one production
plan. It never generates dressing, calls World Labs, approves an owner note, or
publishes media. Reports, screenshots and video contain private licensed imagery.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
HONESTY = "AI-imagined set dressing, not the real room"
REFINEMENT = "Need parking for 5 trucks."
CARD = "#results .pick-card"

# Observe actual browser events. Do not replace requests, synthesize progress or
# dispatch application events. State survives only until the Director navigation.
OBSERVE = r"""(() => {
  const s = window.__judgeCheck = {results: [], events: [], errors: [], descents: []};
  const NativeEventSource = window.EventSource;
  window.EventSource = class extends NativeEventSource {
    constructor(...args) {
      super(...args);
      for (const [kind, key] of [['agent','events'],['result','results'],['error','errors']]) {
        this.addEventListener(kind, event => {
          if (!event.data) return;
          try { s[key].push(JSON.parse(event.data)); }
          catch { s.errors.push({message:'Invalid event JSON'}); }
        });
      }
    }
  };
  document.addEventListener('typecast:descent', event => {
    const stage = document.querySelector('.descent-stage');
    s.descents.push({...event.detail, at:performance.now(),
      source:stage?.querySelector('.descent-source')?.textContent || '',
      note:stage?.querySelector('.descent-note')?.textContent || ''});
  });
})();"""


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def local_base(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in
            {"localhost", "127.0.0.1", "::1"} or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        raise argparse.ArgumentTypeError("Use a local server origin without credentials or a path")
    return value.rstrip("/")


def private_path(path):
    require(path.resolve().is_relative_to((ROOT / "cache").resolve()),
            "Evidence must remain under ignored cache/")
    return path


def grouping(plan, scene_count):
    assignments = plan.get("assignments") or []
    identities = {assignment.get("property_id") for assignment in assignments}
    return (3 <= scene_count <= 4 and len(assignments) == scene_count
            and len({a.get("scene_id") for a in assignments}) == scene_count
            and not plan.get("uncovered_scene_ids") and len(identities) == 1
            and None not in identities and plan.get("locations") == 1
            and plan.get("company_moves") == 0)


def optional_absence(url, status):
    # The UI probes for a precomputed dressing; a 404 is the explicit optional
    # absence contract. All other console errors and failed assets still fail.
    return status == 404 and re.fullmatch(r"/api/dressed/[^/]+", urlsplit(url).path) is not None


def map_tile_cancelled(url, failure):
    # Leaflet cancels obsolete tiles during flyTo. Required DOM images are still
    # decoded below, so a cancelled image that remains on screen cannot pass.
    return (urlsplit(url).hostname in {"tile.openstreetmap.org", "a.tile.openstreetmap.org",
                                      "b.tile.openstreetmap.org", "c.tile.openstreetmap.org"}
            and failure == "net::ERR_ABORTED")


def dressing_urls(data):
    faces = data.get("faces") if isinstance(data, dict) else None
    require(isinstance(faces, list) and faces and all(
        isinstance(face, dict) and isinstance(face.get("dressed_url"), str) and face["dressed_url"]
        for face in faces), "Dressing lookup succeeded without usable offered frames")
    return [face["dressed_url"] for face in faces]


def recording_saved(path, report):
    return not report.get("cleanup_error") and path.is_file() and path.stat().st_size > 0


def check_images(page, timeout_ms=15000):
    failures = page.evaluate("""async timeout => {
      const images = [...document.images].filter(i => i.getAttribute('src'));
      const checks = await Promise.all(images.map(async i => {
        // A hidden lazy image's decode promise need not settle until it nears
        // the viewport. Load its real URL eagerly and keep the wait bounded.
        i.loading = 'eager';
        let timer;
        try {
          await Promise.race([i.decode(), new Promise((_, reject) => {
            timer = setTimeout(() => reject(new Error('Image readiness timeout')), timeout);
          })]);
          return i.naturalWidth > 0 && i.naturalHeight > 0 ? null : i.src;
        } catch { return i.src; }
        finally { clearTimeout(timer); }
      }));
      return checks.filter(Boolean).map(src => src.startsWith('data:') ? 'data image' : new URL(src).pathname);
    }""", timeout_ms)
    require(not failures, f"Missing or undecodable page images: {failures}")
    return len(page.locator("img[src]").all())


def decode_urls(page, urls, timeout_ms=15000):
    return page.evaluate("""async ([urls, timeout]) => Promise.all(urls.map(async url => {
      const image = new Image(); image.src=url;
      let timer;
      try {
        await Promise.race([image.decode(), new Promise((_, reject) => {
          timer = setTimeout(() => reject(new Error('Image readiness timeout')), timeout);
        })]);
        return image.naturalWidth > 0 && image.naturalHeight > 0;
      } catch { return false; }
      finally { clearTimeout(timer); }
    }))""", [urls, timeout_ms])


def run(args, report, output, video_path):
    from playwright.sync_api import sync_playwright

    def step(name, **details):
        report["checks"].append({"name": name, "passed": True, **details})
        print(f"PASS {name}", flush=True)

    def pause(page, seconds=1.8):
        page.wait_for_timeout(int(seconds * 1000 if args.record else 250))

    def screenshot(page, name):
        page.screenshot(path=str(output / f"{name}.png"))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.executable, headless=not args.headed)
        report["chromium_version"] = browser.version
        options = {"viewport": {"width": 1440, "height": 900}, "reduced_motion": "no-preference"}
        if args.record:
            options.update(record_video_dir=str(output / "video-temporary"),
                           record_video_size={"width": 1440, "height": 900})
        context = browser.new_context(**options)
        page = context.new_page()
        video = page.video
        page.set_default_timeout(args.timeout * 1000)
        page.add_init_script(OBSERVE)
        optional_urls = set()
        dressed_responses = []
        console_errors = []
        image_errors = []
        cancelled_tiles = []

        def response_seen(response):
            if urlsplit(response.url).path.startswith("/api/dressed/"):
                dressed_responses.append(response)
            if optional_absence(response.url, response.status):
                optional_urls.add(response.url)
                report["optional_dressing_probes"].append({"status": 404, "result": "not offered"})
            if response.request.resource_type == "image" and response.status >= 400:
                image_errors.append({"url": response.url, "status": response.status})

        page.on("response", response_seen)
        page.on("console", lambda message: console_errors.append(
            {"text": message.text, "url": message.location.get("url", "")})
            if message.type == "error" else None)
        page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        def image_failed(request):
            if request.resource_type == "image":
                target = cancelled_tiles if map_tile_cancelled(request.url, request.failure) else image_errors
                target.append({"url": request.url, "error": request.failure})

        page.on("requestfailed", image_failed)

        try:
            config_response = context.request.get(args.base_url + "/config")
            require(config_response.ok, "Stage /config failed")
            config = config_response.json()
            report["config"] = {key: config.get(key) for key in ("mode", "engine", "tracing")}
            require(config.get("mode") == "live", "Judge path requires explicitly LIVE data")
            require(config.get("engine") == "deep", "Judge path requires the selected deep stage engine")
            step("Stage configuration is LIVE deep")
            page.goto(args.base_url + "/app/", wait_until="domcontentloaded")
            warehouse = page.get_by_role("button", name="Warehouse handoff", exact=True)
            warehouse.wait_for()
            page.wait_for_function("document.querySelector('#source-mode')?.textContent.toUpperCase().includes('LIVE')")
            require("LIVE" in page.locator("#source-mode").inner_text().upper(), "Missing LIVE label")
            pause(page)
            began = time.monotonic()
            # Presets start scouting themselves; clicking Run as well would
            # spend a second request once the first request finishes.
            warehouse.click()
            print("Running one Warehouse scout", flush=True)
            page.wait_for_function("window.__judgeCheck.results.length > 0", timeout=args.timeout * 1000)
            result = page.evaluate("window.__judgeCheck.results.at(-1)")
            report["scout"] = {"seconds": round(time.monotonic() - began, 3),
                               "engine": result.get("engine"), "trace_url": result.get("trace_url"),
                               "thread_id": result.get("thread_id"), "picks": len(result.get("picks", [])),
                               "events": page.evaluate("window.__judgeCheck.events")}
            require(result.get("source_mode") == "live", "Scout silently changed source mode")
            require(result.get("picks"), "Warehouse returned no result cards")
            page.wait_for_function("n => document.querySelectorAll('#results .pick-card').length === n",
                                   arg=len(result["picks"]))
            step("Warehouse live cards", count=len(result["picks"]), engine=result.get("engine"))

            page.wait_for_function("window.__judgeCheck.descents.some(e => e.phase === 'finish')")
            descent = page.evaluate("window.__judgeCheck.descents")
            report["descent"] = descent
            require(descent[-1].get("outcome") == "complete", "Automatic descent did not complete")
            require(any(e["phase"] == "interior" and "Matterport scan" in e["source"] for e in descent),
                    "Descent lacks its real scan honesty label")
            if result["picks"][0].get("logistics", {}).get("aerial_image_path"):
                require(any(e["phase"] == "aerial" and "Vexcel aerial" in e["source"]
                            and "Parking " in e["note"] for e in descent), "Missing aerial or parking status label")
            require(page.evaluate("document.activeElement === document.querySelector('#results .pick-card')"),
                    "Descent did not land on the first card")
            screenshot(page, "01-shortlist")
            step("Inside-out descent and source labels")
            pause(page)
            page.get_by_role("button", name="Replay descent", exact=True).click()
            page.get_by_role("button", name="Skip descent", exact=True).click()
            page.locator(".descent-stage").wait_for(state="detached")
            require(page.evaluate("window.__judgeCheck.descents.at(-1).outcome") == "skipped",
                    "Skip did not cancel the actual descent")
            require(page.evaluate("document.activeElement === document.querySelector('#results .pick-card')"),
                    "Skip did not return focus to the first card")
            step("Skip lands on card one")

            first = page.locator(CARD).first
            first.locator(".vf-open").click()
            page.locator("dialog.vf[open].is-live").wait_for()
            require(page.locator("dialog.vf.no-webgl").count() == 0, "360 viewfinder fell back to a flat image")
            page.locator('.vf-lenses [data-lens="24"]').click()
            pause(page)
            page.keyboard.press("ArrowRight")
            page.locator('.vf-lenses [data-lens="50"]').click()
            pause(page)
            require(page.locator('.vf-lenses [data-lens="50"]').get_attribute("aria-pressed") == "true",
                    "50 mm lens control did not engage")
            screenshot(page, "02-viewfinder")
            step("360 viewfinder and 24 to 50 mm rack")

            # Give the real optional asset probe time to finish; a successful
            # response with broken assets is a failure, not 'not offered'.
            deadline = time.monotonic() + 15
            while not page.locator(".vf-dress").is_visible() and time.monotonic() < deadline:
                if optional_urls:
                    break
                page.wait_for_timeout(100)
            shot_id = result["picks"][0]["shots"][0]["shot_id"]
            probe = next((r for r in reversed(dressed_responses)
                          if unquote(urlsplit(r.url).path) == "/api/dressed/" + shot_id), None)
            require(probe is not None, "Optional dressing lookup did not finish")
            if probe.status == 200:
                dressing = probe.json()
                urls = dressing_urls(dressing)
                require(page.locator(".vf-dress").is_visible(), "Offered dressing did not finish loading")
                decoded_faces = decode_urls(page, urls)
                require(all(decoded_faces), "An offered AI dressing frame could not decode")
                page.keyboard.press("d")
                page.locator(".vf-ai-badge").wait_for(state="visible")
                require(HONESTY in page.locator(".vf-ai-badge").inner_text(), "Missing AI honesty label")
                pause(page, 2.5)
                screenshot(page, "03-ai-dressing")
                report["dressing"] = "offered and checked"
                step("AI dressing and persistent honesty label")
            else:
                require(probe.status == 404, "Dressing lookup failed; this is not optional absence")
                report["dressing"] = "not offered"
                print("AI dressing: not offered", flush=True)
            # Walk mode is informational. The judge path never generates a world
            # or enters an unverified optional immersive workflow.
            walk = page.get_by_role("button", name=re.compile(r"walk", re.I))
            report["walk_mode"] = "offered; not exercised" if any(b.is_visible() for b in walk.all()) else "not offered"
            print(f"Walk mode: {report['walk_mode']}", flush=True)
            pause(page)
            page.keyboard.press("g")
            page.locator(".vf-shot").first.wait_for()
            require(page.locator(".vf-shot-save").first.get_attribute("href").startswith("data:image/jpeg"),
                    "G did not create a real grabbed frame")
            screenshot(page, "04-grabbed-frame")
            pause(page)
            page.keyboard.press("Escape")
            page.locator("dialog.vf[open]").wait_for(state="detached")
            step("G grabs frame and Escape returns")
            step("Scout images decoded", count=check_images(page))

            page.locator("#refine-message").fill(REFINEMENT)
            pause(page)
            with page.expect_response(lambda r: urlsplit(r.url).path == "/refine" and r.request.method == "POST") as refined_response:
                page.locator("#refine-button").click()
            refined_http = refined_response.value
            require(refined_http.ok, "Five-truck refinement failed")
            refined = refined_http.json()
            sent = refined_http.request.post_data_json
            require(sent.get("thread_id") == result["thread_id"] and refined.get("thread_id") == result["thread_id"],
                    "Refinement did not preserve the original thread")
            require(sent.get("message") == REFINEMENT, "Refinement message changed")
            page.locator("#changes").wait_for(state="visible")
            page.locator("#history-section").wait_for(state="visible")
            require(refined.get("source_mode") == "live", "Refinement silently changed source mode")
            report["refine"] = {"engine": refined.get("engine"), "thread_kept": True,
                                "changes": page.locator("#changes").inner_text()}
            pause(page, 3)
            screenshot(page, "05-five-trucks")
            step("Five trucks preserves thread and earlier frames", count=check_images(page))

            page.goto(args.base_url + "/director", wait_until="domcontentloaded")
            if args.director_script_file:
                page.locator("#script").fill(args.director_script_file.read_text())
                report["director_script"] = str(args.director_script_file)
            else:
                page.locator("#demo").click()
                report["director_script"] = "served Demo script"
            pause(page)
            with page.expect_response(lambda r: urlsplit(r.url).path == "/api/production/plan" and r.request.method == "POST") as plan_response:
                page.locator("#build").click()
            plan_http = plan_response.value
            require(plan_http.ok, "Director production plan failed")
            production = plan_http.json()
            report["production"] = production
            require(production.get("plans"), "Director returned no plan")
            page.wait_for_function("document.querySelector('#planSel').options.length > 0")
            scene_count = len(production.get("scenes") or [])
            # Before stream 1's merge the served selector still sorts by raw
            # similarity. Choose its actual zero-move option through the UI.
            # After the merge that same plan is already the default.
            matches = [index for index, plan in enumerate(production["plans"]) if grouping(plan, scene_count)]
            require(matches, "Director has no 3–4 scene / one location / zero move plan")
            zero_moves = page.locator("#planSel option").filter(has_text=re.compile(r"\b0 moves\b")).first
            require(zero_moves.count() > 0, "Director selector does not expose its zero-move plan")
            chosen_value = zero_moves.get_attribute("value")
            report["director_plan_selection_changed"] = page.locator("#planSel").input_value() != chosen_value
            page.locator("#planSel").select_option(chosen_value)
            # Read, never modify, the selected application plan. The new UI sorts
            # plans and displays 'Location A' instead of private property IDs.
            selected = page.evaluate("S.resp.plans[S.planIdx]")
            identity = lambda p: sorted((a["scene_id"], a["property_id"], a["shot_id"])
                                        for a in p.get("assignments", []))
            require(any(identity(selected) == identity(production["plans"][i]) for i in matches),
                    "Selected assignments disagree with the zero-move response plan")
            require(page.locator("#rail button[data-sid]").count() == scene_count,
                    "Director did not render every scene")
            require(grouping(selected, scene_count), "Director winner is not 3–4 covered scenes / one location / zero moves")
            require("Uncalibrated screen-space rehearsal" in page.locator("body").inner_text()
                    and "Geometric fit: unknown" in page.locator("body").inner_text(), "Missing Director geometry honesty label")
            decoded = decode_urls(page, [args.base_url + "/image/" + a["shot_id"] for a in selected["assignments"]])
            require(all(decoded), "An assigned Director frame is missing")
            screenshot(page, "06-director-plan")
            pause(page, 3)
            page.locator("#play").click()
            page.wait_for_function("Number(document.querySelector('#prog').value) > 0")
            pause(page, 5)
            screenshot(page, "07-director-play")
            page.locator("#pause").click()
            step("Director groups every scene and plays", scenes=scene_count, locations=1, moves=0)
        finally:
            report["console_errors"] = [error for error in console_errors if not (
                error["url"] in optional_urls and "404" in error["text"])]
            report["optional_console_errors"] = [error for error in console_errors if error not in report["console_errors"]]
            report["image_errors"] = image_errors
            report["cancelled_map_tiles"] = cancelled_tiles
            try:
                screenshot(page, "last-state")
            except Exception:
                pass
            try:
                context.close()
                if video:
                    video.save_as(str(video_path))
                    video.delete()
                    report["video"] = str(video_path)
            except Exception as error:
                report["cleanup_error"] = f"{type(error).__name__}: {error}"
            finally:
                browser.close()
        if args.record:
            require(recording_saved(video_path, report),
                    "Requested backup recording did not save successfully")
        require(not report["page_errors"], "JavaScript exception; inspect private report")
        require(not report["console_errors"], "Console error; inspect private report")
        require(not image_errors, "Failed image request; inspect private report")
        step("No console errors, JavaScript exceptions or missing images")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", type=local_base, default="http://localhost:8000")
    parser.add_argument("--record", action="store_true", help="Record the same path at human pace, privately")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--executable", help="Existing Chromium executable; otherwise Playwright default")
    parser.add_argument("--director-script-file", type=Path, help="Stream 1's authored script before its PR merges")
    parser.add_argument("--timeout", type=int, default=180, help="Maximum seconds for an individual live step")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = private_path(ROOT / "cache/demo-checks/judge-path" / stamp)
    video_path = private_path(ROOT / "cache/demo-video" / f"{stamp}.webm")
    output.mkdir(parents=True, exist_ok=False)
    if args.record:
        video_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"passed": False, "started_at": stamp, "base_url": args.base_url,
              "playwright_version": importlib.metadata.version("playwright"), "record": args.record,
              "checks": [], "page_errors": [], "optional_dressing_probes": [],
              "evidence": "Recorded live run; private licensed imagery; human approval required before publishing"}
    try:
        run(args, report, output, video_path)
        report["passed"] = True
    except KeyboardInterrupt:
        report["error"] = "Interrupted by operator; this is not an accepted backup"
        print("INTERRUPTED; partial evidence is private and not an accepted backup", file=sys.stderr)
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        # Playwright exceptions can include private DOM text. Keep them in cache.
        print(f"FAIL {type(error).__name__}; details retained in the private report", file=sys.stderr)
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Report: {output / 'report.json'}")
        if report.get("video"):
            print(f"Private video: {report['video']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
