# Release handoff: Director Room + shared agent/viewer

Feature head: a982125, PR #22 into dev. Root did not merge dev/main or deploy.

## What ships

- Shared app serves the full scout viewer at /app/ and Director at /director, linked both ways.
- Bounded multi-scene location grouping, exact property/model join checks, rejection/replan, explicit uncertainty.
- Independent A/B character blocking and timed dialogue over real frames; reviewed model alternatives with Apply/Discard/Undo.
- Verified-horizon WebGL viewfinder, lens/ratio/drag/capture/reopen, scan-relative orientation. No measured stage geometry or world alignment.
- Silent WebM rehearsal, PNG, project JSON and self-contained static shoot pack. Real 1280x720 WebM downloaded and played; final 2-second recording also completed after restarting the release server.
- Saved-project validation and exact-frame restore with changed-frame drafts retained for review. 29 pure tests; browser file-picker round trip is still unverified.
- Actual plan_production_shoot registered in the Deep Agents director graph; fake-model graph dispatch tested. The new tool has not been demonstrated with a live provider trace. Existing scout traces are separate evidence.
- Grok backend/frontend audit failures repaired and converted to passing regressions; unknown statuses do not become factual claims.

## Verification

Integrated scripts/verify.py: 539 passed, one skipped, smoke PASS, concurrent-progress SSE/cached refinement/unsent local-draft approval PASS; 20/20 unlabeled fixture attempts, recall N/A. Python gate also runs Node reel, project, viewfinder, viewer utility and adversarial editor suites. CI success on the exact feature head: https://github.com/Tecncentral/typecast/actions/runs/43641636989 .

Real local browser: real retrieval and property/model identity, staging/playback, reviewed text brainstorm, replan/frame review, JSON/HTML exports, WebGL controls/reopen and actual silent recording. Microphone and browser project import remain unverified. New release restart returned a real kitchen plan with unknown availability/parking retained, and completed a 2-second WebM recording.

## Demo laptop: integration captain

Discord confirms the expanded source cache is on the integration captain's laptop and the final demo will run there. No second private bundle is required on Owner 1's machine. The small local index and old join do not reproduce that richer demo. Keep sponsor assets private.

1. Fetch origin, inspect PR #22 against current dev and preserve any dirty local work. Merge the reviewed lane with current dev only after resolving understood conflicts; do not reset or force-push.
2. Run python scripts/verify.py in the existing environment. Existing baseline dependencies are unchanged by this feature package.
3. Run python -m uvicorn agent.app:app --host 127.0.0.1 --port 8771 with the demo laptop's private .env and caches. Open /app/ and /director.
4. Warm an authored plan. Verify exact selected property/model pairs, real images, availability and Vexcel status/capacity against the existing caches. Reject one location and confirm exclusion. Never replace a missing source with fixtures in live mode.
5. Stage an A take, review/apply a text proposal to B, play, record WebM, open it, export a shoot pack and test JSON re-import using the normal file chooser. Use text unless microphone capture works in rehearsal.
6. For LangChain, show a genuine available deep-agent trace. If pitching the new multi-scene tool as live, run a multi-scene request and verify its actual tool event/result first. No synthetic progress is a trace.

## Human closeout

No further interior labeling is needed. Rehearse a two-minute pitch and keep a fallback recording. Gather team/Discord usernames and actual sponsor opt-ins; submit by the earlier 08:00 Eastern Sunday 15 November deadline. Peri requires a real consultation; omit it if none is completed. Photon/Gemini API/music/3D-character claims are not established. Presentation and submission assets already live under docs/; Director run-of-show is index/DEMO-SCRIPT.md.

Primary targets: ENTERTAINMENT, CoStar, Amazon, LangChain supported by the actual deep-agent implementation/demo. Eligibility is subject to organizers and genuine evidence, not a win guarantee.
