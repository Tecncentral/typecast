"""Exercise the actual viewer on a running local MOCK server.

No server is started here. Screenshots and the report stay in ignored cache/.
Optional failure cases are explicitly controlled browser simulations, not runs
of the scouting engine. This script never sends an owner inquiry.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
POLICE_SCENE = (
    "INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling, windows on one wall. "
    "Parking for 3 trucks and 30 crew cars."
)
REFINEMENT = "need parking for 5 trucks"
# The page rounds over-precise measurements for display (web/utils.js tidyText).
SHOWN = "async (text) => (await import('/app/utils.js')).tidyText(text)"


def shown(page, text):
    return page.evaluate(SHOWN, text)
CARD = "#results .pick-card"

# Observe events delivered by the real EventSource, without adding progress.
OBSERVE_STREAM = """(() => {
  window.__viewerCheck = {events: [], results: [], errors: []};
  const NativeEventSource = window.EventSource;
  window.EventSource = class extends NativeEventSource {
    constructor(...args) {
      super(...args);
      for (const [kind, key] of [['agent', 'events'], ['result', 'results'], ['error', 'errors']]) {
        this.addEventListener(kind, event => {
          if (event.data) {
            try { window.__viewerCheck[key].push(JSON.parse(event.data)); }
            catch { window.__viewerCheck.errors.push({message: 'Malformed SSE JSON'}); }
          }
        });
      }
    }
  };
})();"""

# A pending connection tests elapsed time without inventing agent events.
PENDING_STREAM = """(() => {
  window.EventSource = class extends EventTarget {
    static CONNECTING = 0; static OPEN = 1; static CLOSED = 2;
    constructor(url) { super(); this.url = url; this.readyState = 0; }
    close() { this.readyState = 2; }
  };
})();"""


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def normalized(text):
    return " ".join(text.split())


def path_only(url):
    return "/" + urlsplit(url).path.lstrip("/")


def assert_no_contacts(page, *results):
    text = page.locator("body").inner_text()
    for result in results:
        for pick in result.get("picks", []):
            contact = pick.get("property", {}).get("contact")
            if contact:
                require(contact not in text, "A listing contact is exposed in the screenshot area")
    require(page.locator('a[href^="mailto:"], a[href^="tel:"]').count() == 0,
            "Viewer exposes a contact link")


def assert_no_overflow(page):
    dimensions = page.evaluate("""() => ({
      viewport: document.documentElement.clientWidth,
      content: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)
    })""")
    require(dimensions["content"] <= dimensions["viewport"] + 1,
            f"Horizontal overflow: {dimensions}")


def assert_trace(page, result):
    links = page.get_by_role("link", name=re.compile(r"^View trace\b"))
    trace = result.get("trace_url")
    if trace:
        require(links.count() == 1 and links.first.get_attribute("href") == trace,
                "Trace link does not match the API response")
    else:
        require(links.count() == 0, "A trace link is shown without a returned trace URL")


def assert_cards(page, result):
    picks = result["picks"]
    page.wait_for_function("count => document.querySelectorAll('#results .pick-card').length === count",
                           arg=len(picks))
    cards = page.locator(CARD)
    require(len(picks) == 3, "The mock acceptance run did not return three picks")
    for index, pick in enumerate(picks):
        card = cards.nth(index)
        require(card.is_visible(), "A returned pick is hidden")
        require(card.get_attribute("data-property-id") == pick["property"]["property_id"],
                "Card property does not match the returned shortlist")
        require(card.get_attribute("data-rank") == str(pick["rank"]), "Card rank is incorrect")
        reason = card.locator(".pick-rationale")
        require(reason.locator("summary").is_visible(), "Card has no visible rationale summary")
        reason.locator("summary").click()
        # The page rounds over-precise measurements and renames the blocker
        # prefix; compare against that same display formatting, nothing else.
        expected = page.evaluate("async (text) => (await import('/app/utils.js')).readableReason(text)",
                                 pick["reason"])
        require(all(source in expected for source in ("CoStar", "Matterport", "Vexcel")),
                "Display formatting dropped a source from the rationale")
        require(normalized(expected) in normalized(reason.inner_text()),
                "Expanded reason omits the API's full rationale")
        reason.locator("summary").click()
        extra = card.locator(".skeptic-more")
        if extra.count():
            extra.locator("summary").click()
        text = normalized(card.inner_text())
        for note in pick["skeptic_notes"]:
            require(normalized(shown(page, note)) in text, "Card omits a returned skeptic note")
        if extra.count():
            extra.locator("summary").click()
        allowed = {path_only(shot["image_path"]) for shot in pick["shots"]}
        card.scroll_into_view_if_needed()
        page.wait_for_function("""index => {
          const card = document.querySelectorAll('#results .pick-card')[index];
          const imgs = [...card.querySelectorAll('img')].filter(i => i.getClientRects().length);
          return imgs.length > 0 && imgs.every(i => i.complete && i.naturalWidth > 0 && i.naturalHeight > 0);
        }""", arg=index)
        paths = card.locator("img").evaluate_all("""imgs => imgs
          .filter(i => i.getClientRects().length).map(i => new URL(i.currentSrc).pathname)""")
        require(any(path in allowed for path in paths), "Card does not show a returned interior frame")
    notes = page.locator(f"{CARD} .skeptic-note")
    require(notes.count() > 0 and any(normalized(note) != "No objection." for note in notes.all_text_contents()),
            "No substantive skeptic objection is visible")
    require(result.get("source_mode") == "mock", "A response switched out of mock mode")
    require("MOCK" in page.locator("#source-mode").inner_text().upper(), "MOCK label is missing")
    require(result["engine"].lower() in page.locator("#engine").inner_text().lower(),
            "Engine badge disagrees with the response")
    require(re.search(r"\d", page.locator("#elapsed").inner_text()), "Elapsed time is missing")
    assert_trace(page, result)
    assert_no_contacts(page, result)
    assert_no_overflow(page)


def assert_activity(page, events):
    rows = page.locator("[data-event-text]")
    require(rows.count() > 0, "No inspectable activity rows were rendered")
    returned = {normalized(event["text"]) for event in events}
    for row in rows.all():
        require(normalized(row.get_attribute("data-event-text") or "") in returned,
                "An activity row is not backed by a received event")


def assert_changes(page, before, after):
    changes = page.locator("#changes")
    require(changes.is_visible(), "Refinement summary is hidden")
    text = normalized(changes.inner_text())
    require(text, "Refinement summary is empty")
    previous = {pick["property"]["property_id"]: pick for pick in before["picks"]}
    current = {pick["property"]["property_id"]: pick for pick in after["picks"]}
    moved = []
    new_objections = 0
    for property_id, pick in current.items():
        old = previous.get(property_id)
        if old is None or old["rank"] != pick["rank"]:
            moved.append(property_id)
            require(normalized(pick["property"]["address"]) in text,
                    "Summary omits a new or moved pick")
        if old is None:
            # A newcomer's standing caveats stay on its card, counted in the summary.
            if pick["skeptic_notes"]:
                require(f"its {len(pick['skeptic_notes'])} caveats are on its card" in text.lower(),
                        "Summary does not point to a newcomer's caveats")
            continue
        for note in set(pick["skeptic_notes"]) - set(old["skeptic_notes"]) - {"No objection."}:
            new_objections += 1
            require(normalized(shown(page, note)) in text, "Summary omits a newly returned objection")
    for property_id in previous.keys() - current.keys():
        require(normalized(previous[property_id]["property"]["address"]) in text,
                "Summary omits a removed pick")
    if not moved and previous.keys() == current.keys():
        require("rank order unchanged" in text.lower(), "Unchanged ranks are not stated honestly")
    history = page.locator("#previous-results")
    require(history.is_visible(), "Earlier frames disappeared after refinement")
    history.scroll_into_view_if_needed()
    page.wait_for_function("""() => [...document.querySelectorAll('#previous-results img')]
      .filter(i => i.getClientRects().length).every(i => i.complete && i.naturalWidth > 0)""")
    images = history.locator("img").evaluate_all("""imgs => imgs
      .filter(i => i.getClientRects().length && i.complete && i.naturalWidth > 0)
      .map(i => new URL(i.currentSrc).pathname)""")
    for pick in before["picks"]:
        require(path_only(pick["shots"][0]["image_path"]) in images,
                "An earlier pick's first frame is not preserved visibly")
    return {"rank_changes": len(moved), "new_objections": new_objections}


def screenshot(page, destination, *results, controlled=None):
    assert_no_contacts(page, *results)
    require(page.get_by_role("dialog").count() == 0, "Close the evidence drawer before capture")
    if controlled:
        page.evaluate("""label => {
          const banner = document.createElement('div');
          banner.textContent = 'CONTROLLED UI CHECK — ' + label;
          banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#ffed8a;color:#111;padding:12px;font:700 16px sans-serif;text-align:center';
          document.body.append(banner);
        }""", controlled)
    page.evaluate("""async () => {
      await document.fonts.ready;
      if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
      window.scrollTo({top: 0, left: 0, behavior: 'instant'});
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    }""")
    page.wait_for_function("window.scrollY === 0 && window.scrollX === 0")
    page.screenshot(path=str(destination), full_page=True)


def open_page(browser, viewport, row, *, pending=False):
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    page = context.new_page()
    page.set_default_timeout(60000)
    page.add_init_script(PENDING_STREAM if pending else OBSERVE_STREAM)
    row.update(console_errors=[], expected_map_errors=[], page_errors=[], approve_requests=0)

    def console_message(message):
        if message.type != "error":
            return
        record = {"text": message.text, "url": message.location.get("url", "")}
        host = urlsplit(record["url"]).hostname
        osm_tile = host in {"tile.openstreetmap.org", "a.tile.openstreetmap.org",
                            "b.tile.openstreetmap.org", "c.tile.openstreetmap.org"}
        expected = osm_tile and message.text.startswith("Failed to load resource:")
        row["expected_map_errors" if expected else "console_errors"].append(record)

    page.on("console", console_message)
    page.on("pageerror", lambda error: row["page_errors"].append(str(error)))

    def requested(request):
        if path_only(request.url) == "/approve":
            row["approve_requests"] += 1

    page.on("request", requested)
    return context, page


def run_viewport(browser, args, width, height, report):
    row = {"case": "real_mock_api", "viewport": [width, height], "passed": False}
    report["checks"].append(row)
    context, page = open_page(browser, {"width": width, "height": height}, row)
    try:
        page.goto(args.base_url + "/app/", wait_until="networkidle")
        require("WAREHOUSE" in page.locator("#scene").input_value(), "Default warehouse scene changed")
        # The mock expectations below are written for the police scene.
        page.locator("#scene").fill(POLICE_SCENE)
        require("MOCK" in page.locator("#source-mode").inner_text().upper(), "Config does not visibly say MOCK")
        page.locator("#run-button").click()
        page.wait_for_function("window.__viewerCheck.results.length === 1")
        before = page.evaluate("window.__viewerCheck.results[0]")
        assert_cards(page, before)
        assert_activity(page, page.evaluate("window.__viewerCheck.events"))
        require(row["approve_requests"] == 0, "A draft was requested without an explicit click")
        first_card = page.locator(CARD).first
        evidence = first_card.get_by_role("button", name="View evidence", exact=True)
        require(evidence.count() == 1, "Evidence disclosure is missing")
        evidence.click()
        drawer = page.get_by_role("dialog")
        drawer.wait_for(state="visible")
        for item in before["picks"][0].get("evidence", []):
            require(normalized(shown(page, item["claim"])) in normalized(drawer.inner_text()),
                    "Evidence disclosure omits a returned claim")
        assert_no_contacts(page, before)
        assert_no_overflow(page)
        drawer.get_by_role("button", name=re.compile(r"^Close\b")).first.click()
        page.locator("dialog").wait_for(state="detached")
        screenshot(page, args.screens_dir / f"viewer-{width}x{height}-scout.png", before)

        page.locator("#refine-message").fill(REFINEMENT)
        with page.expect_response(lambda r: path_only(r.url) == "/refine" and r.request.method == "POST") as response:
            page.locator("#refine-button").click()
        require(response.value.ok, "Refinement request failed")
        require(response.value.request.post_data_json == {"thread_id": before["thread_id"], "message": REFINEMENT},
                "Refinement did not preserve the thread and supplied message")
        after = response.value.json()
        page.wait_for_function("document.querySelector('#refine-button').disabled === false")
        require(after["thread_id"] == before["thread_id"], "Refinement switched threads")
        assert_cards(page, after)
        row.update(assert_changes(page, before, after))
        assert_activity(page, before["events"] + after["events"])
        require(row["approve_requests"] == 0, "Refinement automatically requested an owner draft")
        screenshot(page, args.screens_dir / f"viewer-{width}x{height}-refine.png", before, after)

        with page.expect_response(lambda r: path_only(r.url) == "/approve" and r.request.method == "POST") as response:
            page.locator(CARD).first.get_by_role("button", name="Draft note", exact=True).click()
        require(response.value.ok, "Local draft request failed")
        body = response.value.request.post_data_json
        require(body["thread_id"] == after["thread_id"] and body["pick_rank"] == after["picks"][0]["rank"]
                and body["decision"] == "yes", "Draft request targets the wrong pick or lacks explicit approval")
        draft = response.value.json()
        require(draft.get("sent") is False and draft.get("status") == "draft_saved",
                "Draft endpoint did not confirm a saved, unsent draft")
        page.wait_for_function("""() => document.querySelector('#draft-status')
          .textContent.includes('Saved as a local draft, not sent')""")
        require(row["approve_requests"] == 1, "Unexpected extra draft requests")
        assert_no_overflow(page)
        require(not row["page_errors"], "Browser JavaScript error (see report)")
        require(not row["console_errors"], "Browser console error (see report)")
        row.update(passed=True, cards=len(after["picks"]), images_checked=True,
                   source_mode=after["source_mode"], engine=after["engine"])
        return before
    finally:
        context.close()


def controlled_stream(result):
    chunks = [f"event: agent\ndata: {json.dumps(event)}\n\n" for event in result["events"]]
    return "".join(chunks) + f"event: result\ndata: {json.dumps(result)}\n\n"


def run_controlled_cases(browser, args, baseline, report):
    for case in ("api-error", "no-match", "missing-image", "slow-pending-stream"):
        row = {"case": case, "controlled": True, "viewport": [1280, 720], "passed": False}
        report["checks"].append(row)
        context, page = open_page(browser, {"width": 1280, "height": 720}, row,
                                  pending=case == "slow-pending-stream")
        try:
            result = deepcopy(baseline)
            if case == "api-error":
                page.route("**/scout/stream?**", lambda route: route.fulfill(
                    status=503, content_type="application/json", body='{"detail":"Controlled API failure"}'))
            elif case == "no-match":
                result.update(picks=[], gave_up=["Controlled browser check: no matching candidates."],
                              events=[{"type": "relaxed", "agent": "director",
                                       "text": "Controlled browser check: no matching candidates.", "engine": "fixed"}])
                page.route("**/scout/stream?**", lambda route: route.fulfill(
                    content_type="text/event-stream", body=controlled_stream(result)))
            elif case == "missing-image":
                page.route("**/scout/stream?**", lambda route: route.fulfill(
                    content_type="text/event-stream", body=controlled_stream(result)))
                page.route("**/mocks/img/**", lambda route: route.abort("failed"))
            page.goto(args.base_url + "/app/", wait_until="networkidle")
            page.locator("#run-button").click()
            if case == "api-error":
                page.locator("#api-error").wait_for(state="visible")
                require(page.locator(CARD).count() == 0, "API failure was replaced by results")
                require(page.locator("#run-button").is_enabled(), "API error left Run disabled")
            elif case == "no-match":
                page.locator("#relaxations").get_by_text(
                    "Controlled browser check: no matching candidates.", exact=False).first.wait_for()
                page.locator("#empty-state").wait_for(state="visible")
                require(page.locator(CARD).count() == 0, "No-match response was padded with cards")
            elif case == "missing-image":
                page.locator(CARD).first.scroll_into_view_if_needed()
                page.locator("#results .image-fallback").first.wait_for(state="visible")
                require(page.locator(CARD).count() == 3, "A missing image removed a result card")
            else:
                require(page.locator("#run-button").is_disabled(), "Pending stream does not show a running state")
                initial = page.locator("#elapsed").inner_text()
                page.wait_for_function("previous => document.querySelector('#elapsed').textContent !== previous",
                                       arg=initial, timeout=5000)
                require(page.locator(CARD).count() == 0, "Pending stream invented results")
                require(page.locator("[data-event-text]").count() == 0, "Pending stream invented activity")
            require(row["approve_requests"] == 0, "A controlled failure requested an owner draft")
            require(not row["page_errors"], "Controlled state caused a JavaScript error")
            assert_no_overflow(page)
            assert_trace(page, result if case == "missing-image" else {})
            screenshot(page, args.screens_dir / f"controlled-{case}.png", result, controlled=case)
            row["passed"] = True
        finally:
            context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--screens-dir", type=Path, default=ROOT / "cache/screens")
    parser.add_argument("--executable", help="Optional installed Chromium executable")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--failure-states", action="store_true", help="Also run clearly marked controlled UI cases")
    parser.add_argument("--mobile", action="store_true", help="Also run the real mock flow at 390x844")
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.path not in {"", "/"}:
        parser.error("Use a local HTTP application origin")
    args.base_url = args.base_url.rstrip("/")
    args.screens_dir = args.screens_dir.resolve()
    if not args.screens_dir.is_relative_to((ROOT / "cache").resolve()):
        parser.error("Screenshots and reports must stay under ignored cache/")
    try:
        from playwright.sync_api import sync_playwright
        version = importlib.metadata.version("playwright")
    except ImportError:
        parser.error("Playwright is not installed; see web/README.md for isolated browser-check setup")
    args.screens_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.screens_dir / "viewer-report.json"
    report = {"passed": False, "source_mode": "mock", "playwright_version": version, "checks": []}
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    try:
        with sync_playwright() as playwright:
            request = playwright.request.new_context(base_url=args.base_url)
            try:
                health_response = request.get("/health")
                config_response = request.get("/config")
                require(health_response.ok and config_response.ok, "Application health/config request failed")
                health, config = health_response.json(), config_response.json()
                require(health.get("mocks") is True and config.get("mode") == "mock"
                        and set(health.get("source_modes", {}).values()) == {"mock"},
                        "Browser acceptance captures fixtures only: restart the server with all sources in mock mode")
            finally:
                request.dispose()
            browser = playwright.chromium.launch(executable_path=args.executable, headless=not args.headed)
            try:
                report["browser_version"] = browser.version
                baseline = None
                viewports = [(1440, 900), (1280, 720)]
                if args.mobile:
                    viewports.append((390, 844))
                for width, height in viewports:
                    baseline = run_viewport(browser, args, width, height, report)
                if args.failure_states:
                    run_controlled_cases(browser, args, baseline, report)
                report["passed"] = True
            finally:
                browser.close()
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        print(report["error"], file=sys.stderr)
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "playwright_version": version,
                      "checks": len(report["checks"]), "report": str(report_path)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
