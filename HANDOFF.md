# HANDOFF (coordinated, current)

Branch `ai/claude-release-audit` (PR #31), base origin/dev dbceec2. Code head before this docs commit: c5dbfcb. Not pushed by this session. Details and per-finding evidence: `index/CLAUDE-RELEASE-REVIEW.md`. Demo script/checks: `index/GEMINI-DEMO-HANDOFF.md`.

## 1. Goal
Release QA for HackPrinceton Typecast (Director, reel, project import, viewfinder, AI dressing). Fix reproduced failures only; mock/synthetic data only; no push/merge/provider calls/private data. Interior labeling is complete; no more labeling.

## 2. Current state (commits, oldest first)
fb1d54f rejected-location-after-failed-replan · 153c302 portable Windows symlink tests + import overwrite guard · 6823f6d real solver-shape rejection cleanup (`property_ids`, numeric `locations`), import snapshot before first await, constraint guard · b068836 Gemini demo handoff (Claude-reviewed, docs) · 81a8452 AI-dressed viewfinder grab stamp/filename + dressing lifecycle tests (Grok Worker4 leads: provenance fixed; close race and Director-label leads not reproduced) · c5dbfcb Grok Worker5 (PR32 baseline dbceec2) findings fixed: status-authoritative availability, measured-only shot fit, mock-fixture labelling, fixture Look-around explanation, in-page camera metrics panel.

## 3. Verified counts (Windows, existing venv, at c5dbfcb)
`scripts/verify.py` exit 0: 596 passed, 5 skipped (4 file-symlink skips with portable equivalents + 1 prior); smoke, SSE/refinement/no-send approval PASS; 20/20 unlabeled mock attempts, recall N/A. Node: director-audit 32 pass/1 skip (browser-only surface), director-project 29, director_reel 16, viewfinder 8, web lib 15, bridge/core 6; 0 failures. Linux counts from other workers (e.g. 597) are a different context; ignore the stale 539.

## 4. Browser check status (truthful)
NOT RUN. `web/tests/check_viewer.py` needs the Python `playwright` package (`--executable` can point at an installed Chromium; Chrome and Edge exist on this machine). `playwright` is not installed in the project venv, system Python or global npm, and installing is outside this task. Everything above is Node/vm harness or pytest, not a real browser. Specifically unverified in a browser: in-page camera metrics panel rendering, MOCK labels, fixture Look-around message, availability/fit "unknown" badges, WebGL viewfinder stamp, WebM, file-picker import, microphone. Run on a machine with playwright: start a mock server, then `python web/tests/check_viewer.py --base-url http://localhost:8001 [--failure-states --mobile]` (old assertions may mention previous wording; inspect failures, do not blindly edit).

## 5. Open items
- Grok Worker4: still pending its own report; compare against review items "Grok Worker4 leads".
- Grok Worker5 (PR32, 2c2b57f at dbceec2): resolved per review. Unchanged by design: fixture limits (one placeholder frame, trucks not excluding, Require-available emptying mock plans), scout ordering among blocked alternatives, deep-engine fallback.
- Older AI-dressed thumbnails saved before the stamp fix keep unstamped pixels.
- A mock run proves nothing about live CoStar/Vexcel/LangChain eligibility.

## 6. Human final demo (integration captain's machine, private cache)
Follow `index/GEMINI-DEMO-HANDOFF.md`: run verify there; time cold/warm Build plan; record Evidence statuses; choose one replan (Reject, or vehicles then Build plan); check Look around/AI dressing exists for the chosen frame; record and open a WebM; real file-chooser project import and microphone only if tested; genuine Deep Agents trace only if completed; sponsor permission before showing licensed imagery; keep a fallback recording; submit before 08:00 ET Sunday 15 Nov.

## 7. Resume
`node --test index/tests/director-audit.mjs web/tests/lib.test.mjs web/tests/viewfinder.test.cjs`; `python scripts/verify.py` with `typecast/.venv`.
