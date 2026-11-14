# PR30 dressed-set regression audit

Read-only audit of the dressed-set / viewfinder integration. No production code was changed. No provider, model, or network API calls. Mode for every command below: mock / public fixtures (`TYPECAST_USE_MOCKS=1` where a suite sets it). No licensed cache and no live keys were used.

## Baseline

Tested checkout: `dbceec2f392af037d4123177e8da35e8a3b877a8` (`git rev-parse HEAD` before and after the audit files were added; the tree was detached at that commit). That commit is the merge of PR #30 (`dressed-set`) onto PR #22. Feature head `0bdc5e2` is an ancestor. This checkout was not rebased and was not moved to PR31.

PR31 was compared read-only at `e99082d8c617abf0709e9a029fc1f18ad4d31761` (`git fetch origin pull/31/head:pr31`, then `git rev-parse pr31` and `git diff dbceec2 e99082d -- <file>`). PR31 is not merged. Its suite was not executed here.

`git diff dbceec2 e99082d -- agent/app.py worlds/dress.py` is empty. In `web/viewfinder.js`, PR31 adds `shotFilename` / `stampAiLabel` around the grab path and does not change `loadDressed` (badge at line 624, ready-status at lines 638–642).

## Commands and counts

Python: 3.12.3, venv `/tmp/typecast-venv` from `requirements.lock.txt`. Node: v22.23.4.

Baseline, before any audit file existed:

| Command | Observed |
|---|---|
| `/tmp/typecast-venv/bin/python scripts/verify.py` | pytest `597 passed in 13.12s`; smoke `PASS: mock search -> validated picks -> same-thread refinement -> SSE result -> no-send approval`; e2e `PASS: progress arrived while search was blocked; refine reused the thread and cached candidates; yes approval saved a draft with sent=false`; mock eval `20 attempted, 20 succeeded; 0 labeled scenes scored, 20 unlabeled skipped`; `recall@10: N/A` |
| `TYPECAST_USE_MOCKS=1 /tmp/typecast-venv/bin/python -m pytest -q` | `597 passed in 12.34s` |
| `node --test bridge/core.test.mjs index/tests/director_reel.test.js index/tests/director-project.test.cjs index/tests/director-audit.mjs web/tests/lib.test.mjs web/tests/viewfinder.test.cjs` | `tests 90`, `pass 89`, `fail 0`, `skipped 1`, `todo 0` |

The skipped Node test is `real browser surfaces this harness cannot drive` in `index/tests/director-audit.mjs`. The existing viewfinder lifecycle tests passed, including `a late AI-dressing response for a closed scan never dresses the next room`.

After these audit files (same SHA, tests only):

| Command | Observed |
|---|---|
| `TYPECAST_USE_MOCKS=1 /tmp/typecast-venv/bin/python scripts/verify.py` | pytest `600 passed, 7 xfailed in 12.43s`; same smoke PASS, e2e PASS, and mock eval `20/20` unlabeled, `recall@10: N/A` |
| `TYPECAST_USE_MOCKS=1 /tmp/typecast-venv/bin/python -m pytest -q index/tests/test_pr30_regressions.py` | `3 passed, 7 xfailed` |
| `node --test index/tests/pr30-regressions.mjs` | `tests 2`, `pass 0`, `fail 0`, `todo 2` (exit 0). The pytest wrapper passes `--test-reporter=tap` because GitHub's Node prints the spec reporter and omits the `# fail 0` summary. |

`pytest --runxfail` on the new file fails those 7 tests. That is the reproduction. They are `xfail(strict=True)` in normal runs so the suite stays green. Node todos are the same two UI cases.

## Top 3 remaining reproduced failures

These are not fixed in PR31 `e99082d`. There are three, ranked by how directly they mislabel imagery.

### 1. PR30-LABEL — cache text is served as provenance (high)

A dressed record can name the set as a real capture. The route returns that string, and the viewfinder badge displays it instead of the canonical imagined label. A record with no label is returned as JSON `null`. The same response echoes a prompt that contains a key-like token and a home path.

- `agent/app.py:317-318` (`prompt` and `label` are `record.get(...)`)
- `web/viewfinder.js:624` (`data.label || "AI-imagined set dressing, not the real room"`)
- `worlds/dress.py:33` defines `LABEL = "AI-imagined set dressing, not the real room"` but the route does not force it

Repro: `TYPECAST_USE_MOCKS=1 python -m pytest index/tests/test_pr30_regressions.py::test_dressed_response_keeps_the_canonical_label_and_drops_secret_text index/tests/test_pr30_regressions.py::test_missing_cache_label_still_ships_the_canonical_label index/tests/test_pr30_regressions.py::test_viewfinder_badge_ignores_a_real_capture_label --runxfail --tb=line`

Observed:

- JSON `label` is `Real captured Matterport property photograph`, not `dress.LABEL`
- JSON `label` is `null` when the key is absent
- Badge text is `Real captured Matterport property photograph · dressed for “INT. KITCHEN - DAY”`
- The same dressed.json probe returned `"prompt":"sk-TESTKEY private /home/user/.ssh/id_rsa"` (synthetic marker, not a live key)

Expected: every `/api/dressed` body and the badge use `dress.LABEL`, and the body does not repeat credential-like or filesystem text from the cache file.

### 2. PR30-FACE-PATH — a dressed face name serves a different cache image (high)

`dressed_url` is `f"{base}/{f['dressed']}"` with no filename allowlist (`agent/app.py:322`). A face name of `../../../../views/real-property.jpg` is returned as-is. Fetching that URL from `CachedImages` returns the other file's bytes.

Repro: `TYPECAST_USE_MOCKS=1 python -m pytest index/tests/test_pr30_regressions.py::test_dressed_face_name_cannot_escape_onto_another_cache_image --runxfail --tb=line`

Observed: HTTP 200, and the assertion `200 == 404` failed. A direct probe of the same URL shape returned body `b'REALJPEG'` while `GET /cache/secret.txt` stayed 404.

Expected: face names are a single safe basename under that scan's `dressed/` directory. A `..` name is a 404/422 and does not serve `cache/views/real-property.jpg`.

This is not a read of arbitrary non-images. `.txt` and paths that leave `cache/` 404'd in the same probe.

### 3. PR30-CACHE — damaged or missing dressed files do not degrade honestly (medium)

Two cache shapes crash the route. A third says the dressed set is ready when the image never decoded.

- Corrupt `dressed.json`: `worlds/dress.py:178` `json.loads` is uncaught. Observed HTTP 500 (`pytest` line: `assert 500 in (404, 422)`). Expected 404 or 422.
- Face missing `yaw_deg`: `agent/app.py:320` raises `KeyError`. Observed HTTP 500. Expected 404 or 422.
- Image `decode()` rejects: `web/viewfinder.js:638-642` still unhides `.vf-dress` and sets the status to `An AI-dressed version of this room is ready: press D or AI dressing.` Observed `hidden === false` (`assert False is True` in `test_missing_dressed_image_is_not_announced_as_ready`) and that status string from the same `loadDressed` call. Expected: leave the control hidden and do not say the dressed set is ready.

Repro: the three `PR30-CACHE` tests in `index/tests/test_pr30_regressions.py` with `--runxfail`, and `node --test index/tests/pr30-regressions.mjs` (todo `PR30-CACHE`).

An absent worlds directory is already honest: `GET /api/dressed/{id}` is 404 `No dressed set for this scan point` (`test_absent_dressed_cache_is_a_404`, passed).

## Fixed in PR31 e99082d

Not forwarded as remaining defects. Confirmed by diff, not by re-running PR31's suite.

| Reported fix | What the diff shows |
|---|---|
| AI-grab pixel and filename provenance | `web/viewfinder.js` gains `stampAiLabel` and `shotFilename` (`-ai-dressed` suffix, non-filename characters stripped). New tests in `web/tests/viewfinder.test.cjs`. |
| Provenance stamp on the grabbed frame | Same `stampAiLabel` draws `AI-imagined set dressing · not the real room` onto the export canvas. This session did not call `grab()`. |
| Mock labels, camera metric panel, rejection/import races | `index/director.js`, `web/lib.js`, `web/drawer.js`, and their tests. This session did not reproduce those failures. The dbceec2 director Node suite passed 89 and skipped 1, which does not cover the shapes PR31 adds. |

The viewfinder badge at line 624 is not part of that stamp. It is still finding 1.

## Unconfirmed

Not reproduced. Do not treat these as defects from this audit.

- Generated faces or people. Atlas was not called. `dressing_prompt` contains `no people` (`worlds/dress.py:60`). No response field attests that a depicted person is synthetic, and no image with a person was produced.
- Stale dressed textures painted onto the next scan. The existing test `a late AI-dressing response for a closed scan never dresses the next room` passed. A close while face decodes are in flight was not executed here. PR31 adds that test and does not change `loadDressed`'s generation check.
- Whether the static wipe tags (`web/viewfinder.js:291`, `AI-dressed` / `Real scan`) caption dimmed real pixels when no dressed texture uploaded. The control is shown (finding 3). Pixels were not drawn.
- Director PNG, shoot-pack, and WebM labelling of dressed frames. Director does not request `/api/dressed`. Existing export tests passed and do not include dressed sets.
- Browser file-chooser import, microphone, and WebGL pixels.

## Not executed

- Real browser pixels, Chromium, layout, or the file chooser. No display was used.
- PR31's reported gate (596 pass, 5 Windows skips, 106 Node pass, 1 skip) and its Chromium mock UI run.
- Live World Labs, live scout, licensed images, and any network provider.
- Windows path containment (PR31 area). Not run.

## Suggested fix (not applied)

```diff
--- a/worlds/dress.py
+++ b/worlds/dress.py
@@
+def _face_file(name: str) -> bool:
+    return isinstance(name, str) and "/" not in name and "\\" not in name and ".." not in name \
+        and bool(__import__("re").fullmatch(r"[A-Za-z0-9._-]{1,80}", name))
+
 def load_dressed(model_id: str, sweep_id: str) -> Optional[dict]:
     path = scan_point_dir(model_id, sweep_id) / "dressed" / "dressed.json"
     if not path.is_file():
         return None
-    record = json.loads(path.read_text(encoding="utf-8"))
+    try:
+        record = json.loads(path.read_text(encoding="utf-8"))
+    except (OSError, ValueError):
+        return None
+    if not isinstance(record, dict):
+        return None
+    faces = []
+    for face in record.get("faces") or []:
+        if not isinstance(face, dict) or not _face_file(face.get("dressed")) or not _face_file(face.get("real")):
+            continue
+        try:
+            faces.append({**face, "yaw_deg": float(face["yaw_deg"]), "pitch_deg": float(face["pitch_deg"]),
+                          "tan_h": float(face["tan_h"]), "tan_v": float(face["tan_v"])})
+        except (KeyError, TypeError, ValueError):
+            continue
+    if not faces:
+        return None
+    record = {**record, "faces": faces, "label": LABEL}
     record["dir"] = f"/cache/worlds/{_safe(model_id)}/{_safe(sweep_id)}/dressed"
     return record
```

```diff
--- a/agent/app.py
+++ b/agent/app.py
@@
-        "prompt": record.get("prompt_used") or record.get("prompt"),
-        "label": record.get("label"),
+        "prompt": None,
+        "label": LABEL,
```

Use `LABEL` from `worlds.dress`. Keep scene id/text only if they stay free of credential-like and path strings; otherwise omit them too.

```diff
--- a/web/viewfinder.js
+++ b/web/viewfinder.js
@@
-    this.$(".vf-ai-badge").textContent = `${data.label || "AI-imagined set dressing, not the real room"}${scene ? ` · dressed for “${scene}”` : ""}`;
+    const canon = "AI-imagined set dressing, not the real room";
+    this.$(".vf-ai-badge").textContent = `${canon}${scene ? ` · dressed for “${scene}”` : ""}`;
@@
-    if (!current()) return;
-    const toggle = this.$(".vf-dress");
-    toggle.hidden = false;
+    if (!current()) return;
+    const loaded = renderer /* count of setDressedFace calls for this generation */;
+    if (!loaded) return;
+    const toggle = this.$(".vf-dress");
+    toggle.hidden = false;
```

Do not set the ready status unless at least one dressed image decoded in this generation. Do not overwrite the grab stamp from PR31.

## Handoff for the fix owner

Three remaining bugs, all outside the PR31 grab/filename, mock-label, camera-metric, and import/rejection edits: `PR30-LABEL`, `PR30-FACE-PATH`, `PR30-CACHE`. Tests are `xfail(strict=True)` in `index/tests/test_pr30_regressions.py` and `todo` in `index/tests/pr30-regressions.mjs`. A real fix makes those assertions pass; remove the xfail/todo in the same change or strict xfail will fail the run. `test_absent_dressed_cache_is_a_404` and `test_cache_does_not_serve_a_non_image` should stay passing. Do not rebase this branch onto PR31; port the tests onto `e99082d` if that lands first. No schema or dependency change is required.
