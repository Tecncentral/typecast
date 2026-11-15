# PR50 integration review (read-only)

Reviewer: W8. Date: 2026-11-15 (UTC). Mode: mock / offline. No provider calls, no `.env`, no private cache, no merge to `dev` or `main`, and no edits to `map-parking` or `ai/director-production-decisions`.

This file is the review. It does not change product code. The trial merge below lived only in a local worktree and was not pushed.

## Commits and trees

| Role | Commit | Tree | Note |
| --- | --- | --- | --- |
| PR #50 head tested | `9c334aa21d928b23d0b3cc32fcb9779cdb48848f` | `848ddf8f0f43cbdb147d6af922816b7763718051` | `map-parking`. Includes parking (`222b8ce`) and seam repair (`9c334aa`). |
| PR #43 SHA requested | `c549e66beb91c5fa46c34f2f0fd0b92377f3a570` | `b11a05788241924e21a80434c1335fa9db7c6989` | Branch `ai/director-production-decisions` at the assigned base. |
| Merge base | `dd9a603019fecec7c732745bee3370e10032e349` | (not re-hashed here) | This is also `origin/dev` (`Merge pull request #49`). |
| Trial-merge tree tested | not a commit | `e2acf6838649cc6f2d5dc38b6fed3fd92c61c6c1` | `git write-tree` after keeping both sides of the single docs conflict. Not committed, not pushed. |
| Open PR #43 head at review time | `dd6223c6b806d6e6dd4e82fdcba3cdca048fbf75` | `c2bd0c970aac07791797555ff4196ee1720f21e6` | One docs commit after `c549e66` (`docs/EXTERNAL-AI-WORK.md`). Full suite on this SHA was **not** run. |

`git merge-tree` of `dd6223c` with `9c334aa` still conflicts only in `docs/team/CONTRACT-CHANGES.md`.

GitHub check on the PR #50 head: `verify (3.13)` SUCCESS, run `43684910190`, completed `2026-11-15T06:20:15Z`. CodeRabbit and Sourcery were skipped. This agent re-ran the gate on Python 3.12.3, not 3.13.

## Commands and results

Environment: Python 3.12.3 venv at `/tmp/typecast-venv`, installed from `requirements.lock.txt` (system Python had no pytest; `python3-venv` was unavailable, so `virtualenv` created the venv). Node v22.23.4. `TYPECAST_USE_MOCKS=1`. `scripts/verify.py` also forces the fixed engine and blanks model/tracing keys.

### PR #50 alone (`/workspace` at `9c334aa`)

```text
TYPECAST_USE_MOCKS=1 /tmp/typecast-venv/bin/python scripts/verify.py
```

Observed: `693 passed in 17.05s`. Smoke PASS (SSE, same-thread refine, `sent=false` approval). Mock E2E PASS. Eval: 20 attempted, 20 succeeded, 0 labeled, recall@10 N/A, source mode mock. Exit 0.

```text
node --test --test-reporter=spec \
  bridge/core.test.mjs web/tests/lib.test.mjs web/tests/parking.test.mjs \
  web/tests/viewfinder.test.cjs web/tests/cast.test.mjs \
  index/tests/director-project.test.cjs index/tests/director_reel.test.js \
  index/tests/director-audit.mjs index/tests/pr30-regressions.mjs
```

Observed: 141 tests, 140 pass, 0 fail, 1 skip, exit 0. The skip is `director-audit.mjs`: "No display, microphone, or browser HTML parser in this vm."

### Trial merge onto `c549e66`

```text
git worktree add --detach /tmp/typecast-merge c549e66
git merge --no-commit --no-ff 9c334aa
```

Merge exit 1. One unmerged path. README and `web/index.html` auto-merged. Local resolution kept both contract sections (PR #43 block, then the PR #50 crew-vehicles block), `git add` of that file only, no commit. Tested tree `e2acf6838649cc6f2d5dc38b6fed3fd92c61c6c1`.

```text
TYPECAST_USE_MOCKS=1 /tmp/typecast-venv/bin/python scripts/verify.py
```

Observed: `708 passed in 17.07s`. Same smoke, E2E, and unlabeled eval PASS. Exit 0. The extra passes are PR #43 tests that PR #50 does not contain. No semantic failure showed up in the gate.

```text
node --test --test-reporter=spec \
  bridge/core.test.mjs web/tests/lib.test.mjs web/tests/parking.test.mjs \
  web/tests/cast.test.mjs web/tests/viewfinder.test.cjs \
  index/tests/director-project.test.cjs index/tests/director_reel.test.js \
  index/tests/director-audit.mjs index/tests/pr30-regressions.mjs \
  index/tests/director-checks.test.cjs index/tests/producer-brief.test.cjs \
  index/tests/production-costs.test.cjs
```

Observed: 265 tests, 264 pass, 0 fail, 1 skip (same browser-surface skip), exit 0.

`index/commute.py` and `index/scene_customization.py` blobs in the trial-merge index match `c549e66` (`7ddb03a99de2d00718a26f7bcfaa5bc058460928` and `309c4c5cab94cf49c9b7cecda3e1aa09527749b2`). PR #50 does not contain those paths. They were not edited.

## Textual conflict

Only `docs/team/CONTRACT-CHANGES.md`.

Unmerged markers in the `c549e66` + `9c334aa` worktree, before the local docs resolution:

- `docs/team/CONTRACT-CHANGES.md:107` `<<<<<<< HEAD` (the `c549e66` side)
- `docs/team/CONTRACT-CHANGES.md:144` `=======`
- `docs/team/CONTRACT-CHANGES.md:159` `>>>>>>> 9c334aa`

Both sides appended a section after the same aerial-geometry paragraph. The `c549e66` side is the director project JSON / community / Save-the-scene contract notes. The `9c334aa` side is "Crew vehicles and CoStar recorded parking". No code line conflicted.

Auto-merged `web/index.html` in the tested tree:

- line 35: PR #43 masthead link `Plan production · commute & costs` to `/director`
- line 63: PR #50 warehouse placeholder (the police-station placeholder is gone)
- line 132: a single `id="map-section"`, moved above the refine section

`README.md` kept both the Business/Enterprise intro and the vehicle-only visual-order sentence.

Files changed on both sides since `dd9a603`: `README.md`, `web/index.html`, `docs/team/CONTRACT-CHANGES.md`. Everything else in PR #50 is additive relative to that base, including `agent/app.py`, `agent/pipeline.py`, `contracts/schemas.py`, `data/costar_parking.py`, `web/parking.js`, `web/map.js`, and `strike/seams.py`.

## Compatibility by surface

### Static serving

PR #50 wraps `/app` in `ViewerFiles` and sets `Cache-Control: no-cache` (`agent/app.py` `ViewerFiles.get_response`). `/mocks` stays plain `StaticFiles`. `/cache` stays `CachedImages`: image suffixes only, and any path part named `threads` or `outbox` is 404. `test_private_cache_paths_are_not_served` and `test_viewer_modules_always_revalidate` passed.

`/api/aerial/{property_id}` returns georeferencing only, `Cache-Control: no-store`, numeric ids, and rejects symlinks and mismatched bindings (`agent/aerial_metadata.py`, `agent/tests/test_aerial_metadata.py`). The PNG is still loaded from the existing `/cache` mount (`cache/vexcel/<id>/aerial.png`). Starlette 1.10 `StaticFiles.lookup_path` (default `follow_symlink=False`) realpaths the file and rejects a target outside the mount via `commonpath`.

PR #43's director routes (`index/production.py` `FileResponse`s for `director.js` and the other director modules) do not set `Cache-Control`. The merge keeps those routes. Director does import `/app/viewfinder.js` and `/app` CSS, which receive the new no-cache header. Director's own scripts do not. That is a pre-existing cache difference, not a failing test.

### `ScoutResponse.vehicles`

Additive and optional (`contracts/schemas.py` `Vehicles`, default `None`; `contracts/schemas.ts` optional). Fixed and deep engines set `trucks` and `cars` from the requirements actually checked. PR #43 does not construct this field. `agent/tests/test_runtime.py` still builds `ScoutResponse` without it, which remains valid. `Property.parking_spaces` defaults to `{}`. The merged gate, including PR #43 production tests, passed with the new field present.

### Refinement versus production constraints

Vehicle-only refine (`agent/pipeline.py` `refine`): if the parsed `explicit_fields` set is non-empty and a subset of `{trucks, cars}`, the saved shot order is kept and images are not re-scored. `_evaluate` / `_select` still drop failed shot fits and still rank by blocker count, then visual score. Parking shortfalls stay visible as blocked alternatives. A look or era change still re-scores. Covered by `test_vehicle_only_refine_keeps_saved_visual_order_without_rescoring`, which passed on both trees.

PR #43 drive limits and rejections are a different session. `index/production.py` filters on `commute` (OSRM estimate, unknown routes excluded) and `forbidden_property_ids`. `index/director.js` drops a rejected location even when replan fails. PR #50 does not modify those files. `/refine` does not read the director forbidden list or the commute pin, and the production planner does not call scout refine. Merging does not make one honor the other, and it does not make either overwrite the other. No test encoded a cross-UI expectation that then failed.

W7, per `docs/EXTERNAL-AI-WORK.md` on `dd6223c`, is assigned `index/commute.py`, `index/scene_customization.py`, and must report any essential `production.py` change. Those files are untouched by PR #50. No W7 branch was in the fetched remotes; that diff was not reviewed and was not modified.

### Source modes

`TYPECAST_USE_MOCKS` defaults to `1`. Recorded CoStar stalls are attached only in `data/costar_tools.py` `_live()`, from `cache/costar-parking.json`, and a missing or malformed file yields `{}`. Live Vexcel logistics read `cache/vexcel/<id>/logistics.json` and do not fall back to fixtures. The aerial route reads that cache and does not call the provider. This review issued no live CoStar, Vexcel, OSRM, or model call. `python -m strike.seams` was not run; that CLI calls an image model. The offline seam tests in `agent/tests/test_seams.py` passed inside `verify.py`.

### Licensed and private files

`git ls-files` on `9c334aa` has no `cache/`, `.env`, parquet, CoStar kit, or Vexcel PNG. `.gitignore` ignores `cache/` and `.env`. Tracked JPEGs under `mocks/img/` are generated placeholders (`scripts/make_mock_images.py` draws "SYNTHETIC MOCK FRAME" / "Not a real building photograph"). Fixture addresses end in `(FAKE)`. Leaflet UI icons are the other tracked PNGs.

The local server can still serve image bytes that exist under `cache/` to a client that can reach the process. That mount predates PR #50. Nothing in this review published that directory.

## Honesty of parking and nearby-lot figures

Reproduced with the committed helper, no server:

```text
node --input-type=module  # imports web/parking.js
```

Mock-shaped pick (`mock-p1`, `estimated: true`, polygon present, no `parking_area_m2`, no aerial): `fits` is `null`, verdict `Nearby lot size unknown`, lot text `No usable lot outline`. It does not invent a car-space count. `vehiclesOf` on a response that includes `vehicles` reports the requested trucks and cars as known.

Cached-shaped pick (`parking_status: "estimated"`, area `2713.8`, Vexcel SAM3 claim, CoStar `{Surface: 10, Covered: 600}`, demand 5 trucks + 10 cars): capacity `90`, demand `30` (`5*4+10`), `fits: true`, status `estimated`, verdict `Lot covers 5 trucks + 10 cars`, lot text `Nearby Vexcel-segmented lot ≈2,714 m² · ≈90 car spaces (est.)`, recorded line `CoStar record: 10 surface + 600 covered spaces`.

What a Business/Enterprise reader can trust:

- Lot capacity is `floor(area / 30)` car equivalents, one truck = four, same rule as `data/vexcel_tools.py`. Precompute stores `parking_status: "estimated"`. The bar caption says nearby, approximate, and `(est.)`. Unknown area, a sliver under 30 m², unknown status, or unknown crew cars do not become a fit (`web/tests/parking.test.mjs`).
- CoStar stalls are a separate recorded line. They are not added to the traced-lot capacity. The pipeline caveat (surface stalls below truck demand, counted as car equivalents) is a skeptic note, not a blocker, and says "about" and "confirm truck access". Covered stalls are not treated as truck parking.
- Mock properties and frames are labelled fake/synthetic. The page badge says `MOCK MODE` when `/config` reports mock.

What is less careful:

- `web/map.js` subtitle always says the demand was checked against "the nearest lot traced on each Vexcel aerial", and the Leaflet control always adds `Aerials © Vexcel`, including when the pick has no aerial and the id is not a cached numeric property. That copy does not read source mode. In mock mode the numbers stay unknown; the attribution is ahead of the evidence on screen.
- The short verdict `Lot covers …` and the legend keys "Lot fits the crew" / "Lot too small" do not themselves say "estimate". The adjacent lot caption does.
- The CoStar evidence item uses status `measured` because `item()` defaults to that for a supplied CoStar value (same tag as year built and parking flags). The sentence says "CoStar records …". The card's parking row follows logistics status and appends "estimate" when the lot is estimated.

No figure in the tested mock path is presented as a surveyed stall count. Cached figures are estimates plus a recorded CoStar extract, and the code keeps those apart. This review did not open a private cache, so it did not check a real aerial or a real `costar-parking.json`.

## Merge order

1. Land W7 onto `ai/director-production-decisions` first, while its diff stays in `index/commute.py`, `index/scene_customization.py`, and any `index/production.py` edits it reports. PR #50 does not touch those files, so this does not fight the parking diff. W7's branch was not in the fetched remotes; re-check if its file list grows into `web/`, `agent/pipeline.py`, `contracts/`, or `docs/team/CONTRACT-CHANGES.md`.
2. Merge PR #50 (`9c334aa`) into that updated PR #43 head. Expect the same docs conflict. Keep both appended sections. Re-run `TYPECAST_USE_MOCKS=1 python scripts/verify.py` and the Node files, including `director-checks.test.cjs`, `producer-brief.test.cjs`, and `production-costs.test.cjs`.
3. Do not merge either branch to `main`. `origin/dev` is still `dd9a603`. Neither PR is in `dev`.

Order is textually safe the other way only if W7's diff remains outside the files PR #50 edits. Doing W7 first matches the assignment (W7 is already based on `c549e66`) and avoids rebasing it across the docs conflict.

## Blockers and fix PR

No failing test was reproduced on `9c334aa` or on the trial merge. No isolated product fix or patch was opened.

Unexecuted: browser and OSM tiles, live provider calls, private Vexcel/CoStar cache, `python -m strike.seams`, the Python 3.13 CI image (GitHub already reported success for PR #50), a full `verify.py` on `dd6223c`, and W7's unpublished diff.
