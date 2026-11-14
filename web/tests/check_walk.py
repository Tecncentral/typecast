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
STATE = """async () => {
  const {walkState} = await import('/app/viewfinder-walk.js');
  const w = walkState(window.__vf), free = Array.from(w.free || []);
  return {position: w.position, eye: w.eye, at_edge: w.atEdge, free_min: Math.min(...free), free_max: Math.max(...free),
          freest: free.indexOf(Math.max(...free)) * 4, status: window.__vf.$('.vf-status').textContent};
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
        page.on("console", lambda m: errors.append(f"console: {m.text[:300]} @ {m.location.get('url', '')[-80:]}")
                if m.type == "error" else None)
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
        # Walk toward the most open direction until the set's limit stops the camera.
        page.evaluate("(yaw) => { const vf = window.__vf; vf.state.yaw = yaw; vf.view.yaw = yaw; }", start["freest"])
        page.keyboard.down("w")
        page.wait_for_timeout(3500)
        page.keyboard.up("w")
        page.wait_for_timeout(300)
        moved = page.evaluate(STATE)
        walked = ((moved["position"][0] - start["eye"][0]) ** 2 + (moved["position"][2] - start["eye"][2]) ** 2) ** 0.5
        require(start["free_max"] < 0.3 or walked > 0.2, "W did not move the camera")
        require(walked <= start["free_max"] + 0.01 and moved["at_edge"], "the camera walked past the set's limit")
        require(abs(moved["position"][1] - start["eye"][1]) < 1e-6, "eye height changed")
        page.screenshot(path=str(args.screens_dir / "walked.png"))
        aspect = page.evaluate("window.__vf.state.aspect.id")
        page.keyboard.press("a")
        page.keyboard.press("d")
        require(page.evaluate("window.__vf.state.aspect.id") == aspect, "A changed the aspect while walking")
        require(page.evaluate("window.__vf.wipe") == 1, "D toggled the dressing while walking")
        page.keyboard.press("g")
        page.wait_for_timeout(300)
        shot = page.evaluate("window.__vf.shots[0] && {ai: window.__vf.shots[0].ai, size: window.__vf.shots[0].thumb.length}")
        require(shot and shot["ai"] and shot["size"] > 3000, "a frame grabbed in the set is missing or unlabelled")
        page.keyboard.press("e")
        page.wait_for_timeout(900)
        require(not page.evaluate("window.__vf.dialog.classList.contains('is-walking')"), "E did not leave the set")
        page.keyboard.press("e")
        page.wait_for_selector("dialog.vf.is-walking", timeout=20000)
        page.keyboard.press("Escape")
        page.wait_for_timeout(900)
        closed = page.evaluate("({open: window.__vf.dialog.open, canvases: document.querySelectorAll('.vf-walk-canvas').length})")
        require(closed == {"open": False, "canvases": 0}, "closing left the walk canvas behind")
        require(not errors, f"browser errors: {errors[:3]}")
        report.update(walked_m=round(walked, 2), free_min_m=round(start["free_min"], 2),
                      free_max_m=round(start["free_max"], 2), chromium_version=browser.version)
        browser.close()
    print(json.dumps({"ok": True, **report}, indent=2))


if __name__ == "__main__":
    main()
