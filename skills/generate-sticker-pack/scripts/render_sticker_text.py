#!/usr/bin/env python3
"""Render reliable post-generation captions onto transparent sticker assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="asset-map.json")
    parser.add_argument("--assets", required=True, help="Directory containing source PNG assets")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--text-map", help="JSON object mapping label or ID to caption")
    parser.add_argument("--font", help="Optional TTF/TTC/OTF font path")
    parser.add_argument("--font-size", type=int, default=38)
    parser.add_argument("--padding", type=int, default=18)
    return parser.parse_args()


def load_font(path: str | None, size: int) -> ImageFont.ImageFont:
    candidates = [path] if path else []
    candidates.extend([
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ])
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    source_dir = Path(args.assets).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    text_map = json.loads(Path(args.text_map).read_text(encoding="utf-8")) if args.text_map else {}
    if not isinstance(text_map, dict):
        raise ValueError("text-map must be a JSON object")
    label_font = load_font(args.font, args.font_size)
    exported = []

    for asset in manifest.get("assets", []):
        source = source_dir / asset["file"]
        image = Image.open(source).convert("RGBA")
        caption = str(text_map.get(asset["id"], text_map.get(asset["label"], asset["label"]))).strip()
        if not caption:
            caption = asset["label"]
        probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        box = probe.textbbox((0, 0), caption, font=label_font, stroke_width=3)
        text_w, text_h = box[2] - box[0], box[3] - box[1]
        scale = min(1.0, (image.width - args.padding * 2) / max(1, text_w))
        used_font = label_font if scale >= 0.98 else load_font(args.font, max(14, int(args.font_size * scale)))
        box = probe.textbbox((0, 0), caption, font=used_font, stroke_width=3)
        text_w, text_h = box[2] - box[0], box[3] - box[1]
        canvas = Image.new("RGBA", (image.width, image.height + text_h + args.padding * 2), (0, 0, 0, 0))
        canvas.alpha_composite(image, (0, 0))
        draw = ImageDraw.Draw(canvas)
        x = (canvas.width - text_w) // 2
        y = image.height + args.padding - box[1]
        draw.text((x, y), caption, font=used_font, fill=(255, 255, 255, 255),
                  stroke_width=5, stroke_fill=(30, 30, 30, 255))
        target = out_dir / asset["file"]
        canvas.save(target)
        exported.append({"id": asset["id"], "label": asset["label"], "caption": caption, "file": target.name})

    report = {"status": "pass", "count": len(exported), "assets": exported}
    (out_dir / "caption-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: rendered captions for {len(exported)} stickers: {out_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError, FileNotFoundError) as error:
        raise SystemExit(f"ERROR: {error}") from None
