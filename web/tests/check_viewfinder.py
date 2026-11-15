"""Check the viewfinder in local Chromium without a model call or new scout.

Default: explicitly controlled synthetic faces, on a MOCK application server.
--real-index: existing private index and actual /api/sweep responses, on LIVE mode.
All non-local browser requests are blocked. Reports/images stay in ignored cache/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def source_pair(real):
    if real:
        index = ROOT / "cache/shot-index"
        if (index / "CURRENT").is_file():
            index /= (index / "CURRENT").read_text().strip()
        shots = json.loads((index / "shots.json").read_text())
        shots = shots["shots"] if isinstance(shots, dict) else shots
        first = next(shot for shot in shots if shot["heading_deg"] == 0)
        second = next(shot for shot in shots if shot["heading_deg"] == 0
                      and (shot["model_id"], shot["sweep_id"]) != (first["model_id"], first["sweep_id"]))
        return [first, second], {}
    sweeps = {}
    for scan in ("a", "b"):
        faces = [{"heading_deg": heading, "shot_id": f"viewfinder-check-{scan}-{heading}",
                  "image_path": f"/cache/views/viewfinder-check-{scan}-{heading}.jpg"}
                 for heading in (0, 90, 180, 270)]
        sweeps[faces[0]["shot_id"]] = {
            "shot_id": faces[0]["shot_id"], "model_id": "fixture-model", "sweep_id": scan,
            "property_id": "fixture-property", "heading_deg": 0, "depth_m": None,
            "ceiling_m": None, "room_area_m2": None, "measure_on_site": True, "faces": faces}
    return [sweep["faces"][0] for sweep in sweeps.values()], sweeps


def install_harness(page, base, pair, label):
    page.goto(base + "/app/", wait_until="networkidle")
    page.evaluate("""async ([pair,label]) => {
      const {Viewfinder} = await import('/app/viewfinder.js');
      const original = Viewfinder.prototype.open;
      Viewfinder.prototype.open = function(...args) {
        window.__checkedViewfinder = this;
        if (!this.dialog.querySelector('.check-label')) {
          const banner = document.createElement('small'); banner.className='check-label';
          banner.textContent=label;
          banner.style.cssText='position:absolute;bottom:0;left:4px;z-index:5;background:#111;color:#fff;font:10px sans-serif';
          this.dialog.append(banner);
        }
        return original.apply(this,args);
      };
      for (const [i,s] of pair.entries()) {
        const stage=document.createElement('div'); stage.className='shot-stage'; stage.id='vf-check-'+i;
        stage.style.cssText='position:relative;width:min(400px,calc(100vw - 40px));height:350px;margin:20px';
        const image=document.createElement('img'); image.className='shot-image'; image.src=s.image_path;
        image.alt='Browser check at Private scan '+(i+1);
        image.style.cssText='width:100%;height:100%;object-fit:contain';
        stage.append(image); document.body.prepend(stage);
      }
    }""", [pair, label])
    page.locator("#vf-check-0 .vf-open").wait_for()
    page.wait_for_function("[...document.querySelectorAll('[id^=vf-check] img')].every(i=>i.complete&&i.naturalWidth>0)")


def await_live(page, expected):
    page.wait_for_function("""id => {
      const vf=window.__checkedViewfinder;
      return vf?.dialog.open && vf.dialog.classList.contains('is-live') && vf.sweep.shot_id===id;
    }""", arg=expected, timeout=15000)
    page.wait_for_timeout(650)
    require(page.locator("dialog.vf.no-webgl").count() == 0, "Unexpected image-only fallback")
    # A room opens clean; these checks are about the camera frame, so bring it on.
    if page.locator("dialog.vf.is-clean").count():
        page.keyboard.press("f")
        page.wait_for_timeout(200)
    result = page.evaluate("""() => {
      const c=window.__checkedViewfinder.canvas, gl=c.getContext('webgl2');
      const p=new Uint8Array(4); gl.readPixels(c.width/2,c.height/2,1,1,gl.RGBA,gl.UNSIGNED_BYTE,p);
      return {context_lost:gl.isContextLost(),pixel:[...p]};
    }""")
    require(not result["context_lost"] and result["pixel"][3] == 255, "No rendered WebGL frame")
    return result


def close(page):
    page.locator(".vf-close").click()
    page.wait_for_function("!document.querySelector('dialog.vf').open")


def controls_inside(page):
    return page.locator(".vf-bottom button").evaluate_all("""buttons=>buttons.every(b=>{
      const r=b.getBoundingClientRect();
      return r.left>=0 && r.right<=innerWidth+1 && r.top>=0 && r.bottom<=innerHeight+1;
    })""")


def readout_clear(page):
    return page.evaluate("""() => document.querySelector('.vf-monitor').getBoundingClientRect().bottom
      <= document.querySelector('.vf-bottom').getBoundingClientRect().top""")


def main():
    from playwright.sync_api import sync_playwright
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8007")
    parser.add_argument("--screens-dir", type=Path, default=ROOT / "cache/screens/viewfinder")
    parser.add_argument("--executable", help="Installed Chromium executable")
    parser.add_argument("--real-index", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    require(urlsplit(base).hostname in {"localhost", "127.0.0.1"}, "Use a local server")
    require(args.screens_dir.resolve().is_relative_to((ROOT / "cache").resolve()), "Screenshots must remain private")
    args.screens_dir.mkdir(parents=True, exist_ok=True)
    pair, sweeps = source_pair(args.real_index)
    fixture_image = (ROOT / "mocks/img/mock-p2-s1.jpg").read_bytes() if not args.real_index else None
    report = {"passed": False, "mode": "real cached scans; no fresh scout" if args.real_index else "controlled MOCK faces",
              "checks": [], "page_errors": []}
    report_path = args.screens_dir / "viewfinder-report.json"
    report_path.write_text(json.dumps(report))
    label = "REAL CACHED SCAN - NO FRESH SCOUT" if args.real_index else "CONTROLLED UI CHECK - MOCK FACES"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.executable, headless=True)
            report["chromium_version"] = browser.version
            health = browser.new_context().request.get(base + "/health").json()
            require(health["mocks"] is not args.real_index, "Server mode does not match explicit check mode")

            def context(width=1440, height=900):
                result = browser.new_context(viewport={"width": width, "height": height})
                def route(request):
                    parsed = urlsplit(request.request.url)
                    if parsed.hostname not in {"localhost", "127.0.0.1"}:
                        return request.abort()
                    if not args.real_index and parsed.path.startswith("/api/sweep/"):
                        body = sweeps.get(unquote(parsed.path.rsplit("/", 1)[-1]))
                        return request.fulfill(status=200 if body else 404, json=body or {"detail": "Unknown fixture"})
                    if not args.real_index and parsed.path.startswith("/cache/views/viewfinder-check-"):
                        return request.fulfill(content_type="image/jpeg", body=fixture_image)
                    request.continue_()
                result.route("**/*", route)
                page = result.new_page()
                page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
                install_harness(page, base, pair, label)
                return result, page

            if args.real_index:
                sweep = browser.new_context().request.get(base + "/api/sweep/" + pair[0]["shot_id"])
                body = sweep.json()
                require(sweep.status == 200 and [f["heading_deg"] for f in body["faces"]] == [0, 90, 180, 270], "Real sweep API failed")
                require(body["model_id"] == pair[0]["model_id"] and body["sweep_id"] == pair[0]["sweep_id"], "Wrong real scan point")
                report["checks"].append({"name": "real_sweep_api", "faces": 4, "passed": True})

            ctx, page = context()
            for index in (0, 0, 1):
                page.locator(f"#vf-check-{index} .vf-open").click()
                frame = await_live(page, pair[index]["shot_id"])
                report["checks"].append({"name": "repeated_open", "scan": index, "passed": True, **frame})
                close(page)
            page.locator("#vf-check-0 .vf-open").click()
            await_live(page, pair[0]["shot_id"])
            page.locator('.vf-lenses [data-lens="35"]').click()
            page.locator('.vf-aspects [data-aspect="1.85"]').click()
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(650)
            page.locator(".vf-grab").click()
            require(page.locator(".vf-shot").count() == 1, "Grab did not save a frame")
            require(page.locator(".vf-shot-save").get_attribute("href").startswith("data:image/jpeg"), "No saved JPEG")
            page.locator('.vf-lenses [data-lens="14"]').click()
            page.locator(".vf-shot-recall").click()
            page.wait_for_timeout(650)
            require(page.locator('.vf-lenses [data-lens="35"]').get_attribute("aria-pressed") == "true", "Shot recall lost its lens")
            page.screenshot(path=str(args.screens_dir / "desktop.png"))
            report["checks"].append({"name": "lens_aspect_turn_grab_recall", "passed": True})
            ctx.close()

            ctx, page = context(390, 844)
            page.locator("#vf-check-0 .vf-open").click()
            await_live(page, pair[0]["shot_id"])
            require(controls_inside(page), "Mobile controls leave the viewport")
            require(readout_clear(page), "Mobile controls cover the camera readout")
            page.locator(".vf-grab").click()
            page.wait_for_timeout(650)
            require(controls_inside(page), "Mobile controls leave the viewport after grabbing")
            require(readout_clear(page), "Mobile controls cover the readout after grabbing")
            page.screenshot(path=str(args.screens_dir / "mobile.png"))
            report["checks"].append({"name": "mobile_controls_before_after_grab", "passed": True})
            ctx.close()

            ctx, page = context()
            page.evaluate("""id => {
              const native=window.fetch;
              window.fetch=async (...args)=>{
                const response=await native(...args);
                if(String(args[0]).endsWith('/api/sweep/'+encodeURIComponent(id)))
                  await new Promise(resolve=>setTimeout(resolve,1200));
                return response;
              };
            }""", pair[0]["shot_id"])
            page.locator("#vf-check-0 .vf-open").click()
            close(page)
            require(page.locator("#vf-check-0 .vf-open").evaluate("button=>button===document.activeElement"),
                    "Closing a loading viewfinder did not restore button focus")
            page.locator("#vf-check-1 .vf-open").click()
            await_live(page, pair[1]["shot_id"])
            page.wait_for_timeout(1500)
            require(page.evaluate("id=>window.__checkedViewfinder.sweep.shot_id===id", pair[1]["shot_id"]), "Dismissed response replaced the new scan")
            report["checks"].append({"name": "controlled_close_while_loading", "controlled": True, "passed": True})
            ctx.close()

            ctx, page = context()
            page.evaluate("""async () => {
              const {Viewfinder}=await import('/app/viewfinder.js'), open=Viewfinder.prototype.open;
              Viewfinder.prototype.open=function(...args){this.canvas.getContext=()=>null;return open.apply(this,args);};
            }""")
            page.locator("#vf-check-0 .vf-open").click()
            page.locator("dialog.vf.no-webgl").wait_for()
            require("can't draw" in page.locator(".vf-status").inner_text(), "No WebGL fallback status")
            close(page)
            report["checks"].append({"name": "controlled_no_webgl_fallback", "controlled": True, "passed": True})
            ctx.close()

            ctx, page = context()
            page.route("**/api/sweep/*", lambda route: route.fulfill(status=503, json={"detail": "Controlled outage"}))
            page.locator("#vf-check-0 .vf-open").click()
            page.locator("dialog.vf.no-webgl").wait_for()
            require("isn't available" in page.locator(".vf-status").inner_text(), "No unavailable-sweep status")
            close(page)
            report["checks"].append({"name": "controlled_api_failure", "controlled": True, "passed": True})
            ctx.close()
            require(not report["page_errors"], "Browser JavaScript exception")
            browser.close()
            report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"passed": report["passed"], "checks": len(report["checks"]), "report": str(report_path.resolve())}))


if __name__ == "__main__":
    main()
