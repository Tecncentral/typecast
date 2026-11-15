# Strike status (integration captain)

Strike shows the same real room emptied of furniture, the way an art department strikes a location before dressing it. It follows Matterport's defurnishing research, [An Empty Room is All We Want](https://arxiv.org/abs/2405.03682) (CVPR 2024 workshops). Every struck frame is labelled **"AI-edited: furniture removed, not the real room"**.

## How it works

1. **Decide.** The OpenAI Decisions API (`/v1/decisions`, `gpt-6-luna`) answers "does this view contain movable furniture?" as a calibrated probability. Views below 0.5 are left alone.
2. **Edit.** `gpt-image-2.6-flare` removes movable furniture from the 1024 px horizon face. In the probe it was about 9 s per face, versus 49–89 s for the other models, with framing kept.
3. **Blend.** A change mask keeps every unchanged pixel of the real 2048 px scan. Walls, windows and the view stay the real photograph, which is the paper's blending idea. The mask fills enclosed holes so a rug that matches the new floor cannot survive as a ghost.
4. **Check.** The Decisions API compares real and struck: "are the walls, windows, doors, floor, ceiling and built-ins the same?" Faces below 0.7 are rejected and never served.

There is no fine-tuning. The paper's other two levers, full-panorama context and a domain-tuned model, are not reproduced, so the four views of a scan point are edited independently.

## Result on the demo scan points (2026-11-15 UTC)

- **Coverage:** 14 scan points (56 views): the Director's one-location demo plus the stage top picks for the five scenes.
- **Outcome:** 29 views were already empty; of the 27 furnished, **19 were struck and accepted** and **8 were rejected** by the architecture check, twice each (two attempts).
- **Visual check:** all 19 accepted results were reviewed by eye. Desks, chairs, pallets, debris, stools and a staged living set are removed, with windows, columns and roller doors intact.
- **Second question not used as a gate:** the "is it empty now" probability gives false negatives (kitchen appliances or exposed studs read as objects), so it is recorded but does not gate.
- **Privacy screen:** `python -m strike.privacy --demo` screened all **68** views the demo can show for people, faces, plates and readable personal text. **0 flagged.**
  - Positive control: on the frame the human QA flagged (a person leaning into a car), it returned person 1.0, face 0.0, plate 0.01, matching the human note.
  - The private report is `cache/qa/privacy-screen.json`. A human still reviews anything flagged; the screen narrows the search and does not certify.

## Where it shows

On result cards, a **Scan | Empty (AI)** toggle under "Look around" wipes the emptied plate over the real frame, with the label. The real image element is never modified, so the viewfinder, descent and frame arrows keep working. Cards without an accepted struck face show nothing.

`GET /api/strike/{shot_id}` returns the shot's face and the scan point's faces. The label is canonical and the cache is validated, never trusted. Disable with `TYPECAST_ENABLE_STRIKE=0`.

## Commands

```bash
python -m strike --demo --api http://localhost:8010            # precompute (skips done scan points)
python -m strike --demo --api http://localhost:8010 --retry-rejected
python -m strike.privacy --demo --api http://localhost:8010
```

Output stays in git-ignored `cache/strike/` and `cache/qa/`. A spend ledger is in `cache/strike/ledger.jsonl`. This used about 60 image edits and about 200 decision calls in total, from the team's OpenAI credit.

## Not done / next

- A "Struck" look in the 360° viewfinder, and re-dressing from struck faces so the precinct is no longer bound to the office's desks. The World Labs session owns the viewer; it has the file layout.
- The Director's Room stage could use a struck plate for blocking.
