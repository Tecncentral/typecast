"""Privacy screen for every frame the demo can show, using the Decisions API's calibrated yes/no answers.

  python -m strike.privacy --demo [--api http://localhost:8010]

Covers all four horizon faces at each scan point behind the Director demo and the stage top picks.
Writes a private report to cache/qa/privacy-screen.json (git-ignored) and prints counts only.
A human still reviews every flagged frame; this narrows the search, it does not certify a frame.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from PIL import Image

from strike.__main__ import director_shots, stage_pick_shots
from strike.core import ROOT, OpenAIClient, StrikeError

QUESTIONS = {
    "person": "Is a person, or any part of a person, visible in this image, including reflections and people seen through windows?",
    "face": "Is a human face visible clearly enough to recognise someone?",
    "plate": "Is a vehicle licence plate legible in this image?",
    "personal_text": "Is readable personal information visible, such as a name, address, phone number, mail, a document or a screen?",
}
FLAG_AT = 0.3


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--shot", action="append", default=[])
    args = parser.parse_args(argv)
    shots = list(args.shot) + (director_shots(args.api) + stage_pick_shots() if args.demo else [])
    faces, seen = [], set()
    for shot_id in shots:
        r = requests.get(f"{args.api}/api/sweep/{shot_id}", timeout=60)
        if not r.ok:
            continue
        for face in r.json()["faces"]:
            if face["shot_id"] not in seen:
                seen.add(face["shot_id"])
                faces.append(face)
    print(f"screening {len(faces)} frames")
    client = OpenAIClient()
    names = list(QUESTIONS)

    def screen(face):
        try:
            image = Image.open(ROOT / face["image_path"].lstrip("/")).convert("RGB")
            probs = client.predicates([image], [QUESTIONS[n] for n in names])
            return {"shot_id": face["shot_id"], **{n: round(p, 3) for n, p in zip(names, probs)}}
        except (StrikeError, OSError) as error:
            return {"shot_id": face["shot_id"], "error": type(error).__name__}

    with ThreadPoolExecutor(6) as pool:
        rows = list(pool.map(screen, faces))
    flagged = [r for r in rows if any(isinstance(r.get(n), float) and r[n] >= FLAG_AT for n in names)]
    errors = [r for r in rows if "error" in r]
    out = ROOT / "cache" / "qa" / "privacy-screen.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    earlier = []
    if out.is_file():  # merge: a later, smaller run never erases earlier screened frames
        try:
            earlier = [r for r in json.loads(out.read_text(encoding="utf-8")).get("rows", [])
                       if r.get("shot_id") not in {x["shot_id"] for x in rows}]
        except (OSError, ValueError, AttributeError):
            earlier = []
    out.write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "flag_at": FLAG_AT,
                               "questions": QUESTIONS, "rows": earlier + rows}, indent=1), encoding="utf-8")
    by = {n: sum(1 for r in rows if isinstance(r.get(n), float) and r[n] >= FLAG_AT) for n in names}
    print(f"screened {len(rows) - len(errors)}, errors {len(errors)}, flagged {len(flagged)}: "
          + ", ".join(f"{n} {c}" for n, c in by.items()))
    print(f"private report: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
