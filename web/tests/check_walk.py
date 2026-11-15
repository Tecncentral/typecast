"""Check the walkable AI set in local Chrome: load the splat, walk, hit a wall, grab, leave.

Needs a running live server whose cache holds a dressed scan point with a splat
(`python -m worlds.dress --splat --draft ...`). No model call, no Atlas call, no spend.
Screenshots stay in ignored cache/.

  cache/browser-venv/bin/python web/tests/check_walk.py --base-url http://localhost:8006 \
    --shot <shot_id> --executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

OPEN = """async (id) => {
  const {Viewfinder} = await import('/app/viewfinder.js');
  const vf = new Viewfinder(); window.__vf = vf;
  const img = new Image(); img.className = 'shot-image'; img.alt = 'Frame at Check St';
  img.src = '/cache/views/' + id + '.jpg'; img.style.cssText = 'position:fixed;left:20px;top:20px;width:200px';
  document.body.append(img); await img.decode(); await vf.open(id, img);
}"""
CARD = """async (id) => {
  const stage = document.createElement('div'); stage.className = 'shot-stage';
  stage.style.cssText = 'position:fixed;left:20px;top:20px;width:640px;height:360px;z-index:5';
  const img = new Image(); img.className = 'shot-image'; img.alt = 'Frame at Check St';
  img.src = '/cache/views/' + id + '.jpg'; img.style.cssText = 'width:100%;height:100%;object-fit:cover';
  stage.append(img); document.body.append(stage); await img.decode();
}"""
STATE = """async () => {
  const {walkState} = await import('/app/viewfinder-walk.js');
  const w = walkState(window.__vf), free = Array.from(w.free || []), g = w.grid;
  const on = g ? g.walk[Math.floor((w.position[2] - g.minZ) / g.cell) * g.nx + Math.floor((w.position[0] - g.minX) / g.cell)] === 1 : null;
  let toward = free.length ? free.indexOf(Math.max(...free)) * 4 : 0;
  if (g) {  // head for the nearest other scan point
    const others = g.points.filter(p => Math.hypot(p[0] - w.eye[0], p[2] - w.eye[2]) > 0.2 * w.scale)
      .sort((a, b) => Math.hypot(a[0] - w.eye[0], a[2] - w.eye[2]) - Math.hypot(b[0] - w.eye[0], b[2] - w.eye[2]));
    toward = (Math.atan2(others[0][0] - w.eye[0], -(others[0][2] - w.eye[2])) * 180 / Math.PI + 360) % 360;
  }
  return {position: w.position, eye: w.eye, at_edge: w.atEdge, room: Boolean(g), on_walkable: on,
          walkable_m2: g ? g.cells * 0.01 : null, scan_points: g ? g.points.length : 1,
          free_min: free.length ? Math.min(...free) : 0, free_max: free.length ? Math.max(...free) : 0,
          freest: toward, units_per_m: w.scale, status: window.__vf.$('.vf-status').textContent};
}"""


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    from playwright.sync_api import sync_playwright
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8006")
    parser.add_argument("--shot", required=True, help="shot id of a dressed scan point that has a splat")
    parser.add_argument("--screens-dir", type=Path, default=ROOT / "cache/screens/walk")
    parser.add_argument("--executable", help="Installed Chromium executable")
    args = parser.parse_args()
    args.screens_dir.mkdir(parents=True, exist_ok=True)
    report, errors = {}, []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.executable, headless=True,
                                             args=["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda error: errors.append(f"pageerror: {str(error)[:300]}"))
        # A frame with no emptied plate answers 404 to the card's Strike lookup; that is not this check's subject.
        page.on("console", lambda m: errors.append(f"console: {m.text[:300]} @ {m.location.get('url', '')[-80:]}")
                if m.type == "error" and "/api/strike/" not in m.location.get("url", "") else None)
        page.add_init_script("addEventListener('unhandledrejection', (e) => console.error('unhandled rejection: '"
                             " + String(e.reason && (e.reason.stack || e.reason.message || e.reason))))")
        # Only the local server may be reached. Spark starts its sort worker from a blob: URL.
        local = (args.base_url, "blob:", "data:")
        page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(local) else route.abort())
        page.goto(args.base_url + "/app/", wait_until="networkidle")
        page.evaluate(OPEN, args.shot)
        page.wait_for_selector(".vf-walk:not([hidden])", timeout=15000)
        page.wait_for_timeout(700)
        page.keyboard.press("e")
        page.wait_for_selector("dialog.vf.is-walking", timeout=60000)
        page.wait_for_timeout(1000)
        start = page.evaluate(STATE)
        badge = page.evaluate("window.__vf.$('.vf-ai-badge').textContent")
        require("not the real room" in badge and "3D reconstruction" in badge, "walk mode lost the AI label")
        require(start["position"] == start["eye"], "the walk does not start at the scan point")
        page.screenshot(path=str(args.screens_dir / "start.png"))
        # Walk toward the most open direction (a whole room: toward the next scan point).
        page.evaluate("(yaw) => { const vf = window.__vf; vf.state.yaw = yaw; vf.view.yaw = yaw; }", start["freest"])
        page.keyboard.down("w")
        page.wait_for_timeout(3500)
        page.keyboard.up("w")
        page.wait_for_timeout(300)
        moved = page.evaluate(STATE)
        k = start["units_per_m"]
        walked = ((moved["position"][0] - start["eye"][0]) ** 2 + (moved["position"][2] - start["eye"][2]) ** 2) ** 0.5
        if start["room"]:
            require(start["on_walkable"] and moved["on_walkable"], "the camera left the walkable floor")
            require(walked > 1.0 * k, "W did not carry the camera toward the next scan point")
            require(page.evaluate("getComputedStyle(document.querySelector('.vf-walk-map')).display") == "block",
                    "the floor plan is not shown for a whole-room set")
        else:
            require(start["free_max"] < 0.3 * k or walked > 0.2 * k, "W did not move the camera")
            require(walked <= start["free_max"] + 0.01 and moved["at_edge"], "the camera walked past the set's limit")
        require(abs(moved["position"][1] - start["eye"][1]) < 1e-6, "eye height changed")
        page.screenshot(path=str(args.screens_dir / "walked.png"))
        if start["room"]:
            # Stand-ins: P brings on the cast, B adds one, each stands on walkable floor, P clears.
            page.keyboard.press("p")
            page.wait_for_function("(async () => (await import('/app/viewfinder-walk.js')).walkState(window.__vf).cast?.size > 0)()", timeout=20000)
            page.wait_for_timeout(1200)
            cast = page.evaluate("""async () => { const {walkState} = await import('/app/viewfinder-walk.js');
              const w = walkState(window.__vf), g = w.grid;
              const on = (m) => g.walk[Math.floor((m.z - g.minZ) / g.cell) * g.nx + Math.floor((m.x - g.minX) / g.cell)] === 1;
              return {size: w.cast.size, walkers: w.cast.members.filter(m => m.route).length, on_floor: w.cast.members.every(on),
                      animated: w.cast.members.filter(m => m.mixer).length, heights_m: w.cast.members.map(m => m.heightM),
                      shown: getComputedStyle(document.querySelector('.vf-cast')).display}; }""")
            require(cast["size"] == 5 and cast["walkers"] == 2 and cast["on_floor"], f"the default cast is wrong: {cast}")
            require(cast["animated"] == 5, f"the stand-ins are not the animated people: {cast}")
            require(all(1.6 <= h <= 1.85 for h in cast["heights_m"]) and cast["shown"] != "none", "stand-ins are not life size")
            page.screenshot(path=str(args.screens_dir / "stand-ins.png"))
            page.keyboard.press("b")
            page.wait_for_timeout(600)
            require(page.evaluate("(async () => (await import('/app/viewfinder-walk.js')).walkState(window.__vf).cast.size)()") == 6,
                    "B did not add a stand-in")
            page.keyboard.press("p")
            page.wait_for_timeout(300)
            require(page.evaluate("(async () => (await import('/app/viewfinder-walk.js')).walkState(window.__vf).cast.size)()") == 0,
                    "P did not clear the stand-ins")
        aspect = page.evaluate("window.__vf.state.aspect.id")
        page.keyboard.press("a")
        page.keyboard.press("d")
        require(page.evaluate("window.__vf.state.aspect.id") == aspect, "A changed the aspect while walking")
        require(page.evaluate("window.__vf.wipe") == 1, "D toggled the dressing while walking")
        page.keyboard.press("g")
        page.wait_for_timeout(300)
        shot = page.evaluate("window.__vf.shots[0] && {ai: window.__vf.shots[0].ai, size: window.__vf.shots[0].thumb.length}")
        require(shot and shot["ai"] and shot["size"] > 1000, "a frame grabbed in the set is missing or unlabelled")
        page.keyboard.press("e")
        page.wait_for_timeout(900)
        require(not page.evaluate("window.__vf.dialog.classList.contains('is-walking')"), "E did not leave the set")
        page.keyboard.press("e")
        page.wait_for_selector("dialog.vf.is-walking", timeout=20000)
        page.keyboard.press("Escape")
        page.wait_for_timeout(900)
        closed = page.evaluate("({open: window.__vf.dialog.open, canvases: document.querySelectorAll('.vf-walk-canvas').length})")
        require(closed == {"open": False, "canvases": 0}, "closing left the walk canvas behind")
        # The direct link opens the scan point and steps inside without a scout.
        page.goto(args.base_url + "/app/#walk=" + args.shot, wait_until="networkidle")
        page.reload(wait_until="networkidle")
        page.wait_for_selector("dialog.vf.is-walking", timeout=60000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(args.screens_dir / "linked.png"))
        # On a card, the frame offers the walk itself: one press opens the room and steps inside.
        page.goto(args.base_url + "/app/", wait_until="networkidle")
        page.reload(wait_until="networkidle")
        page.evaluate(CARD, args.shot)
        page.wait_for_selector(".shot-stage > .vf-walk-open", timeout=10000)
        page.wait_for_selector(".shot-stage > .vf-open", timeout=10000)
        page.screenshot(path=str(args.screens_dir / "card.png"))
        page.click(".shot-stage > .vf-walk-open")
        page.wait_for_selector("dialog.vf.is-walking", timeout=60000)
        if start["room"]:
            page.wait_for_selector(".vf-cast.is-active", timeout=20000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(args.screens_dir / "card-walk.png"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(900)
        # Look around on the same frame afterwards opens the 360° view, not the walk.
        page.click(".shot-stage > .vf-open")
        page.wait_for_selector(".vf-walk:not([hidden])", timeout=15000)
        page.wait_for_timeout(1200)
        require(not page.evaluate("document.querySelector('dialog.vf').classList.contains('is-walking')"),
                "Look around stepped into the set without being asked")
        require(not errors, f"browser errors: {errors[:3]}")
        report.update(walked_m=round(walked / k, 2), world_units_per_m=round(k, 3), chromium_version=browser.version)
        if start["room"]:
            report.update(scan_points=start["scan_points"], walkable_m2=round(start["walkable_m2"], 1))
        else:
            report.update(free_min_m=round(start["free_min"] / k, 2), free_max_m=round(start["free_max"] / k, 2))
        browser.close()
    print(json.dumps({"ok": True, **report}, indent=2))


if __name__ == "__main__":
    main()
