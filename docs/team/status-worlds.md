# AI-dressed sets (World Labs Atlas)

Updated 2026-11-14 ~21:10 UTC. Branch `dressed-set`.

## Works (verified)
- `python -m worlds.dress --demo` dressed the top pick's scan point for all 5 demo scenes: images2PosedRGBD (4 real horizon faces, 1280x720, first frame canonical) then atlasChisel (depth-only targets plus a set-dressing prompt). Each step finished in seconds. Estimated camera headings came back within 4° of 0/90/180/270, which independently confirms the viewfinder's face order.
- `GET /api/dressed/{shot_id}` returns the dressed faces with their Atlas camera heading and field of view, the scene, and a fixed AI label. 404 when none exists or when `TYPECAST_ENABLE_DRESSED=0`; 422 on a bad id.
- Viewfinder: an "AI dressing" toggle (D) appears when a dressed set exists. It sweeps a before/after wipe into the 360° view, with a draggable divider ("AI-dressed" | "Real scan") and a persistent "AI-imagined set dressing, not the real room" badge. Outside the dressed frames' vertical coverage the real room shows dimmed. Grabbed frames that include dressing are marked "AI-dressed".
- `/cache` serves `.spz` only under `cache/worlds/`. All world outputs stay in git-ignored `cache/worlds/`.
- Tests: `agent/tests/test_worlds.py` (9). `python scripts/verify.py`: 356 passed.

## Spend
10 Atlas operations (5 images2PosedRGBD, 5 atlasChisel), listed in `cache/worlds/atlas-operations.jsonl`. Atlas publishes no price for these two tasks; check the balance at https://atlas.worldlabs.ai/settings/credits/developer (it was 9,960 credits before the runs). No posedImages2Splats (5,000 credits) has been run.

## Not done / limits
- Walkable splat: `python -m worlds.dress --splat --shot <id> --allow-spend-credits 5000`, written but not run. With four views from one optical center the docs predict a good result only near that point.
- Dressed frames are 1280x720, so they cover about ±30° vertically; above and below, the real room shows dimmed.
