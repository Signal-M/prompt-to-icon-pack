#!/usr/bin/env python3
"""Generate a deterministic 1,000-icon alpha-matting regression corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default=str(ROOT / "corpus-spec.json"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--count", type=int, help="Smoke-test override")
    return parser.parse_args()


def draw_case(category: str, size: int, rng: random.Random) -> tuple[Image.Image, Image.Image]:
    asset = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(asset)
    dx = rng.randint(-4, 4)
    dy = rng.randint(-3, 3)
    green = (112 + rng.randint(-8, 8), 194 + rng.randint(-8, 8), 49, 255)
    dark = (48, 116, 31, 255)
    white = (251, 251, 248, 255)
    pale = (242, 246, 235, 255)

    if category == "white_cap_open_boundary":
        draw.ellipse((31 + dx, 42 + dy, 97 + dx, 108 + dy), fill=green, outline=dark, width=2)
        draw.pieslice((29 + dx, 13 + dy, 99 + dx, 77 + dy), 180, 360, fill=white)
        draw.arc((29 + dx, 13 + dy, 99 + dx, 77 + dy), 180, 360, fill=dark, width=2)
        draw.rounded_rectangle((26 + dx, 49 + dy, 102 + dx, 62 + dy), radius=6, fill=green, outline=dark, width=2)
    elif category == "enclosed_white_detail":
        draw.rounded_rectangle((24 + dx, 20 + dy, 104 + dx, 108 + dy), radius=22, fill=green, outline=dark, width=3)
        draw.ellipse((43 + dx, 42 + dy, 85 + dx, 84 + dy), fill=white, outline=dark, width=3)
    elif category == "pale_foreground":
        draw.ellipse((25 + dx, 18 + dy, 103 + dx, 108 + dy), fill=pale, outline=(202, 213, 191, 255), width=2)
        draw.rounded_rectangle((42 + dx, 52 + dy, 86 + dx, 92 + dy), radius=12, fill=green)
    elif category == "true_transparent_hole":
        draw.ellipse((24 + dx, 20 + dy, 104 + dx, 108 + dy), fill=green, outline=dark, width=2)
        draw.ellipse((46 + dx, 43 + dy, 82 + dx, 79 + dy), fill=(0, 0, 0, 0))
    elif category == "detached_prop":
        draw.ellipse((18 + dx, 30 + dy, 78 + dx, 104 + dy), fill=green, outline=dark, width=2)
        draw.ellipse((91 + dx, 55 + dy, 112 + dx, 76 + dy), fill=(247, 197, 42, 255), outline=(177, 125, 14, 255), width=2)
    elif category == "thin_white_detail":
        draw.rounded_rectangle((26 + dx, 22 + dy, 102 + dx, 106 + dy), radius=18, fill=green, outline=dark, width=2)
        for offset in range(0, 37, 9):
            draw.line((45 + dx + offset, 39 + dy, 45 + dx + offset, 83 + dy), fill=white, width=3)
        for offset in range(0, 45, 9):
            draw.line((42 + dx, 39 + dy + offset, 86 + dx, 39 + dy + offset), fill=white, width=3)
    elif category == "edge_highlight":
        draw.ellipse((24 + dx, 20 + dy, 104 + dx, 108 + dy), fill=green, outline=dark, width=2)
        draw.pieslice((35 + dx, 29 + dy, 93 + dx, 91 + dy), 195, 282, fill=white)
    else:
        draw.rounded_rectangle((24 + dx, 22 + dy, 104 + dx, 106 + dy), radius=20, fill=green, outline=dark, width=2)
        draw.ellipse((44 + dx, 43 + dy, 56 + dx, 55 + dy), fill=(20, 24, 18, 255))
        draw.ellipse((72 + dx, 43 + dy, 84 + dx, 55 + dy), fill=(20, 24, 18, 255))

    background = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    source = Image.alpha_composite(background, asset).convert("RGB")
    alpha = asset.getchannel("A")
    return source, alpha


def main() -> int:
    args = parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    count = args.count or int(spec["count"])
    if count < 1:
        raise ValueError("count must be positive")
    out_dir = Path(args.out).expanduser().resolve()
    source_dir = out_dir / "source"
    alpha_dir = out_dir / "alpha"
    source_dir.mkdir(parents=True, exist_ok=True)
    alpha_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(int(spec["seed"]))
    categories = list(spec["categories"])
    records = []
    for index in range(1, count + 1):
        category = categories[(index - 1) % len(categories)]
        source, alpha = draw_case(category, int(spec["canvas_size"]), rng)
        name = f"case-{index:04d}"
        source_path = source_dir / f"{name}.png"
        alpha_path = alpha_dir / f"{name}.png"
        source.save(source_path)
        alpha.save(alpha_path)
        records.append({"id": name, "category": category, "source": f"source/{name}.png", "alpha": f"alpha/{name}.png"})
    manifest = {**spec, "count": count, "cases": records}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {count} deterministic cases: {out_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"ERROR: {error}")
