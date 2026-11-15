"""Render real API response images in Chromium; keep screenshots private.

Run with a separate Playwright environment; no app dependency is required.
Tests browser image loading, not the independently owned viewer UI.
"""
import argparse
from html import escape
import json
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def response_images(result):
    if result.get("source_mode") != "live" or len(result.get("picks", [])) != 3:
        raise RuntimeError("Expected a live response with three source-backed picks")
    images = []
    for pick in result["picks"]:
        shots = pick.get("shots") or []
        aerial = pick.get("logistics", {}).get("aerial_image_path")
        if not shots or not aerial:
            raise RuntimeError("Every demo pick needs interior frames and a Vexcel aerial")
        images.extend(("Matterport interior", shot["image_path"]) for shot in shots)
        images.append(("Vexcel annotated aerial", aerial))
    return images


def image_url(base, image):
    if not isinstance(image, str):
        raise RuntimeError("Expected a private cache image path")
    parsed = urlsplit(image)
    decoded = unquote(parsed.path).lstrip("/")
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or not decoded.startswith("cache/") or "\\" in decoded
            or any(part in {".", ".."} for part in PurePosixPath(decoded).parts)):
        raise RuntimeError("Unexpected non-cache image path")
    return base.rstrip("/") + "/" + parsed.path.lstrip("/")


def main():
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--responses", type=Path, default=ROOT / "cache/demo-checks")
    parser.add_argument("--executable", help="Optional installed Chromium executable")
    args = parser.parse_args()
    if urlsplit(args.base_url).hostname not in {"localhost", "127.0.0.1"}:
        parser.error("Use the local application origin")
    if not args.responses.resolve().is_relative_to((ROOT / "cache").resolve()):
        parser.error("Demo responses must stay in private cache")
    responses = sorted({*args.responses.rglob("*.response.json"),
                        *args.responses.rglob("*.refine.json")})
    if not responses:
        parser.error("No saved API responses")
    report = []
    report_path = args.responses / "browser-report.json"
    # A failed rerun must not leave an earlier all-success report in place.
    report_path.write_text("[]\n")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.executable, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(args.base_url + "/docs")
        for path in responses:
            row = {"response": str(path.resolve().relative_to((ROOT / "cache").resolve())),
                   "engine": "unknown", "images_loaded": 0, "failed": 1}
            report.append(row)
            try:
                result = json.loads(path.read_text())
                row["engine"] = result.get("engine", "unknown")
                cards = []
                for label, image in response_images(result):
                    source = image_url(args.base_url, image)
                    cards.append(f'<figure><img src="{escape(source, quote=True)}"><figcaption>{label}</figcaption></figure>')
                page.set_content('<style>body{background:#17191d;color:#eee;font:16px sans-serif}main{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}figure{margin:0}img{width:100%;height:260px;object-fit:contain;background:#24262b}figcaption{padding:6px}</style><h1>Typecast real-frame browser verification</h1><main>' + ''.join(cards) + '</main>')
                page.wait_for_function("[...document.images].every(i => i.complete)", timeout=30000)
                sizes = page.locator("img").evaluate_all("images => images.map(i => [i.naturalWidth,i.naturalHeight])")
                if not sizes or any(width <= 0 or height <= 0 for width, height in sizes):
                    raise RuntimeError("A real API image failed to decode in Chromium")
                page.screenshot(path=str(path.with_suffix(".browser.png")), full_page=True)
                row.update(images_loaded=len(sizes), failed=0)
            except Exception as error:
                row["error_type"] = type(error).__name__
                raise
            finally:
                report_path.write_text(json.dumps(report, indent=2))
        browser.close()
    print(json.dumps({"responses": len(report), "images_loaded": sum(r['images_loaded'] for r in report), "failures": 0}))


if __name__ == "__main__":
    main()
