"""Check the real inside-out descent against a separately running local server.

Live scenes call the actual scouting API. Additional controls replay those exact
responses through a labelled browser route; they do not run the scouting engine.
Licensed responses, screenshots and reports remain in ignored private cache/.
No server is started/stopped and no owner draft or contact request is made.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import importlib.metadata
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from check_viewer import (CARD, OBSERVE_STREAM, assert_activity, assert_no_contacts,
                          assert_no_overflow, controlled_stream, path_only, require)

ROOT = Path(__file__).resolve().parents[2]
VIEWPORTS = [(1440, 900), (1280, 720)]

# Observe UI lifecycle, decoded assets, actual animation arguments, and visible
# RAF cadence. These records never dispatch application lifecycle/progress events.
OBSERVE_DESCENT = r"""(() => {
  const state = window.__descentCheck = {
    runs: [], longtasks: [], animations: [], flyCalls: [], transitions: 0,
    active: null, lastFrame: null, lastSample: 0,
  };
  const rect = node => {
    const r = node.getBoundingClientRect();
    return {x:r.x, y:r.y, width:r.width, height:r.height};
  };
  const snapshot = () => {
    const stage = document.querySelector('.descent-stage');
    if (!stage) return {stage:false};
    return {
      stage:true, phase:stage.dataset.phase, bounds:rect(stage),
      source:stage.querySelector('.descent-source')?.textContent || '',
      note:stage.querySelector('.descent-note')?.textContent || '',
      outline:stage.querySelector('.descent-parking')?.getAttribute('d') || null,
      mapTransform:stage.querySelector('.leaflet-map-pane')?.style.transform || '',
      markers:[...stage.querySelectorAll('.leaflet-marker-icon')].map(n => Number(getComputedStyle(n).opacity)),
      images:[...stage.querySelectorAll('img')].filter(n => !n.closest('.leaflet-tile-pane')).map(n => ({
        path:n.currentSrc ? new URL(n.currentSrc).pathname : '',
        decoded:n.complete && n.naturalWidth > 0 && n.naturalHeight > 0,
        layer:n.closest('.descent-aerial') ? 'aerial' : n.closest('.descent-interior') ? 'interior' : 'map',
        opacity:Number(getComputedStyle(n.closest('.descent-layer') || n).opacity),
        transform:getComputedStyle(n).transform,
      })),
    };
  };
  document.addEventListener('typecast:descent', event => {
    const now = performance.now();
    if (!state.active) {
      const run = {start:now, events:[], frames:[], samples:[], animationStart:state.animations.length,
                   flyStart:state.flyCalls.length, transitionStart:state.transitions};
      state.runs.push(run); state.active = run; state.lastFrame = null; state.lastSample = 0;
    }
    const run = state.active;
    run.events.push({...event.detail, at:now, visible:!document.hidden, dom:snapshot()});
    if (event.detail.phase === 'finish') {
      run.end = now; run.animationEnd = state.animations.length;
      run.flyEnd = state.flyCalls.length; run.transitionEnd = state.transitions;
      state.active = null; state.lastFrame = null;
    }
  });
  function frame(now) {
    const run = state.active;
    if (run && !document.hidden) {
      if (state.lastFrame !== null) run.frames.push(now - state.lastFrame);
      state.lastFrame = now;
      if (now - state.lastSample > 100) {
        run.samples.push({at:now, ...snapshot()}); state.lastSample = now;
      }
    } else state.lastFrame = null;
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  try { new PerformanceObserver(list => {
    for (const entry of list.getEntries()) state.longtasks.push({start:entry.startTime, duration:entry.duration});
  }).observe({type:'longtask', buffered:true}); } catch {}
  const animate = Element.prototype.animate;
  Element.prototype.animate = function(frames, options) {
    state.animations.push({at:performance.now(), target:this.className?.baseVal ?? this.className,
                           frames, options});
    return animate.call(this, frames, options);
  };
  if (typeof document.startViewTransition === 'function') {
    const transition = document.startViewTransition.bind(document);
    document.startViewTransition = (...args) => {state.transitions++; return transition(...args);};
  }
})();"""


def save_report(args, report):
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "descent-report.json").write_text(json.dumps(report, indent=2) + "\n")


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    return round(values[low] + (values[high] - values[low]) * (position - low), 3)


def telemetry(page, index=-1):
    return page.evaluate("""index => {
      const s = window.__descentCheck, r = s.runs.at(index);
      if (!r) return null;
      return {...r, animations:s.animations.slice(r.animationStart,r.animationEnd),
        flyCalls:s.flyCalls.slice(r.flyStart,r.flyEnd),
        viewTransitions:r.transitionEnd-r.transitionStart,
        longtasks:s.longtasks.filter(t => t.start >= r.start && t.start <= r.end)};
    }""", index)


def open_page(browser, args, row, *, result=None, reduced=False, no_transition=False,
              metadata_failure=False, metadata_corrupt=False, image_failure=False):
    context = browser.new_context(viewport={"width": row["viewport"][0], "height": row["viewport"][1]},
                                  reduced_motion="reduce" if reduced else "no-preference")
    page = context.new_page()
    page.set_default_timeout(60000)
    page.add_init_script(OBSERVE_STREAM)
    page.add_init_script(OBSERVE_DESCENT)
    if no_transition:
        page.add_init_script("Object.defineProperty(document,'startViewTransition',{value:undefined,configurable:true})")
    row.update(console_errors=[], expected_resource_errors=[], page_errors=[], approve_requests=0)

    def console(message):
        if message.type != "error":
            return
        url = message.location.get("url", "")
        path = path_only(url)
        expected = (urlsplit(url).hostname in {"tile.openstreetmap.org", "a.tile.openstreetmap.org",
                    "b.tile.openstreetmap.org", "c.tile.openstreetmap.org"}
                    or metadata_failure and path.startswith("/api/aerial/")
                    or image_failure and (path.startswith("/cache/vexcel/") or path.startswith("/mocks/")))
        row["expected_resource_errors" if expected else "console_errors"].append({"text":message.text, "url":url})

    page.on("console", console)
    page.on("pageerror", lambda error: row["page_errors"].append(str(error)))
    page.on("request", lambda request: row.update(approve_requests=row["approve_requests"] + 1)
            if path_only(request.url) == "/approve" else None)
    if result is not None:
        page.route("**/scout/stream?**", lambda route: route.fulfill(
            content_type="text/event-stream", body=controlled_stream(result)))
    if metadata_failure:
        page.route("**/api/aerial/*", lambda route: route.fulfill(status=404, json={"detail":"Controlled missing extent"}))
    if metadata_corrupt:
        def corrupt(route):
            response = route.fetch()
            if response.ok:
                body = response.json()
                body["coordinates"] = [0, 0]
                route.fulfill(response=response, json=body)
            else:
                route.fulfill(response=response)
        page.route("**/api/aerial/*", corrupt)
    if image_failure:
        page.route("**/cache/vexcel/**", lambda route: route.abort("failed"))
    page.goto(args.base_url + "/app/", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('#scene-buttons button').length === 5")
    page.evaluate("""async () => {
      const {Map} = await import('/app/vendor/leaflet/leaflet-src.esm.js');
      const fly = Map.prototype.flyTo;
      Map.prototype.flyTo = function(...args) {
        window.__descentCheck.flyCalls.push({at:performance.now(), point:args[0], zoom:args[1], options:args[2]});
        return fly.apply(this,args);
      };
    }""")
    return context, page


def start_scout(page, scene):
    page.locator("#scene").fill(scene)
    page.locator("#run-button").click()
    page.wait_for_function("window.__viewerCheck.results.length > 0", timeout=180000)
    return page.evaluate("window.__viewerCheck.results.at(-1)")


def await_finish(page, count=1):
    page.wait_for_function("count => window.__descentCheck.runs.filter(r => r.end).length >= count", arg=count)
    return telemetry(page)


def assert_landed(page, result):
    require(page.locator(".descent-stage").count() == 0, "Descent overlay remained after landing")
    require(page.locator(CARD).count() == len(result["picks"]), "Descent changed the shortlist")
    require(page.evaluate("document.activeElement === document.querySelector('#results .pick-card')"),
            "Descent did not focus card 1")
    first = page.locator(CARD).first
    require(first.get_attribute("data-property-id") == result["picks"][0]["property"]["property_id"],
            "Landing targets a different property")
    image = first.locator(".shot-image")
    require(image.count() == 1, "Card 1 has no exact landing image")
    page.wait_for_function("""() => {
      const image = document.querySelector('#results .pick-card .shot-image');
      return image?.complete && image.naturalWidth > 0;
    }""")
    require(path_only(image.get_attribute("src")) == path_only(result["picks"][0]["shots"][0]["image_path"]),
            "Card 1 did not land on the supplied first interior frame")
    bounds = image.bounding_box()
    height = page.viewport_size["height"]
    require(bounds and bounds["y"] < height and bounds["y"] + bounds["height"] > 0,
            "Landing frame is outside the viewport")
    require(page.get_by_role("button", name="Replay descent", exact=True).count() == 1,
            "Replay must appear once, on card 1")
    require(first.get_by_role("button", name="Replay descent", exact=True).count() == 1,
            "Replay is not attached to card 1")
    require(page.evaluate("!document.body.classList.contains('descent-playing') && !document.documentElement.classList.contains('descent-transition')"),
            "Descent left a document motion class behind")
    require(not page.evaluate("[...document.body.children].some(n => n.inert)"),
            "Descent left the viewer inert")
    require(page.locator("#location-map .location-map__canvas").count() == 1,
            "Descent did not restore the original map canvas")
    require(not page.evaluate("[...document.querySelectorAll('#location-map .leaflet-marker-icon')].some(n => Number(getComputedStyle(n).opacity) < 1)"),
            "Descent left map pins dimmed")
    assert_no_contacts(page, result)
    assert_no_overflow(page)


def assert_sequence(run, result, *, reduced=False, aerial=True, native=True):
    require(run is not None, "No descent lifecycle occurred")
    events = run["events"]
    phases = [event["phase"] for event in events]
    live = result["source_mode"] == "live"
    expected = (["map"] + (["aerial"] if aerial else []) if live else []) + ["interior", "land", "finish"]
    require(phases == expected, f"Unexpected descent phases: {phases}; expected {expected}")
    require(events[-1].get("outcome") == "complete", "Normal descent did not complete")
    require(all(event["source_mode"] == result["source_mode"] and event["reducedMotion"] is reduced for event in events),
            "Lifecycle source/reduced-motion metadata is incorrect")
    require(all(event["property_id"] == result["picks"][0]["property"]["property_id"] for event in events),
            "Descent lifecycle changed property identity")
    width, height = run["events"][0]["dom"]["bounds"]["width"], run["events"][0]["dom"]["bounds"]["height"]
    require(width > 0 and height > 0, "Lifecycle was emitted without a visible stage")
    for phase in expected[:-2]:
        samples = [sample for sample in run["samples"] if sample.get("phase") == phase]
        require(samples, f"No browser frame displayed the {phase} stage")
        require(any(sample.get("source") for sample in samples), f"The {phase} stage has no source label")
        if phase in {"aerial", "interior"}:
            require(any(image["decoded"] and image["layer"] == phase and image["opacity"] > .8
                        for sample in samples for image in sample.get("images", [])),
                    f"The {phase} image did not become visibly opaque in a real browser frame")
    if live:
        maps = [sample for sample in run["samples"] if sample.get("phase") == "map"]
        require(any(sample["markers"] and max(sample["markers"]) == 1 and min(sample["markers"]) < 1 for sample in maps),
                "Map stage did not retain the top pin and dim other pins")
        if reduced:
            require(not run["flyCalls"], "Reduced motion invoked Leaflet flyTo")
            require(len({sample["mapTransform"] for sample in maps}) <= 1,
                    "Reduced-motion map moved between rendered frames")
        else:
            require(len(run["flyCalls"]) == 1, "Normal descent did not fly the actual Leaflet map exactly once")
            require(run["flyCalls"][0]["point"] == [result["picks"][0]["property"]["lat"], result["picks"][0]["property"]["lon"]],
                    "Map flew to coordinates other than the top pick")
        if aerial:
            event = next(event for event in events if event["phase"] == "aerial")
            require("Vexcel aerial" in event["dom"]["source"], "Aerial is not labelled Vexcel")
            require("Parking " in event["dom"]["note"], "Aerial omits parking uncertainty")
            logistics = result["picks"][0]["logistics"]
            status = logistics.get("parking_status") or ("estimated" if logistics.get("estimated") is True else "unknown")
            require(f"Parking {status}" in event["dom"]["note"], "Parking certainty disagrees with the response")
            geometry = event.get("geometry")
            require(geometry in {"projected", "existing-image"}, "Aerial has no honest geometry path")
            require(bool(event["dom"]["outline"]) == (geometry == "projected"),
                    "SVG outline disagrees with the validated geometry path")
            image = next(image for image in event["dom"]["images"] if image["layer"] == "aerial")
            original = path_only(result["picks"][0]["logistics"]["aerial_image_path"])
            projected = f"/cache/vexcel/{result['picks'][0]['property']['property_id']}/aerial.png"
            require(image["decoded"] and image["path"] == (projected if geometry == "projected" else original),
                    "Aerial does not use the decoded supplied property image")
        require("Matterport scan" in next(event for event in events if event["phase"] == "interior")["dom"]["source"],
                "Real interior is not labelled Matterport scan")
    else:
        require(not run["flyCalls"] and run["viewTransitions"] == 0, "Mock data performed a live map/morph")
        require("MOCK" in events[0]["dom"]["source"] and "Synthetic" in events[0]["dom"]["source"],
                "Fixture descent is not honestly labelled")
    interior = next(event for event in events if event["phase"] == "interior")
    image = next(image for image in interior["dom"]["images"] if image["layer"] == "interior")
    require(image["decoded"] and image["path"] == path_only(result["picks"][0]["shots"][0]["image_path"]),
            "Descent interior differs from the supplied first shot")
    if reduced:
        for animation in run["animations"]:
            for frame in animation["frames"]:
                require(not any(key in frame for key in {"transform", "filter", "clipPath"}),
                        "Reduced motion contains flight, zoom, blur or wipe")
            require(animation["options"]["duration"] <= 200, "Reduced-motion layer exceeds 200ms")
        require(run["viewTransitions"] == 0, "Reduced motion used a spatial View Transition")
        require(events[-1]["elapsed_ms"] <= 1600, "Reduced-motion sequence was not a short crossfade")
    elif live:
        require(run["viewTransitions"] == int(native), "Native View Transition/fallback choice is incorrect")
        require(1800 <= events[-1]["elapsed_ms"] <= 5500, "Normal descent duration is outside the authored motion budget")


def finish_row(page, row, result):
    require(row["approve_requests"] == 0, "Descent requested an owner draft")
    require(not row["page_errors"], "Browser JavaScript exception; inspect report")
    require(not row["console_errors"], "Unexpected browser console error; inspect report")
    require(result["source_mode"].upper() in page.locator("#source-mode").inner_text().upper(),
            "Viewer source badge disagrees with the returned response")
    for event in row.get("lifecycle", []):
        if event.get("dom", {}).get("stage"):
            bounds = event["dom"]["bounds"]
            require(abs(bounds["x"]) <= 1 and abs(bounds["y"]) <= 1
                    and abs(bounds["width"] - row["viewport"][0]) <= 1
                    and abs(bounds["height"] - row["viewport"][1]) <= 1,
                    "A rendered descent layer did not fill the actual viewport")
    if result.get("events"):
        assert_activity(page, page.evaluate("window.__viewerCheck.events"))
    assert_no_contacts(page, result)
    assert_no_overflow(page)
    row["passed"] = True


def measured(run):
    frames = run["frames"]
    return {"visible_raf_intervals":len(frames), "raf_p50_ms":percentile(frames, .5),
            "raf_p95_ms":percentile(frames, .95), "raf_max_ms":round(max(frames), 3) if frames else None,
            "longtasks":run["longtasks"], "elapsed_ms":round(run["events"][-1]["elapsed_ms"], 3),
            "target_fps":60, "measurement":"Uninterrupted visible sequence; no concurrent screenshots"}


def case(report, args, name, viewport, controlled, operation):
    row = {"case":name, "viewport":list(viewport), "controlled":controlled, "passed":False}
    report["checks"].append(row)
    save_report(args, report)
    try:
        return operation(row)
    except Exception as error:
        row["error"] = f"{type(error).__name__}: {error}"
        print(f"{name} {viewport}: {row['error']}", file=sys.stderr, flush=True)
    finally:
        save_report(args, report)


def genuine(browser, args, row, scene, index):
    context, page = open_page(browser, args, row)
    try:
        result = start_scout(page, scene["scene"])
        require(result["source_mode"] == args.mode, "Genuine API response source mode disagrees with config")
        destination = args.output / f"scene-{index}-{row['viewport'][0]}.response.json"
        destination.write_text(json.dumps(result, indent=2) + "\n")
        row.update(scene=scene["label"], response_file=destination.name, source_mode=result["source_mode"],
                   engine=result["engine"], evidence="Genuine browser EventSource -> actual local scouting API")
        run = await_finish(page)
        row["motion"] = measured(run)
        row["lifecycle"] = run["events"]
        assert_sequence(run, result, aerial=bool(result["picks"][0]["logistics"].get("aerial_image_path")))
        assert_landed(page, result)
        assert_activity(page, page.evaluate("window.__viewerCheck.events"))
        finish_row(page, row, result)
        return result
    finally:
        context.close()


def controlled(browser, args, row, baseline, name):
    result = deepcopy(baseline)
    if name == "missing-aerial":
        result["picks"][0]["logistics"]["aerial_image_path"] = None
    if name == "missing-geometry":
        result["picks"][0]["logistics"].update(parking_polygon=[], parking_geometry=None)
    if name == "mock":
        result.update(picks=json.loads((ROOT / "mocks/pick.json").read_text()),
                      source_mode="mock", engine="fixed", events=[], trace_url=None)
    reduced = name == "reduced-motion"
    context, page = open_page(browser, args, row, result=result, reduced=reduced,
                              no_transition=name == "no-view-transition",
                              metadata_failure=name == "missing-extent", metadata_corrupt=name == "stale-extent",
                              image_failure=name == "failed-aerial-image")
    try:
        row["evidence"] = "Controlled browser replay of saved real API response; scouting engine not rerun"
        if name == "mock":
            row["evidence"] = "Controlled synthetic fixture response; scouting engine not rerun"
        if name == "mock":
            page.route("**/config", lambda route: route.fulfill(json={"mode":"mock", "engine":"fixed"}))
        start_scout(page, "Controlled descent acceptance replay")
        page.locator(".descent-stage").wait_for(state="visible")
        if name in {"click-skip", "escape-skip", "any-key-skip"}:
            if name == "click-skip":
                page.locator(".descent-stage").click(position={"x":100, "y":300})
            else:
                page.keyboard.press("Escape" if name == "escape-skip" else "x")
            run = await_finish(page)
            require(run["events"][-1].get("outcome") == "skipped", "Input did not skip descent")
            require(run["events"][-1]["elapsed_ms"] < 1800, "Skip waited for the full sequence")
            assert_landed(page, result)
        elif name == "hidden-tab":
            # Playwright normally forces every page to be focused/visible.
            # Release that native CDP override before testing actual tab hiding.
            session = context.new_cdp_session(page)
            session.send("Emulation.setFocusEmulationEnabled", {"enabled":False})
            page.bring_to_front()
            other = context.new_page()
            other.goto("about:blank")
            other.bring_to_front()
            page.wait_for_timeout(150)
            actual_hidden = page.evaluate("document.hidden")
            visibility_method = "Actual foreground-tab change" if actual_hidden else None
            window_id = None
            if not actual_hidden and args.headed:
                try:
                    window_id = session.send("Browser.getWindowForTarget")["windowId"]
                    session.send("Browser.setWindowBounds", {"windowId":window_id, "bounds":{"windowState":"minimized"}})
                    page.wait_for_timeout(250)
                    actual_hidden = page.evaluate("document.hidden")
                    if actual_hidden:
                        visibility_method = "Actual headed Chrome window minimization"
                except Exception as error:
                    row["visibility_window_control"] = type(error).__name__
            row["visibility_method"] = visibility_method or "Controlled visibilitychange simulation (browser retained visible state)"
            if not actual_hidden:
                page.evaluate("""() => {
                  Object.defineProperty(document,'hidden',{value:true,configurable:true});
                  document.dispatchEvent(new Event('visibilitychange'));
                }""")
            run = await_finish(page)
            require(run["events"][-1].get("outcome") == "hidden", "Hidden tab did not abort descent")
            require(page.locator(".descent-stage").count() == 0, "Hidden abort left the overlay")
            require(not page.evaluate("document.body.classList.contains('descent-playing')"), "Hidden abort retained scroll lock")
            page.evaluate("delete document.hidden")
            if session and window_id is not None:
                session.send("Browser.setWindowBounds", {"windowId":window_id, "bounds":{"windowState":"normal"}})
            if session:
                session.send("Emulation.setFocusEmulationEnabled", {"enabled":True})
                session.detach()
            other.close()
            page.bring_to_front()
            page.wait_for_timeout(250)
            require(page.evaluate("window.__descentCheck.runs.length") == 1, "Returning to tab replayed the descent")
        else:
            run = await_finish(page)
            row["motion"] = measured(run)
            assert_sequence(run, result, reduced=reduced,
                            aerial=name not in {"missing-aerial", "failed-aerial-image"} and result["source_mode"] == "live",
                            native=name != "no-view-transition")
            assert_landed(page, result)
            if name in {"missing-extent", "stale-extent", "missing-geometry"}:
                aerial = next(event for event in run["events"] if event["phase"] == "aerial")
                require(aerial.get("geometry") == "existing-image" and aerial["dom"]["outline"] is None,
                        "Unreliable geometry did not use the existing annotated image")
            if name == "replay":
                # Move to another supplied frame before replay; landing must still
                # use shots[0], including after the viewfinder's own decoration.
                next_frame = page.locator(CARD).first.get_by_role("button", name=re.compile(r"^Next interior frame at "))
                if len(result["picks"][0]["shots"]) > 1:
                    require(next_frame.count() == 1 and next_frame.is_enabled(), "Cannot change supplied frame before replay")
                    next_frame.click()
                    require(path_only(page.locator(CARD).first.locator(".shot-image").get_attribute("src"))
                            == path_only(result["picks"][0]["shots"][1]["image_path"]),
                            "Next-frame control did not actually change the frame before replay")
                    row["replay_from_other_frame"] = True
                else:
                    row["replay_from_other_frame"] = False
                page.get_by_role("button", name="Replay descent", exact=True).click()
                run = await_finish(page, 2)
                assert_sequence(run, result)
                assert_landed(page, result)
                require(page.evaluate("window.__viewerCheck.results.length") == 1, "Replay reran the scouting engine")
        row["lifecycle"] = run["events"]
        finish_row(page, row, result)
    finally:
        context.close()


def refinement(browser, args, row, baseline):
    context, page = open_page(browser, args, row, result=baseline)
    try:
        start_scout(page, "Controlled refinement setup")
        await_finish(page)
        after = deepcopy(baseline)
        page.route("**/refine", lambda route: route.fulfill(json=after))
        page.locator("#refine-message").fill("need parking for 5 trucks")
        page.locator("#refine-button").click()
        page.wait_for_function("document.querySelector('#refine-button').disabled === false")
        page.wait_for_timeout(1200)
        require(page.evaluate("window.__descentCheck.runs.length") == 1, "Refinement automatically replayed descent")
        require(page.locator("#changes").is_visible(), "Refinement lost its change summary")
        require(page.get_by_role("button", name="Replay descent", exact=True).count() == 1, "Refinement lost replay")
        page.get_by_role("button", name="Replay descent", exact=True).click()
        run = await_finish(page, 2)
        assert_sequence(run, after)
        assert_landed(page, after)
        row.update(lifecycle=run["events"], evidence="Controlled scout/refinement response replay; engine not rerun")
        finish_row(page, row, after)
    finally:
        context.close()


def captures(browser, args, row, baseline):
    context, page = open_page(browser, args, row, result=baseline)
    try:
        start_scout(page, "Controlled phase capture replay")
        for phase in ["map", "aerial", "interior"]:
            page.locator(f'.descent-stage[data-phase="{phase}"]').wait_for(state="visible")
            page.wait_for_timeout(240 if phase != "map" else 100)
            assert_no_contacts(page, baseline)
            page.evaluate("""() => {
              let b = document.querySelector('#controlled-capture-label');
              if (!b) {b=document.createElement('div'); b.id='controlled-capture-label'; document.body.append(b);}
              b.textContent='CONTROLLED UI REPLAY — real cached response; not a fresh engine run';
              b.style.cssText='position:fixed;z-index:99999;bottom:0;left:0;right:0;background:#ffed8a;color:#111;padding:8px;font:700 12px sans-serif;text-align:center;pointer-events:none';
            }""")
            page.screenshot(path=str(args.output / f"controlled-{row['viewport'][0]}-{phase}.png"))
        run = await_finish(page)
        assert_landed(page, baseline)
        page.screenshot(path=str(args.output / f"controlled-{row['viewport'][0]}-land.png"))
        row.update(lifecycle=run["events"], evidence="Controlled screenshot replay; excluded from performance measurements")
        finish_row(page, row, baseline)
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8008")
    parser.add_argument("--mode", choices=["live", "mock"], default="live")
    parser.add_argument("--output", type=Path, default=ROOT / "cache/screens/descent")
    parser.add_argument("--executable", default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--controls-only", action="store_true", help="Replay --response; no genuine API runs")
    parser.add_argument("--response", type=Path, help="Private saved response for controlled reruns")
    parser.add_argument("--case", action="append", help="Limit controlled cases by name")
    args = parser.parse_args()
    origin = urlsplit(args.base_url)
    if origin.scheme != "http" or origin.hostname not in {"localhost", "127.0.0.1"} or origin.path not in {"", "/"}:
        parser.error("Use a local HTTP application origin")
    args.base_url = args.base_url.rstrip("/")
    args.output = args.output.resolve()
    if not args.output.is_relative_to((ROOT / "cache").resolve()):
        parser.error("Reports/screenshots must stay under ignored private cache/")
    if args.controls_only and not args.response:
        parser.error("--controls-only requires a saved --response")
    if args.response and not args.response.resolve().is_relative_to((ROOT / "cache").resolve()):
        parser.error("Saved responses must stay under ignored private cache/")
    try:
        from playwright.sync_api import sync_playwright
        version = importlib.metadata.version("playwright")
    except ImportError:
        parser.error("Use the isolated cache/browser-venv Playwright environment")
    report = {"passed":False, "created_utc":datetime.now(timezone.utc).isoformat(),
              "playwright_version":version, "requested_mode":args.mode,
              "controls_only":args.controls_only, "checks":[]}
    save_report(args, report)
    try:
        with sync_playwright() as playwright:
            request = playwright.request.new_context(base_url=args.base_url)
            try:
                health = request.get("/health")
                config = request.get("/config")
                require(health.ok and config.ok, "Application health/config failed")
                health, config = health.json(), config.json()
                require(config.get("mode") == args.mode and set(health.get("source_modes", {}).values()) == {args.mode},
                        "Server source configuration disagrees with requested mode")
                report["server"] = {"mode":config["mode"], "engine":config.get("engine"), "mocks":health.get("mocks")}
            finally:
                request.dispose()
            browser = playwright.chromium.launch(executable_path=args.executable, headless=not args.headed)
            try:
                report["browser_version"] = browser.version
                baseline = json.loads(args.response.read_text()) if args.response else None
                if not args.controls_only:
                    scene_context = browser.new_context()
                    scene_page = scene_context.new_page()
                    scene_page.goto(args.base_url + "/app/")
                    scenes = scene_page.evaluate("async () => (await import('/app/scenes.js')).SCENES")
                    scene_context.close()
                    for viewport in VIEWPORTS:
                        for index, scene in enumerate(scenes, 1):
                            response = case(report, args, "genuine-api-scene", viewport, False,
                                lambda row, scene=scene, index=index: genuine(browser, args, row, scene, index))
                            if response and (baseline is None or
                                len(baseline["picks"][0]["shots"]) < 2 <= len(response["picks"][0]["shots"])):
                                baseline = response
                require(baseline is not None, "No genuine response is available for labelled controlled checks")
                if args.mode == "live":
                    names = ["replay", "click-skip", "escape-skip", "any-key-skip", "hidden-tab", "reduced-motion",
                             "no-view-transition", "missing-aerial", "failed-aerial-image", "missing-extent", "stale-extent", "missing-geometry", "mock"]
                    for viewport in VIEWPORTS:
                        for name in names:
                            if args.case and name not in args.case:
                                continue
                            case(report, args, name, viewport, True,
                                 lambda row, name=name: controlled(browser, args, row, baseline, name))
                        if not args.case or "refinement-no-auto" in args.case:
                            case(report, args, "refinement-no-auto", viewport, True,
                                 lambda row: refinement(browser, args, row, baseline))
                        if not args.case or "phase-captures" in args.case:
                            case(report, args, "phase-captures", viewport, True,
                                 lambda row: captures(browser, args, row, baseline))
                report["passed"] = bool(report["checks"]) and all(row["passed"] for row in report["checks"])
            finally:
                browser.close()
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        print(report["error"], file=sys.stderr)
    finally:
        save_report(args, report)
    print(json.dumps({"passed":report["passed"], "checks":len(report["checks"]),
                      "genuine_api_runs":sum(not row["controlled"] for row in report["checks"]),
                      "report":str(args.output / "descent-report.json")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
