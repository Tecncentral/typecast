"""Generate labelled placeholders for the invented shot fixture image paths."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    shots = json.loads((ROOT / "mocks/shot.json").read_text())
    title = ImageFont.load_default(size=32)
    text = ImageFont.load_default(size=22)
    for shot in shots:
        path = (ROOT / shot["image_path"]).resolve()
        if not path.is_relative_to((ROOT / "mocks/img").resolve()):
            raise ValueError("Fixture image must be inside mocks/img")
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGB", (800, 500), "#e9edf1")
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((28, 28, 772, 472), outline="#718293", width=3)
        draw.text((56, 62), "SYNTHETIC MOCK FRAME", font=title, fill="#182735")
        draw.text((56, 132), shot["shot_id"], font=text, fill="#182735")
        draw.text((56, 196), f"Fixture room: {shot['room_area_m2']} m2", font=text, fill="#34495e")
        draw.text((56, 238), f"Ceiling: {shot['ceiling_m']} m | Depth: {shot['depth_m']} m", font=text, fill="#34495e")
        draw.text((56, 280), f"Camera heading: {shot['heading_deg']} degrees", font=text, fill="#34495e")
        draw.text((56, 402), "Not a real building photograph.", font=text, fill="#923f24")
        canvas.save(path, quality=85)
    print(f"Generated {len(shots)} labelled synthetic mock frames.")


if __name__ == "__main__":
    main()
