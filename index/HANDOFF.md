# Owner 1 integration handoff

Implementation branch: lane-a. Review PR #6 into dev together with Windows compatibility PR #8. Owner 3 is integration captain; neither dev nor main has been merged by this handoff.

## Completed and verified
- Real Matterport ingestion and CLIP cosine retrieval: 608 views / 19 catalog-linked properties; text queries change order; example matching excludes source property and model.
- Resumable validated images, atomic index generations, strict geometry filters and unknown/estimated fit handling.
- Room evidence: 600 assignments, 488 ceiling estimates, 25 validated room polygons covering 164 indexed scan views.
- Cinematic query briefs and MMR shortlist with hard property/scan diversity caps.
- Local lens/FOV and room-clearance planning, observed-ID SDK scan navigation, live viewer FOV and SDK pose capture.
- Scene lookbook export as self-contained HTML or editable JSON.
- Blinded review UI with 20 fixed scenes (15 test, 5 tune); attributed labels and pooled recall metrics separated by human/AI and live/mock.
- 76 index tests pass. Combined with dev 3514a61 and PR #8: 186 tests plus API smoke, streaming progress, cached refinement and no-send approval pass. Latest implementation CI at 512d1b8 is green.

## Run on another machine

```sh
git clone https://github.com/Tecncentral/typecast.git
cd typecast
git switch lane-a
python -m venv .venv
# Activate the virtual environment for your OS.
python -m pip install -r requirements.lock.txt -r index/requirements.txt
```

Obtain the private Typecast-Owner1-Team.zip from the team and extract into the repo root. It includes the prebuilt index, 608 images, provenance, catalog/model pairs and room polygons, but no credentials. Alternatively set individual sponsor API credentials privately in .env and run:

```sh
python -m index.bootstrap --max-models 20 --max-sweeps 8
```

Set TYPECAST_USE_MOCKS=0 in the launching shell (PowerShell: $env:TYPECAST_USE_MOCKS='0'), then:

```sh
python -m uvicorn index.preview:app --host 127.0.0.1 --port 8765
```

Open http://localhost:8765/ . Use localhost for SDK access; the existing key does not allow 127.0.0.1 as a browser origin. An individual MATTERPORT_SDK_KEY is required for the SDK. Retrieval and prebuilt imagery work without it. See index/README.md for API and data details.

## Remaining human intervention

1. COMPLETE: all20 human/live reviews are saved (15 test/5 tune). Held-out pooled recall@10 is38.9% cosine /30.5% diverse. See index/EVALUATION.md. The following instructions are retained for future re-evaluation: Open http://localhost:8765/evaluate, enter actual reviewer name, choose Human review, load each scene, inspect all40 views, mark relevant views, and save the complete review. Empty relevance is valid. Repeat20 scenes and export labels. Do not tune on the15 held-out test scenes. /api/evaluation/metrics reports pooled recall, not exhaustive catalog recall. Human pooled retrieval metrics are now available; they are not exhaustive catalog accuracy.
2. Exact image-heading alignment is unverified. Selected-scan identity/navigation is verified, but cube-relative image heading is not a world/SDK camera bearing. Either validate orientation against the actual source view before promising a matched image angle, or retain the visible caveat. This is a technical verification item, not a requirement for the user to manually enter geometry.
3. Owner3 must inspect and integrate PRs #6 and #8, run scripts/verify.py, and check the full real-data flow. PR#9 is an independent draft audit test proposal; inspect it separately and discard obsolete URL-form expected failures.
4. Owner4 must integrate the local studio interactions/APIs into the final viewer. Owner2 must finish real property/aerial joins using literal costar_property_id from the shared catalog. These remain other lanes' responsibilities.
5. The team must rehearse the real end-to-end demo, prepare submission assets, and perform human submission. Those are not completed by Owner1 code.

## Honest demo limits

Geometry is estimated; no furniture/access/rigging collision certification. Missing room polygons stay unknown. SDK zoom may constrain requested FOV, so actual FOV is displayed. Lookbook selection is tab-local: export before refreshing. Public GitHub contains code/docs only; private images, embeddings, labels and keys are supplied separately. Shared Shot/search/check_shot contracts and root dependencies are unchanged.

## Producer workflow reliability pass (2026-11-15, base c549e66)
Goal: harden the producer decision memo (stale/unbound decisions, import races, unknown/negative money, storage opt-out, exporter safety). Done and verified; full detail, commands and limits in `docs/BUSINESS-ACCEPTANCE.md`. Files: `index/director-planning.js`, `producer-brief.js`, `director.js` (snapshot staleness), tests `index/tests/director-planning.test.cjs`, `planning-harness.cjs`, `browser_producer_check.py`, one added case in `director-audit.mjs`. Open: real-browser slow-file-read timing untested; no live-mode, routing or provider checks. Next: coordinator review and integration. Resume: `node --test index/tests/director-planning.test.cjs index/tests/director-audit.mjs`; `../typecast/.venv/Scripts/python.exe index/tests/browser_producer_check.py` (needs playwright + Chromium).
