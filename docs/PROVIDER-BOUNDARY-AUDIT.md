# Provider boundary audit

Branch `cursor/provider-boundary-audit-7eb1`, started from `c549e66beb91c5fa46c34f2f0fd0b92377f3a570` (PR 43 head). Mock/offline only. No live OSRM or image-provider call, no `.env`, no licensed cache.

## Baseline at c549e66 (before edits)

`TYPECAST_USE_MOCKS=1 python3 scripts/verify.py` exit 0.

- pytest: `700 passed in 17.01s`
- smoke: `PASS: mock search -> validated picks -> same-thread refinement -> SSE result -> no-send approval`
- e2e: `PASS: progress arrived while search was blocked; refine reused the thread and cached candidates; yes approval saved a draft with sent=false`
- eval: `20 attempted, 20 succeeded; 0 labeled scenes scored, 20 unlabeled skipped`; `recall@10: N/A`; `Engine: fixed; source mode: mock`

Node (`node --test` on `bridge/core.test.mjs`, `index/tests/director_reel.test.js`, `index/tests/director-project.test.cjs`, `index/tests/director-checks.test.cjs`, `index/tests/director-audit.mjs`, `index/tests/pr30-regressions.mjs`, `index/tests/producer-brief.test.cjs`, `index/tests/production-costs.test.cjs`, `web/tests/lib.test.mjs`, `web/tests/viewfinder.test.cjs`, `web/tests/cast.test.mjs`) exit 0: `259 tests, 258 pass, 0 fail, 1 skip`.

New regressions were run before the fix: `python3 -m pytest -q index/tests/test_commute.py index/tests/test_scene_customization.py --tb=line` → `7 failed, 14 passed`. The seven failures are the bugs below. `test_malformed_coordinates_never_call_the_router` and `test_router_url_uses_longitude_then_latitude` passed on the unmodified code.

## After

Same `TYPECAST_USE_MOCKS=1 python3 scripts/verify.py` exit 0: `710 passed in 16.04s`, smoke PASS, e2e PASS, eval `20/20` mock. Same Node command exit 0: `258 pass, 1 skip`.

Focused: `python3 -m pytest -q index/tests/test_commute.py index/tests/test_scene_customization.py index/tests/test_production.py index/tests/test_grok_production_audit.py agent/tests/test_production_integration.py` → `168 passed`.

## Reproduced bugs

1. **Misaligned OSRM table published a partial drive time.** At c549e66 `index/commute.py:72-86`, a short `durations` row updated earlier properties to `status=estimated` and then the `IndexError` handler only replaced `note`. The contradictory row was cached. `production.py` treats `status=="estimated"` as a real commute, so the bad minutes could keep a location eligible. Failing test: `test_misaligned_router_table_does_not_publish_partial_estimates`. Fix: require one aligned duration, distance, and destination per coordinate before writing any estimate; on failure reset every row to unknown and do not cache.

2. **Provider failures were cached for five minutes.** At c549e66 `index/commute.py:83-86`, connect errors, timeouts, and non-Ok HTTP responses (including 503 via `raise_for_status`) were stored in `_CACHE`. The next identical request did not call the router. Failing tests: `test_provider_errors_are_not_cached` (ConnectError and TimeoutException). The 503 case was added to that same test after the fix. Fix: cache only a complete table. The 1.05s process rate limit and the 12s httpx timeout are unchanged. No automatic retry loop was added.

3. **A cache hit dropped property ids that were not in the cached request.** At c549e66 `index/commute.py:46-51`, the key was only the routable `(id, lat, lon)` tuples, and a hit returned that earlier map verbatim. A later request with the same routable property plus a property without coordinates omitted the new id (`KeyError` in `test_cache_hit_returns_every_requested_property`). Fix: rebuild a row for every requested id and overlay only the cached routable rows.

4. **A null OSRM waypoint raised AttributeError.** At c549e66 `index/commute.py:75`, `destinations[i].get` was outside the `except` tuple on line 83, so a JSON `null` waypoint escaped the planner as a 500. Failing test: `test_null_router_waypoints_stay_unknown_without_raising`. Fix: skip a non-object waypoint and leave that property unknown. A valid sibling in the same aligned table is still estimated.

5. **Null, list, or object commute fields returned HTTP 500.** At c549e66 `index/production.py:51-56` and `:109-112`, the `mode="before"` validator called `float(None)` / `float([])` / `float({})`. That `TypeError` is not a `RequestValidationError`, so the plan route's non-finite handler never ran (`TestClient` returned `500 Internal Server Error`). Failing test: `test_null_commute_coordinates_are_422_not_500` (lat, lon, and max_minutes). Fix: that validator only, listed below.

6. **An unreadable indexed frame escaped as `UnidentifiedImageError`.** At c549e66 `index/scene_customization.py:44-48`, `Image.open` ran after the provider client was constructed and outside the `OSError` handler on lines 63-64. With a configured key, a corrupt `cache/views` file became an uncaught error (HTTP 500 through FastAPI) instead of the existing 404. Failing test: `test_unreadable_indexed_frame_is_a_404`. Fix: decode the frame before constructing the client, and map `OSError` to 404. The provider `_post` is not called and no customization file is written.

## production.py changes

Only `CommuteConstraint._v_number` (`index/production.py:109-116`). `TypeError` from `_finite_float` is re-raised as `ValueError`, so null, list, and dict commute numbers are HTTP 422 with the existing JSON `detail` list. No other production.py behavior was changed. `index/production.py` join, rejection, and solver calls are untouched.

`agent/deep_tools.py` was not edited. `plan_production_shoot` already calls `run_production_plan`, so it uses the same request validator and commute helper.

## Checked and left as-is

- Malformed coordinates (NaN, bool, non-numeric strings, `None`, empty list, longitude stuffed into `lat` so `lat < -90`) never call the router. `coordinates()` returns `None`. In-range swaps such as `(40, -74)` cannot be told apart from a real point. The request string is longitude then latitude (`test_router_url_uses_longitude_then_latitude`: `20,10;21,11`).
- Numeric strings on `PlanRequest` commute fields are still parsed by `_finite_float` (`"34.0"` accepted, `"nope"` is 422). They are range-checked; they are not a fabricated route.
- Rejection and joins stay on ids. Existing tests that passed in the 710: `test_rejection_replans_without_assigning_forbidden_location`, `test_http_replan_drops_an_exact_forbidden_property`, `test_forbidden_property_never_returns_and_plans_are_independent_and_deterministic`, `test_live_property_model_join_confirms_conflicts_and_preserves_unknown`.
- Upload consent and mock frames: `test_image_upload_requires_explicit_consent`, `test_disabled_upload_and_mock_frames_are_never_sent`. One-off with keys removed and a real PNG: HTTP 503 `Configured image provider unavailable`, source bytes unchanged, `cache/customizations` not created. One-off `StrikeError` from `_post`: HTTP 502 `Image provider did not return a usable preview; original retained`, source unchanged, no preview file.
- Provenance: `test_image_edit_is_separate_stamped_and_source_unchanged` (source bytes unchanged, banner pixel, `geometry_verified` false, kind `imagined-single-frame`). Token traversal and a symlink at the preview file are 404 (`test_preview_path_rejects_traversal` and a one-off). A source path with `..` or a `cache/views` symlink pointing outside `cache/views` is 404 and is not uploaded.
- Missing source file is already 404. A symlink of `cache/` itself still resolves; that is a relocated cache directory, not a token traversal, and was not changed.
- `deep_tools.py` failure text stays the exception type (`test_tool_validation_and_sanitized_failure`). No second provider client lives there.

## Not executed

- No live `router.project-osrm.org` request and no live image edit. Timeouts and HTTP 503 were monkeypatched `httpx` / `StrikeError` only.
- No measured socket hang. The commute client still passes `timeout=12` (httpx per-phase, not a separate wall-clock cap). The image client still uses `strike.core.OpenAIClient._post` with `timeout=300` and that client's existing 429/5xx retries. `strike/core.py` was not changed.
- No browser pass. Director, producer-brief, and production-cost UI files were not modified.
- No private CoStar, Matterport, or Vexcel cache. No merge to `dev` or `main`.
