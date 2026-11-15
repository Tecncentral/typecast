"""Clean-Chromium check of the producer decision workflow against a LOCAL static server.

SYNTHETIC: /api/production/plan is answered by this script with a fabricated MOCK-mode plan (placeholder ids), /image/*
with a 1x1 PNG. No real data, provider, routing or tile request is made; every non-localhost request is aborted.
Run with an environment that has playwright and a Chromium: python index/tests/browser_producer_check.py [--executable PATH]
"""
import argparse, functools, http.server, json, tempfile, threading
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1]
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


def cand(pid, sid):
    return {"eligible": True, "shot": {"shot_id": sid, "property_id": pid, "model_id": "m-" + pid, "sweep_id": "w-" + pid, "heading_deg": 10, "score": 0.4, "measure_on_site": True},
            "property": {"available": None, "availability_status": "unknown", "address": "SYNTHETIC " + pid}, "logistics": {"parking_status": "unknown", "estimated": True},
            "warnings": [{"source": "synthetic", "field": "dimensions", "status": "unknown", "message": "Dimensions unknown (synthetic)"}]}


def plan_for(body, first):
    scenes = body["scenes"]
    rows = [{"scene_id": s["id"], "property_id": first, "shot_id": "shot-" + first, "score": 0.5} for s in scenes]
    rejected = set(body.get("forbidden_property_ids") or [])
    pool = [p for p in ("P_A", "P_B") if p not in rejected]
    rows = [{**r, "property_id": pool[0], "shot_id": "shot-" + pool[0]} for r in rows]
    return {"mode": "mock", "scenes": [{"id": s["id"], "heading": s["heading"], "description": s["description"], "candidates": [cand(p, "shot-" + p) for p in pool]} for s in scenes],
            "plans": [{"assignments": rows, "uncovered_scene_ids": [], "company_moves": 0, "mean_similarity": 0.4, "property_ids": [pool[0]], "locations": 1}],
            "evaluated_subsets": 1, "optimal_within_pool": True, "pool_properties": pool, "trace": {"steps": []}, "events": []}


def main():
    from playwright.sync_api import sync_playwright
    ap = argparse.ArgumentParser(); ap.add_argument("--executable"); args = ap.parse_args()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(INDEX))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    results, external = [], []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))

    with sync_playwright() as pw, tempfile.TemporaryDirectory() as tmp:
        browser = pw.chromium.launch(executable_path=args.executable, headless=True)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        def route(r):
            url = r.request.url
            if not url.startswith(base):
                external.append(url); return r.abort()
            if "/api/production/plan" in url:
                body = json.loads(r.request.post_data); return r.fulfill(status=200, content_type="application/json", body=json.dumps(plan_for(body, "P_A")))
            if "/image/" in url:
                return r.fulfill(status=200, content_type="image/png", body=PNG)
            if "/app/" in url or "/api/" in url:
                return r.fulfill(status=404, body="")
            r.continue_()
        page.route("**/*", route)
        page.goto(base + "/director.html")
        page.fill("#script", "INT. KITCHEN - DAY | A kitchen.\nINT. OFFICE - DAY | An office.")
        page.click("#build"); page.wait_for_function("document.getElementById('status').textContent.includes('candidate plan')")
        page.evaluate("document.querySelectorAll('details').forEach(d=>d.open=true)")
        cost = lambda: page.inner_text("#costResult")
        dis = lambda: page.evaluate("document.getElementById('exportProducerJson').disabled||document.getElementById('exportProducerHtml').disabled")
        check("mock plan labelled MOCK on the cost card and export enabled", "MOCK PLAN" in cost() and not dis(), cost()[:200])

        page.click("#commercialRatePreset")
        check("sourced $957.58 shown to the cent", "$957.58/day" in cost() and "$958" not in cost(), cost()[:300])
        page.fill("#dailyScoutRate", "")
        page.select_option("#scoutBilling", "hourly")
        check("blank day rate in hourly mode still exports", not dis(), page.inner_text("#producerCaseStatus"))
        page.select_option("#scoutBilling", "daily"); page.fill("#dailyScoutRate", "957.58")

        page.fill("#producerDecision", "Shortlist P_A for both scenes")
        with page.expect_download() as d:
            page.click("#exportProducerJson")
        path = Path(tmp) / "case.json"; d.value.save_as(path); case = json.loads(path.read_text())
        check("exported JSON is projection, mock, not measured, bound to a fingerprint",
              case["plan"]["mode"] == "mock" and case["budget"]["result"]["measured"] is False and case["plan"]["fingerprint"].startswith("plan:") and case["plan"]["covered"] == 2)
        check("decision bound to this plan raises no unbound-decision warning", not any("Reviewer decision" in u for u in case["plan"]["unknowns"]), str(case["plan"]["unknowns"]))

        # Reject -> in-flight replan: export must be disabled until the new plan arrives, and stay disabled after clearing rejections.
        page.unroute("**/*")
        pending = []
        def hold(r):
            url = r.request.url
            if "/api/production/plan" in url:
                pending.append(r); return
            route(r)
        page.route("**/*", hold)
        page.click("#reject")
        page.wait_for_timeout(200)
        check("export disabled while a replan after a rejection is in flight", dis())
        body = json.loads(pending[0].request.post_data); pending[0].fulfill(status=200, content_type="application/json", body=json.dumps(plan_for(body, "P_B")))
        page.wait_for_function("document.getElementById('status').textContent.includes('candidate plan')")
        page.wait_for_timeout(100)
        with page.expect_download() as d2:
            page.click("#exportProducerJson")
        d2.value.save_as(path); case2 = json.loads(path.read_text())
        check("after the replan the memo is a different, current plan and flags the earlier decision text",
              case2["plan"]["fingerprint"] != case["plan"]["fingerprint"] and any("earlier plan" in u for u in case2["plan"]["unknowns"]), str(case2["plan"]["unknowns"]))
        page.click("#clearRej"); page.wait_for_timeout(100)
        check("clearing rejections without a rebuild disables export", dis())

        # Literal storage opt-in / clear.
        page.check("#keepProducerCase")
        key = "typecast-producer-budget-v1"
        has = lambda: page.evaluate(f"localStorage.getItem('{key}')!==null")
        check("opt-in writes the browser copy", has())
        page.click("#clearProducerCase")
        check("clear removes it and unchecks the box", not has() and not page.is_checked("#keepProducerCase"))
        page.fill("#cost_crew", "9"); page.wait_for_timeout(100)
        check("later edits do not recreate it", not has())

        # Import: file lacks crew -> unknown, requires rebuild.
        page.fill("#cost_crew", "7")
        imp = Path(tmp) / "import.json"; c = json.loads(path.read_text()); c["budget"]["assumptions"].pop("crew", None); imp.write_text(json.dumps(c))
        page.set_input_files("#importProducerJson", str(imp)); page.wait_for_timeout(300)
        check("import of a case lacking crew leaves it blank, not the previous project's 7", page.input_value("#cost_crew") == "")
        check("import never enables an export by itself", dis())
        browser.close()
    server.shutdown()
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed; blocked external requests: {sorted(set(external))}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
