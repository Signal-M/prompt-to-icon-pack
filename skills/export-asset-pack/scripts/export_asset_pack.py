#!/usr/bin/env python3
"""Export a transparent asset pack to multiple raster sizes, formats, and mappings."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import zipfile

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="asset-map.json")
    parser.add_argument("--assets", required=True, help="Directory containing source PNG files")
    parser.add_argument("--out", required=True, help="Fresh output directory")
    parser.add_argument("--formats", default="png,webp", help="Comma-separated png,webp")
    parser.add_argument("--sizes", default="64,128,256", help="Comma-separated square sizes")
    parser.add_argument("--targets", default="generic", help="Comma-separated target names")
    parser.add_argument("--sprite", action="store_true", help="Create a sprite sheet and CSS")
    parser.add_argument("--allow-upscale", action="store_true")
    return parser.parse_args()


def identifier(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_$]", "_", value)
    if result and result[0].isdigit():
        result = f"asset_{result}"
    return result or "asset"


def contain(image: Image.Image, size: int, allow_upscale: bool) -> Image.Image:
    source = image.convert("RGBA")
    factor = min(size / source.width, size / source.height)
    if factor > 1 and not allow_upscale:
        factor = 1
    width, height = max(1, round(source.width * factor)), max(1, round(source.height * factor))
    resized = source.resize((width, height), Image.Resampling.LANCZOS) if (width, height) != source.size else source
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((size - width) // 2, (size - height) // 2))
    return canvas


def write_mappings(manifest: dict, sizes: list[int], formats: list[str], out: Path) -> None:
    ts = ["export const AssetPack = {"]
    css = [":root {"]
    preferred = "webp" if "webp" in formats else formats[0]
    size = max(sizes)
    for asset in manifest["assets"]:
        key = identifier(asset["id"])
        stem = Path(asset["file"]).stem
        path = f"./{preferred}/{size}/{stem}.{preferred}"
        ts.append(f'  {key}: {{ label: {json.dumps(asset["label"], ensure_ascii=False)}, src: "{path}" }},')
        css.append(f'  --asset-{asset["id"]}: url("{path}");')
    ts.extend(["} as const;", "", "export type AssetId = keyof typeof AssetPack;", ""])
    css.append("}")
    (out / "assets.ts").write_text("\n".join(ts), encoding="utf-8")
    (out / "assets.css").write_text("\n".join(css) + "\n", encoding="utf-8")


def make_sprite(manifest: dict, rendered: dict[str, Image.Image], size: int, out: Path) -> dict:
    count = len(manifest["assets"])
    columns = max(1, math.ceil(math.sqrt(count)))
    rows = math.ceil(count / columns)
    sheet = Image.new("RGBA", (columns * size, rows * size), (0, 0, 0, 0))
    css = [".asset-sprite {", "  display: inline-block;", f"  background-image: url('./asset-sprite.png');", f"  background-size: {columns * size}px {rows * size}px;", "}"]
    positions = []
    for offset, asset in enumerate(manifest["assets"]):
        row, column = divmod(offset, columns)
        x, y = column * size, row * size
        sheet.alpha_composite(rendered[asset["id"]], (x, y))
        class_name = re.sub(r"[^a-z0-9-]", "-", asset["id"].lower())
        css.extend([
            f".asset-{class_name} {{",
            f"  width: {size}px; height: {size}px;",
            f"  background-position: {-x}px {-y}px;",
            "}",
        ])
        positions.append({"id": asset["id"], "x": x, "y": y, "width": size, "height": size})
    sprite_dir = out / "sprite"
    sprite_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(sprite_dir / "asset-sprite.png")
    (sprite_dir / "asset-sprite.css").write_text("\n".join(css) + "\n", encoding="utf-8")
    return {"file": "sprite/asset-sprite.png", "width": sheet.width, "height": sheet.height, "cell": size, "positions": positions}


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    source_dir = Path(args.assets).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"Refusing to overwrite non-empty output directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    formats = [value.strip().lower() for value in args.formats.split(",") if value.strip()]
    if not formats or any(value not in {"png", "webp"} for value in formats):
        raise ValueError("formats must contain only png and webp")
    sizes = sorted({int(value) for value in args.sizes.split(",") if value.strip()})
    if not sizes or any(size < 16 or size > 4096 for size in sizes):
        raise ValueError("sizes must be between 16 and 4096")
    targets = [value.strip().lower() for value in args.targets.split(",") if value.strip()]

    rendered_for_sprite: dict[str, Image.Image] = {}
    files = []
    for asset in manifest.get("assets", []):
        source = source_dir / asset["file"]
        image = Image.open(source).convert("RGBA")
        if image.getextrema()[3] == (255, 255):
            raise ValueError(f"Source asset has no transparency: {source}")
        stem = Path(asset["file"]).stem
        for size in sizes:
            rendered = contain(image, size, args.allow_upscale)
            if size == max(sizes):
                rendered_for_sprite[asset["id"]] = rendered
            for fmt in formats:
                directory = out / fmt / str(size)
                directory.mkdir(parents=True, exist_ok=True)
                target = directory / f"{stem}.{fmt}"
                if fmt == "webp":
                    rendered.save(target, format="WEBP", lossless=True, quality=100, method=6)
                else:
                    rendered.save(target, format="PNG", optimize=True)
                files.append(str(target.relative_to(out)))

    write_mappings(manifest, sizes, formats, out)
    sprite = make_sprite(manifest, rendered_for_sprite, max(sizes), out) if args.sprite else None
    export_manifest = {
        "schema_version": 1, "source_manifest": str(manifest_path), "count": len(manifest.get("assets", [])),
        "formats": formats, "sizes": sizes, "targets": targets, "upscale_allowed": args.allow_upscale,
        "files": files, "sprite": sprite,
    }
    (out / "export-manifest.json").write_text(json.dumps(export_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    zip_path = out / "asset-export.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path != zip_path:
                archive.write(path, path.relative_to(out))
    print(f"PASS: exported {export_manifest['count']} assets to {formats} at {sizes}: {zip_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError, FileNotFoundError) as error:
        raise SystemExit(f"ERROR: {error}") from None
