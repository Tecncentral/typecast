# Typecast integration readiness review — v3 (lane-a `9284a86`, PR #6; PR #8)

Auditor: Grok Bot. Refreshed Sat Nov 14 2026, ~6:10 AM ET. Supersedes v2 (`fcc9a1d`, ~5:41 AM ET).
The user-reported head was `9a6fea1`; lane-a advanced to **`9284a86`** during this review, so that newer head is the one reviewed (`9a6fea1` results are kept for traceability).
GitHub was read-only: nothing was pushed, branched, commented, reviewed or merged. The PR #6 + PR #8 merge below
exists only in a local scratch worktree. No keys, private data, sponsor records or model weights were used, and there is
no `.env` on the auditing machine. No implementation files were edited; this change adds only `index/tests/_audit_helpers.py`,
`index/tests/test_audit_*.py` and this document.

Labels: **VERIFIED** = I ran it and saw the result. **USER-REPORTED** / **PR-REPORTED** = a claim I did not verify.

## 1. SHAs (last fetched 6:06 AM ET)

| Ref | SHA |
|---|---|
| `origin/lane-a` = PR #6 head (**reviewed**) | `9284a86ce2b81f4beb9e1855fa07f7ae55a9f364` ("Record completed live bootstrap, browser evidence and integration handoff", 6:00 AM ET) |
| lane-a `9faab10` | "Normalize malformed catalog dimensions before schema validation" (5:55 AM ET) |
| lane-a `9a6fea1` (user-reported head) | `9a6fea1677c19ca8fd8b5bce15aa4119830dccfe` ("Resolve independent audit findings in validation, sampling and preview fallback", 5:53 AM ET) |
| lane-a `1b31e04` | "Harden recovery and add live-verified one-command teammate bootstrap" (5:48 AM ET) |
| prior review heads | `fcc9a1d` (v2), `d08103f` (v1) |
| PR #8 head = `origin/fix/windows-verification` | `dd51df85e696c1cb89cc939fb2a352b937b67e47` ("Support Windows local image paths and offline asyncio socketpairs", 5:51 AM ET) |
| `origin/dev` (base of PR #6 and PR #8) | **`3514a61790d37be3c68e2308074fec81fd50ec36`**: PR #7 (lane-c deep-engine/tracing) merged at 6:00 AM ET. It was `a89cbad` when both PRs were opened |
| `origin/lane-c` | `9ce4438` (merged via PR #7; agent code not reviewed in depth here) |
| `origin/lane-b` = `origin/lane-d` | `5a449bcc9952d038ce7b0de12a1d401099c62574` (unchanged; no lane work) |
| `origin/main` | `69286611f5ff5f3ec200fbcb83c0d6b2eda7bbf9` |
| Local scratch merges (never pushed) | `9a6fea1`+PR #8 = `004c36e`; `9284a86`+PR #8 = `e26b853`; new dev `3514a61`+`9284a86`+PR #8 = `faa8013` |

`fcc9a1d..9284a86` touches 15 files, +520/−40, all under `index/` plus `docs/team/status-lane-a.md`. New: `index/bootstrap.py`,
`index/tests/test_bootstrap.py`, `index/tests/test_preview.py`. Changed: `build.py`, `geometry.py`, `matterport.py`,
`preview.py`, `rooms.py`, `search.py` and tests. `9a6fea1..9284a86` adds catalog-dimension normalization *before* schema
validation (`index/search.py:119-131`), a status-message change and status docs. PR #8 touches `agent/eval/harness.py` (+8)
and `agent/rerank.py` (+3). The PRs share no files, and every local merge, including onto the new dev `3514a61`, was conflict-free.

## 2. PR status and CI (VERIFIED through the GitHub API, read-only)

**PR #6**: https://github.com/Tecncentral/typecast/pull/6 — open, not draft, lane-a → dev. 9 commits, 21 files, +3408/−47.
GitHub reported `mergeable: true`, `mergeable_state: clean` at 6:02 AM ET (after dev moved).
- **`9284a86`:**
  - `verify (3.13)` **success** at 6:01:01 AM ET: https://github.com/Tecncentral/typecast/actions/runs/43587919534/job/132426302855
  - `verify (3.13)` **success** at 6:01:05 AM ET: https://github.com/Tecncentral/typecast/actions/runs/43587925216/job/132426318744
- **`9faab10`:** verify success ×2 (5:56 AM ET).
- **`9a6fea1`:** verify success ×2 (5:53:52 and 5:54:05 AM ET):
  - https://github.com/Tecncentral/typecast/actions/runs/43587387763/job/132424698227
  - https://github.com/Tecncentral/typecast/actions/runs/43587391533/job/132424709643
- Sourcery skipped and CodeRabbit skipped on all three.
- **No new review comments** since v2. The last inline comments are from Codex/Sourcery on `08fae84`. Codex has not re-reviewed, and there is still no human review.
- The PR body was **updated** at 6:02 AM ET. It now states PR-REPORTED 608 views / 19 properties / 600 room assignments / 488 ceiling estimates, Chrome-rendered 2048 px images, a 0.04 s warm query and a 5.72 s first model load ("observations, not a benchmark"), 65 index tests, a combined gate with PR #8 of 139 tests, and "No human-labelled recall metric is claimed".

**PR #8**: https://github.com/Tecncentral/typecast/pull/8 "Fix Windows image reranking and offline verification" — open, not draft,
`fix/windows-verification` → dev (`a89cbad`). 1 commit, 2 files, +11/−0. GitHub reports `mergeable: true`, `clean`.
- `verify (3.13)` **success** at 5:52:18 AM ET: https://github.com/Tecncentral/typecast/actions/runs/43587271648/job/132424354667 (one run, not two)
- Sourcery success; CodeRabbit skipped. Codex: completed with **no findings**.
- **New Sourcery findings (open):**
  - 🟡 Medium, `agent/rerank.py:64`: UNC paths (`\\host\share\...`) are passed to `Path.resolve()` before the containment check. On Windows that can contact an attacker-chosen SMB host and leak NTLM credentials. Fix: reject UNC/device paths before resolving.
  - ⚪ Low, `agent/eval/harness.py:41`: the docstring should say that only CPython's internal fallback socketpair is allowed.
- PR body (PR-REPORTED): Windows/Python 3.13 against dev passes 97 tests, smoke, SSE and offline eval (0 labels).

## 3. Commands and exact observed output (VERIFIED, Linux, Python 3.13.5)

The venv is built from `requirements.lock.txt`. The optional CLIP stack (`index/requirements.txt`) is **not** installed, so the real
encoder never runs.

| # | Tree | Command | Observed |
|---|---|---|---|
| 1 | **`9284a86` clean** | `python -m pytest -q` | `139 passed in 3.89s` |
| 2 | `9284a86` clean | `python scripts/verify.py` | exit 0. `139 passed`. PASS mock search → validated picks → same-thread refinement → SSE result → no-send approval. First SSE event 3.22 ms, SSE result 8.62 ms. Search calls before/after refine `{'search_shots': 1, 'search_costar': 1}` both. PASS progress/refine/no-send. Eval: `20 attempted, 20 succeeded; 0 labeled scenes scored, 20 unlabeled skipped`, `recall@10: N/A`, p50 4.63 ms / p95 7.17 ms (mock fixtures, not a quality result) |
| 3 | `9284a86` clean | `python -m pytest -q index` | `65 passed in 0.44s` |
| 4 | `9284a86` + PR #8 (local merge `e26b853`) | `python -m pytest -q` / `index` / `verify.py` | `139 passed` / `65 passed` / exit 0, both PASS, `0 labeled`, `recall@10: N/A`, p50 4.40 / p95 5.71 ms |
| 5 | new dev `3514a61` + `9284a86` + PR #8 (`faa8013`) | `python -m pytest -q`; `verify.py` | `175 passed`; exit 0, both PASS, first SSE 2.31 ms, SSE result 11.63 ms, `0 labeled`, `recall@10: N/A` |
| 6 | `9a6fea1` clean (user-reported head) | `pytest -q` / `index` / `verify.py` | `134 passed` / `60 passed` / exit 0, both PASS, `0 labeled`, recall N/A. With PR #8 (`004c36e`): `134 passed`, verify exit 0 |
| 7 | `9284a86` + audit tests | `python -m pytest -q index/tests/test_audit_*.py` | **`180 passed, 1 xfailed`**, 0 failed, 0 skipped |
| 8 | same | `python -m pytest -q` | `319 passed, 1 xfailed` |
| 9 | same | `python -m pytest -q index` | `245 passed, 1 xfailed` |
| 10 | same | `python scripts/verify.py` | exit 0; `319 passed, 1 xfailed`; both PASS lines; `0 labeled`; recall@10 N/A |
| 11 | same | `python -m pytest -q --runxfail index/tests/test_audit_*.py` | `1 failed, 180 passed`. The failure is the URL-form test (reason correct) |
| 12 | `9284a86` + PR #8 + audit tests | `pytest -q`; `verify.py` | `319 passed, 1 xfailed`; exit 0 |
| 13 | new dev + `9284a86` + PR #8 + audit tests | `pytest -q`; `verify.py` | `355 passed, 1 xfailed`; exit 0 |
| 14 | **`fcc9a1d`** + the same audit tests | `pytest -q index/tests/test_audit_*.py` | `57 failed, 123 passed, 1 xfailed`. Every new regression fails on the v2 head, which proves it guards a real fix |
| 15 | **`9a6fea1`** + the same audit tests | same | `10 failed, 170 passed, 1 xfailed`. Only the non-numeric catalog-dimension cases fail; `9faab10` fixed them |
| 16 | `9284a86`, `TYPECAST_USE_MOCKS=1 uvicorn index.preview:app --port 8798` | curl | `GET /` 200. `/api/search?q=office` → mock, 15 views, 5 properties, 12 results. `/image/mock-p1-s0` **200 image/jpeg** (v2: 404). `?example=mock-p1-s0` 200. No params → 400. `?example=nope` → **503** (see N7) |

## 4. User-reported metrics (NOT verified by me)

None of these can be checked without the private cache, keys and the CLIP stack:
- One-command bootstrap verified live on 19 models
- 608 views
- **600 room matches, 488 ceiling estimates** (replaces the earlier 96/36)
- 0.04 s warm query
- 2048 px images
- Cross-property results

`docs/team/status-lane-a.md` (updated 10:59 UTC, 5:59 AM ET) and the updated PR #6 body carry the same 608/19/600/488 numbers. The PR body adds a 5.72 s first model load and a Chrome render.

**USER-REPORTED** combined local gate: 134 tests + smoke + SSE + offline eval. This matches my Linux run at `9a6fea1`+PR #8 (134). At the newer `9284a86`+PR #8 I observed **139**, which matches the PR body's figure. I could not reproduce the Windows half.
**No recall or quality metric is claimed.** There are 0 labelled scenes, so recall@10 is N/A.

## 5. Resolved / open versus v2

| # | v2 item | Status at `9284a86` | Evidence (audit tests are regressions unless marked xfail) |
|---|---|---|---|
| 1 | Shared gate broken by `USE_MOCKS` | **RESOLVED** (since v2) | Runs 1–2; CI green |
| 1b | Two `TYPECAST_USE_MOCKS` parsers (Sourcery High) | **RESOLVED** | `index/search.py:41` now uses `== "1"`, the same as `search.py:25`, `agent/runtime.py:28,52`, `data/costar_tools.py:11` and `data/vexcel_tools.py:6`. `test_index_mode_uses_exact_equals_one_contract` ×10 ('1' → mock; '0', 'true', 'TRUE', 'yes', 'on', '2', '', ' 1', '1 ' → live). `test_runtime_adapters_and_index_agree_on_source_mode` ×5 runs a fresh interpreter per value and checks that runtime, both adapters and the index agree |
| 2 | Property-id join and per-adapter modes (Owners 2/3) | **OPEN** | lane-b is still `5a449bc`; the data adapters' live mode still has no implementation |
| 3 | Manifest wiped on failed/partial rerun | **RESOLVED** | `index/matterport.py:717-727` merges prior records whose local image is still valid. Tests: `test_failed_rerun_preserves_previous_good_manifest`, `test_partial_rerun_keeps_previously_ingested_model_records` (old m1 records unchanged, no duplicates), new `test_preserved_records_require_valid_local_images` (deleted or corrupt images are not republished) |
| 4a | Direct invalid input → ValueError | **BY DESIGN, now covered by the owner** | `index/tests/test_geometry_evidence.py::test_reject_invalid_physical_inputs` now has True, False, 0, −1, nan, inf × 4 fields. I removed the duplicate audit cases |
| 4b | Direct bool input accepted | **RESOLVED** | `index/geometry.py:12` rejects bool (owner test above) |
| 4c | Rooms payload normalization | **RESOLVED** (since v2) | 9/9 audit cases pass |
| 4d | Build manifest dimensions not normalized | **RESOLVED** | `index/build.py` `_dimension`. 9 cases (0, −2.5, nan, inf, "abc", "", True, [], {}) → None **and** force `measure_on_site=True`. Valid numeric strings and numbers are kept |
| 4e | Catalog-row (`shots.json`) dimensions crash `check_fit` | **RESOLVED for on-disk catalogs** | `index/search.py:119-131` (`9faab10`, before schema validation) and `:136-146` (after). 6 numeric cases (0, −, NaN, inf) plus 14 non-numeric cases (True, False, "3.1m", "unknown", "", [], {} × depth and area) → None, `measure_on_site`, status `unknown`. Other fields and other rows survive. A numeric string "3.25" is kept. A `Shot` built in memory and passed straight to `ShotRetrievalIndex(...)` is not normalized; that is a programmatic/direct input, consistent with the policy, and not tested as a defect |
| 5 | `TYPECAST_INDEX_DIR` ignored by reader (Codex P2) | **RESOLVED** | `index/search.py:430`; writer and reader roundtrip, and the default directory is not created |
| 6 | Malformed `row_count` escapes raw | **RESOLVED** | 7 cases ("two", "2", [2], {}, True, 2.0, mismatch) → `IndexUnavailableError` |
| 7 | Importer/builder id rules disagree | **RESOLVED** | `index/build.py:39` = `index/matterport.py:65`. 10 ids are accepted by both or rejected by both (dots, 128/129 chars, leading `.`/`-`, `..`, `/`, space, empty) |
| 8 | Fixture vs built image URL forms differ | **OPEN** (only xfail) | `mocks/shot.json` uses `mocks/img/...`; `index/build.py:69` uses `/cache/views/...` |
| 9 | Unauthenticated `/cache` mount and preview | **OPEN** (partly mitigated) | `agent/app.py:213` (new dev) still mounts `/cache`. The preview is containment-checked, `no-store`, and bound to 127.0.0.1 by convention only |
| 10 | `agent/pipeline.py:66-67` turns estimates into "tight" | **OPEN, more likely to trigger now** | Still present on the new dev `3514a61` (`agent/pipeline.py:67-68`). With **488 ceiling estimates**, any row that also gets a depth estimate shows "tight" instead of "unknown". The index's own `check_shot` returns unknown (tested). Owner 3 |
| 11 | Cube-local headings | **Improved, still OPEN** | Rooms enrichment now records the provider `anchor_id` and `source_rotation_quaternion` in provenance. Headings are still not validated tour poses |
| 12 | First-query model failure returns 500 | **RESOLVED** | `index/preview.py:19-20` → 503 without leaking details (audit test injects the failure inside the real encoder path; the owner test patches `search_shots`) |
| N1 | Sampling before readiness (Codex P2) | **RESOLVED** | `select_spread_panos` validates skybox readiness before spacing. Invalid panos are ordered last |
| N2 | Preview example-only → 422 | **RESOLVED** | 200; no `q` and no `example` → 400 |
| N3 | Preview mock mode had no images | **RESOLVED** | The image root follows the index mode: mock → only `mocks/img`, live → only `cache/views`. A cross-mode request is 404 (tested both ways). curl: 200 image/jpeg |
| N4 | Enrich/preview missing from documented build; provenance sidecar not generation-scoped | **Docs RESOLVED; sidecar OPEN** | `index/README.md:15,47,51` documents bootstrap, enrich and preview. `index/build.py` still writes `cache/view-provenance.json` outside the index generation |
| N5 | Windows harness/rerank | **FIX IN PR #8 (open, CI green on Linux)** | Windows not executed by me. New Sourcery Medium on PR #8 (UNC/SMB) is **OPEN** |
| N6 | (new) Preserved records survive model access revocation | **OBSERVATION** | The merge keeps prior records for a model that now returns 403. Images are retained locally. This is a data-handling decision for the owner (post-event deletion is already required) |
| N7 | (new) Preview maps every search exception to 503 | **LOW** | `?example=<unknown id>` returns 503 "Interior index unavailable or query invalid", not 404. Harmless, but a stale example link looks like an outage. Not added as a test because the contract is the owner's call |
| N8 | (new at `9a6fea1`) PR #6 body stale | **RESOLVED** | Body updated at 6:02 AM ET (§2) |
| N9 | (new) dev moved to `3514a61` (PR #7) under both PRs | **VERIFIED OK** | A local merge of new dev + PR #6 + PR #8 is conflict-free: 175 passed, verify exit 0; 355 passed, 1 xfailed with audit tests |

## 6. Audit test suite (7 files under `index/tests/`, rebased onto `9284a86`)

All tests run offline. They use an injected 3-axis fake encoder, fake GraphQL/CDN sessions, `tmp_path` caches and the FastAPI TestClient, plus one
subprocess per source-mode value (stdlib only, no network). Nothing reads the real `cache/`. The one xfail is `strict=True`.

| File | Covers | Pass | xfail |
|---|---|---|---|
| `_audit_helpers.py` | fake encoder, shots, generation writer, JPEG bytes, fake HTTP sessions, `pano()`/`panos_body()` (5 m spacing) | — | — |
| `test_audit_ordering.py` | query-dependent order, determinism, tie-break, filter before top-k, k ≤ 0, invalid requests, copies, dim mismatch | 15 | 0 |
| `test_audit_lookalike.py` | excludes source model/property; filter can't re-add; mock mode | 5 | 0 |
| `test_audit_dimensions.py` | unknown/estimated geometry never "fits"; rooms/build/catalog normalization (numeric and non-numeric); numeric strings kept; minimum filters | 45 | 0 |
| `test_audit_index_files.py` | absent/corrupt/pointer cases, row_count, live-no-index, store roundtrip, `TYPECAST_INDEX_DIR`, generation isolation, exact `==1` mode contract + cross-module agreement | 50 | 0 |
| `test_audit_provider_failures.py` | 14 GraphQL failures, retry policy, 401 report, 7 CDN failures, mixed models, sampling, readiness, manifest preservation ×3 | 33 | 0 |
| `test_audit_viewer_compat.py` | importer → build → contract shots, TS/Python parity, API mounts, URL rule, id agreement ×10, preview smoke (home, live search with context, example-only cross-building, 400, private image headers, traversal/missing/unknown 404, no-index 503, encoder 503, mode-scoped image root) | 32 | 1 |
| **Total** (verified per file) | | **180** | **1** |

Changes from v2:
- **22 xfails** for fixed cases (row_count, index dir, manifest ×2, id, sampling readiness, preview example-only, encoder 503, bool, build dims, and the parser ×4, which was rewritten to the exact contract) became regression tests.
- The 4 catalog-row xfails were retargeted from in-memory `Shot`s to an on-disk `shots.json` loaded by `from_cache_dir`, because that is where the owner normalizes. They now pass.
- **Removed as duplicates** of the owner's `test_geometry_evidence.py`: 16 direct-invalid cases and 4 bool cases.
- The separate example-only test was folded into the example search test.
- **Added:**
  - build valid-value preservation;
  - catalog non-numeric ×14 (bool, strings, list, object × depth/area; the owner's test covers ceiling);
  - catalog numeric string kept;
  - row_count bool, float, numeric-string and mismatch;
  - mode contract ×10 and cross-module agreement ×5;
  - preserved records require valid images;
  - partial-rerun no-duplicate check;
  - id agreement ×10;
  - empty request → 400;
  - mode-scoped image root.

**Remaining xfail (1):** `test_fixture_and_index_image_paths_use_same_url_form`. OPEN: fixture paths are repo-relative (`mocks/img/...`) while built paths are root-relative (`/cache/views/...`, `index/build.py:69`). A viewer page served under `/app/` resolves the fixture form incorrectly. With `--runxfail` it fails on exactly that assertion.

## 7. Dimension policy (as now implemented and tested)

1. **Direct invalid physical input → `ValueError`**: 0, negative, NaN, inf, True, False for depth, ceiling, focal length and frame width. Covered by the owner's test.
2. **Malformed provider/catalog dimensions → `None` + `measure_on_site=True` → fit `unknown`**, at all three entry points:
   - rooms payload (`index/rooms.py` `_positive_finite`);
   - import/enriched manifest (`index/build.py` `_dimension`);
   - on-disk catalog rows (`index/search.py` `_load_shots_file`).
   Since `9faab10`, non-numeric values (strings, bool, list, object) in `shots.json` are normalized too, rather than making the whole index unavailable.
3. **Estimated or partial geometry is never a verified fit** at the index (`check_shot`). The agent pipeline still has the "tight" override (item 10).

## 8. Readiness verdicts

| Scope | Verdict |
|---|---|
| **PR #6** | **Ready to integrate into dev** for fixture-mode stability and as the interior-search demo path. CI is green at `9284a86`, verify passes (also on top of the new dev), and every v2 Owner-1 finding except the URL form is fixed and regression-tested. Before merging, get one human review. |
| **PR #8** | **Ready to integrate** after addressing (or consciously accepting for the event) the Sourcery UNC/SMB Medium. It is small, Linux CI is green, and it merges cleanly with PR #6 (local merge: 134 passed, verify exit 0). Windows not verified by me. |
| Lane B / D | Not started on GitHub. Real joined picks still need Owner 2's matching `costar_property_id`. |
| Full scene → three cited real picks | **Not ready**: blocked on lane B. |

## 9. Checks NOT executed

- Live Matterport/GraphQL/CDN and `index.bootstrap` (no credentials, by design).
- Real CLIP weights: query quality, the 0.04 s warm query, cold load time and memory.
- The 608/19/600/488 numbers and 2048 px images.
- A browser render of the preview and the tour link (HTTP only).
- **Windows** (PR #8 claims and the user-reported Windows gate).
- The UNC/SMB behaviour itself.
- PR #7 (lane-c, now merged into dev `3514a61`), the deep engine and LangSmith traces. I ran only the shared offline gate on the merge.
- recall@10 (0 labels).
- DNS-rebinding and oversized-download Sourcery Mediums from v2 (not injected).
- Concurrent cold-start preview requests.

## 10. Two-minute demo (updated)

Prerequisites:
- On the demo laptop, run `index.preview` and `agent.app` on 127.0.0.1 with `TYPECAST_USE_MOCKS=0` for the preview. The flag must be exactly `1` or anything else; only `1` means fixtures.
- Pre-warm CLIP with one query.
- Record a backup video.
- If the live index fails, the preview now **works in fixture mode with images**: set `TYPECAST_USE_MOCKS=1` and say "fixtures" out loud.

| Time | On screen | Say | Fallback |
|---|---|---|---|
| 0:00-0:12 | Scene text | Scouts spend days finding a room that can play a scene | Slide |
| 0:12-0:45 | Preview: "bright kitchen with counters and cabinets"; status shows LIVE, view/property counts; 12 real frames | Real Matterport camera views searched with an image-text model; similarity is not a probability | Preview in fixture mode (labelled) or recorded clip |
| 0:45-1:00 | "Find similar elsewhere" (example-only search) | The same look in **other** buildings only | Recorded clip |
| 1:00-1:12 | Card facts: room label, "Ceiling … m estimated", FIT UNKNOWN | Room and ceiling come from the provider's floor plan and anchors; we never invent depth, so fit stays unknown until measured | Narrate over the frame |
| 1:12-1:40 | Agent stream (fixtures, labelled unless Owner 2 is live): plan → scouts → skeptic objection → 3 picks | Live progress, a skeptic veto, every claim sourced | Recorded backup |
| 1:40-1:52 | `/refine` "parking for 5 trucks": same thread, no new search | Follow-ups reuse cached evidence | JSON |
| 1:52-2:00 | `/approve` → `draft_saved`, `sent=false` | A human approves; nothing reaches a real owner | JSON |

Never claim:
- 608/19/600/488/0.04 s unless they are visible on screen;
- any recall or accuracy number;
- a matched tour pose;
- real CoStar/Vexcel evidence while lane B is unmerged;
- Windows parity beyond PR #8's own claim.

## 11. Cut recommendation

- **Lead:** the interior preview (real frames, cross-building LookAlike, honest unknown fit). It is the most-tested piece and independent of lanes B and D.
- **Keep:** the agent stream, skeptic, refine and approve on fixtures, clearly labelled. Switch to live only if Owner 2's ids match before about H21.
- **Cut:**
  - Photon/voice;
  - World Labs;
  - owner view;
  - tour pose alignment (keep a plain tour link);
  - deep engine as the default;
  - any eval number without 20 human labels;
  - Peri unless a real interview happened.
- **Before demo, cheap:**
  - fix `agent/pipeline.py:67-68` (new dev) so estimates read "unknown", not "tight" (Owner 3, ~3 lines);
  - reject UNC paths in `agent/rerank.py` (PR #8).
- **Defer:** the URL-form unification, the generation-scoped provenance sidecar, and DNS-rebinding/download-size hardening.

## 12. Deliverables

The deliverables are in `/workspace/typecast-deliverables/`. Their hashes are listed in the hand-off message.
- `REVIEW.md` (this file; identical to `docs/team/REVIEW-integration-audit.md` in the patch)
- `PR_BODY.md`
- `index-tests.patch` (plain diff vs `9284a86`)
- `index-tests.format-patch`
- `typecast-review-tests-v3.zip`
- Local commit on branch `audit/index-tests` in `/workspace/typecast-audit-tests` (not pushed).

The connected GitHub account reports push/admin permission, but nothing was pushed, by instruction. The parent/user handles any PR.
