# AI-dressed sets (World Labs Atlas)

Updated 2026-11-14 ~22:35 UTC. Branch `dressed-set`.

## Works (verified)
- `python -m worlds.dress --demo` dressed the top pick's scan point for all 5 demo scenes: images2PosedRGBD (4 real horizon faces, 1280x720, first frame canonical) then atlasChisel (depth-only targets plus a set-dressing prompt). Each step finished in seconds. Estimated camera headings came back within 4° of 0/90/180/270, which independently confirms the viewfinder's face order.
- `GET /api/dressed/{shot_id}` returns the dressed faces with their Atlas camera heading and field of view, the scene, and a fixed AI label. 404 when none exists or when `TYPECAST_ENABLE_DRESSED=0`; 422 on a bad id.
- Viewfinder: an "AI dressing" toggle (D) appears when a dressed set exists. It sweeps a before/after wipe into the 360° view, with a draggable divider ("AI-dressed" | "Real scan") and a persistent "AI-imagined set dressing, not the real room" badge. Outside the dressed frames' vertical coverage the real room shows dimmed. Grabbed frames that include dressing are marked "AI-dressed".
- Walkable set (new): `python -m worlds.dress --splat --draft --scene-id la-empty-shop --allow-spend-credits 500` reconstructed the dressed frames of the LA empty shop as Gaussian splats (posedImages2Splats with `refine: false`). It finished in under 4 minutes and returned one 8.1 MB SPZ (`draftSplat`). `/api/dressed` now returns `splat` (url, mode, scan-point position).
- Viewfinder: when a dressed set has a splat, "Walk the set" (E) appears. The 360° view finishes dressing, then cuts to the splat rendered with three.js + Spark, both vendored and loaded on first use. Same look, lens and grab controls; W A S D moves at eye height. The walk stops at walls and at the edge of what the scan point saw: the limit per direction is read from the splat itself. The badge reads "AI-imagined set dressing, not the real room · draft 3D reconstruction", and grabbed frames stay marked AI-dressed.
- Browser check: `cache/browser-venv/bin/python web/tests/check_walk.py --base-url http://localhost:8006 --shot 8241342-bP9oEnqmeie-8ahy5w856ah6x717cqkucchbc-180.000-c69369ccb8ef --executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'` passed in headless Chrome 157 for both sets (walked 1.5 m to the limit, direct link, 61 fps on an M4 Pro, no browser errors).
- New look on the same geometry: `python -m worlds.dress --redress --scene-id la-office-confrontation --scene "INT. 1980S POLICE PRECINCT BULLPEN - NIGHT. ..."` re-ran atlasChisel on the stored cameras and depth (no re-posing; seconds). The LA office became a night precinct: banker's lamps on the desk rows, a corkboard city map, neon through blinds, filing cabinets. The previous look moved to `dressed/looks/1/`. A draft splat of the new look (7.9 MB, 524,288 splats) finished in about 4 minutes.
- Scale: a one-point capture has no metric scale (0.23 and 0.39 world units per metre in the two sets). The viewer finds the floor in the splat and assumes the scan camera stood 1.5 m above it, so walking speed and wall limits are in metres. Before this fix the empty shop let the camera walk through walls.
- Direct link: `/app/#walk=<shot_id>` (optional `&yaw=<degrees>`) opens the scan point and steps inside, facing the most open direction. Precinct: `http://localhost:8006/app/#walk=10463354-LZFBoH68TzD-kpggz0sc9c3ichwidtgf7i1wa-270.000-3c5d2e61a5af`.
- `/cache` serves `.spz` only under `cache/worlds/`. All world outputs stay in git-ignored `cache/worlds/`.
- Tests: `agent/tests/test_worlds.py` (14). `python scripts/verify.py`: 602 passed.

## Spend
13 Atlas operations, listed in `cache/worlds/atlas-operations.jsonl`: 5 images2PosedRGBD, 6 atlasChisel, and 2 draft posedImages2Splats (500 credits each, both approved by Zukhriddin on Nov 14). Atlas publishes no price for the first two tasks; check the balance at https://atlas.worldlabs.ai/settings/credits/developer (it was 9,960 credits before any run). No refined splat (5,000 credits) has been run.

## What the drafts showed
- A bold scene is what makes this a reveal. The first five dressed sets are plain because their scenes describe the rooms as they already are; the precinct prompt changed the room and reads immediately.
- Standing at the scan point the precinct holds together toward the bullpen (headings 315 to 45). Toward the glass partition one metre away (heading 270) it smears, and above and below about ±30° there is nothing, because the four source frames are 1280x720.
- One metre from the scan point the sets are still coherent but softer. These are drafts from four views that share one optical centre.

## Not done / limits
- Refined splat: `python -m worlds.dress --splat --scene-id la-office-confrontation --allow-spend-credits 5000` (15 to 25 minutes). Not run; needs a go-ahead for the spend.
- One look per scan point is live at a time; switching looks inside the walk (the video's style morph) is not built.
- Better coverage: the docs ask for 8 to 16 spread-out views per room. Adding faces from neighbouring scan points in the same room is not built.
- No real-room splat yet, so the cut into 3D goes from the dressed 360° view, not from a walkable real room.
- Walk mode has no touch controls; the button works on phones but movement needs a keyboard.
- Dressed frames are 1280x720, so in the 360° comparison they cover about ±30° vertically; above and below, the real room shows dimmed.
