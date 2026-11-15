# Save the scene (Film production mode)

## Purpose & Scope
**Save the scene** is a Film-mode-only transactional interaction (`#saveBtn` / `#savePanel` in `index/director.html`, `index/director.js`, and `index/director-checks.js`). It lets a director test a concrete production constraint (trucks, crew cars, or required listing availability) against the current candidate pool, inspect a bounded before/after comparison, and apply a complete revised solver plan without losing existing takes or misrepresenting unknown data.

- **Film mode only:** Hidden and disabled in Community planning (`data-film-only`).
- **Deterministic planner flow:** Calls `/api/production/plan` with the active script, existing `max_locations`, and `forbidden_property_ids`. No LLM, provider call, or Deep Agents trace is invoked.

## Interaction & Transaction Rules
1. **Staged Constraint Form (`openSave` / `runSave`):** Pre-fills current `trucks`, `cars`, and `require_available` while preserving global `max_locations` and rejected properties. Live feedback shows why the current frame is unmet or `unknown`.
2. **Complete Valid Plan Requirement (`saveSceneOutcome`):**
   - Only proposes an alternative actually assigned to the target scene in `plans[0]` of the revised solver response (no off-plan fallback).
   - Every script scene must remain assigned (`uncovered_scene_ids` empty for active scenes), within `max_locations`, with no rejected property IDs, and every assigned scene must satisfy the revised request (`satisfaction(candidateFacts(c), req).satisfied === true`).
   - Unknown parking capacity (`parking_status === 'unknown'`) against a positive vehicle requirement is **never** counted as met.
   - Estimated capacity (`parking_status === 'estimated'`) satisfies numeric vehicle checks when `enough_parking === true`, while explicitly stating approval remains unknown.
3. **Honest Non-Results & Stale Context Guards:**
   - Returns an honest non-result (`kind: 'none'` or `'already'`) with original state unchanged if no requirement is entered, the current candidate already satisfies it, all candidates are ruled out, only unknown capacity exists, the plan leaves scenes uncovered or over `max_locations`, or the fetch fails.
   - `saveCtxValid` aborts or marks the review stale if the script, global constraints, rejections, active scene, plan, or source `mode` changes mid-flight.
4. **Explicit Apply, Destination Preservation & Single-Step Undo (`applySave` / `undoSave`):**
   - Re-verifies full-plan validity and candidate eligibility before committing.
   - Updates global constraint inputs (`#trucks`, `#cars`, `#reqAvail`) to match the applied plan, clears stale `swapStale` flags when the assignment matches `plans[0]`, and updates `#saveBtn` disabled state after `busy(false)` / import / draft restore.
   - Copies Take A and Take B onto the new frame as unreviewed drafts (`carried: true`, preserving `authored-sample` origin) unless destination staging already exists (`dest_kept: true`), in which case existing destination staging is kept with explicit recovery controls.
   - Other scenes moved by the whole-plan replan keep their existing takes attached to their old frames (`frameChange` notice).
   - **Undo Save the scene** restores the exact pre-apply snapshot (`snapshotAll` / `restoreAll`) until a subsequent edit increments `S.rev`.
5. **Historical Decision Record (`decisionRecord` / `decisionOf`):**
   - Persists a bounded, whitelisted record (`v: 1`, `original`, `revised`, `before`, `after`, `scope: 'whole_plan'`, `totals_recalculated`, `moved_scenes`, `differences`, `unresolved`) in Project JSON, local draft recovery, and the printable Shoot pack.
   - Re-importing Project JSON re-validates live/current pool evidence and displays the saved decision strictly as historical review context, never as current source verification.

## Verification Status (Commit `39077b6ca7bafd0f127dbbb307ff1fc69fbbdef3`)
- `python scripts/verify.py`: **672 passed, 7 skipped** (including 2 Windows symlink cases).
- Node test suites (9 files): **228 passed, 1 browser-only skip, 0 failed, 0 TODO**.
- Clean Chromium QA (`../manager-drafts/save-scene-qa/qa_save.py`): **33/33 checks true**. Default mock fixtures honestly produced no alternative because parking capacity is unknown; the positive alternative branch used clearly labeled `SYNTHETIC` intercepted responses with complete assignments and estimated capacity, not real private data or provider calls.
