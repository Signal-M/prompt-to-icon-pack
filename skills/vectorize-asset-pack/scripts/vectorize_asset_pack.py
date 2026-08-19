#!/usr/bin/env python3
"""Create sanitized SVG assets with eligibility and render-back QA gates."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image


SVG_NS = "http://www.w3.org/2000/svg"
ALLOWED_TAGS = {
    "svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon",
    "defs", "linearGradient", "radialGradient", "stop", "clipPath", "mask", "title", "desc",
}
SHAPE_TAGS = {"path", "circle", "ellipse", "rect", "line", "polyline", "polygon"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="asset-map.json")
    parser.add_argument("--assets", required=True, help="Directory containing source PNG assets")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--mode", choices=("auto", "trace", "native"), default="auto")
    parser.add_argument("--svg-source", help="Directory with native SVG files; defaults to assets")
    parser.add_argument("--max-colors", type=int, default=64)
    parser.add_argument("--max-shapes", type=int, default=500)
    parser.add_argument("--max-bytes", type=int, default=500_000)
    parser.add_argument("--max-error", type=float, default=0.12, help="Maximum normalized render difference")
    return parser.parse_args()


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def raster_color_count(path: Path, limit: int) -> int:
    image = Image.open(path).convert("RGBA")
    thumb = image.resize((min(256, image.width), min(256, image.height)), Image.Resampling.LANCZOS)
    rgba = np.asarray(thumb)
    pixels = rgba[:, :, :3][rgba[:, :, 3] > 8]
    if not len(pixels):
        return 0
    quantized = (pixels // 16).astype(np.uint8)
    return min(limit + 1, len(np.unique(quantized, axis=0)))


def sanitize_svg(source: Path, target: Path, max_shapes: int, max_bytes: int) -> dict:
    raw = source.read_bytes()
    if len(raw) > max_bytes * 4:
        raise ValueError("source SVG is excessively large")
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("DOCTYPE and ENTITY are not allowed")
    root = ET.fromstring(raw)
    if local(root.tag) != "svg":
        raise ValueError("root element must be svg")
    removed = []
    for parent in list(root.iter()):
        for child in list(parent):
            if local(child.tag) not in ALLOWED_TAGS:
                removed.append(local(child.tag))
                parent.remove(child)
        for key in list(parent.attrib):
            name = local(key).lower()
            value = parent.attrib[key].strip()
            lower_value = value.lower()
            if name.startswith("on") or name in {"href", "xlink:href"} and not lower_value.startswith("#"):
                del parent.attrib[key]
                removed.append(f"attribute:{name}")
            elif "url(" in lower_value and "url(#" not in lower_value:
                del parent.attrib[key]
                removed.append(f"external-url:{name}")
    if "viewBox" not in root.attrib and "viewbox" not in {key.lower() for key in root.attrib}:
        raise ValueError("SVG requires a viewBox")
    shape_count = sum(1 for node in root.iter() if local(node.tag) in SHAPE_TAGS)
    if shape_count > max_shapes:
        raise ValueError(f"shape count {shape_count} exceeds {max_shapes}")
    ET.register_namespace("", SVG_NS)
    target.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)
    size = target.stat().st_size
    if size > max_bytes:
        target.unlink(missing_ok=True)
        raise ValueError(f"sanitized SVG size {size} exceeds {max_bytes}")
    return {"shape_count": shape_count, "bytes": size, "removed": removed}


def trace_png(source: Path, target: Path) -> None:
    executable = shutil.which("vtracer")
    if not executable:
        raise ValueError("VTracer CLI is not installed")
    subprocess.run([
        executable, "--input", str(source), "--output", str(target),
        "--colormode", "color", "--mode", "spline", "--preset", "poster",
    ], check=True, capture_output=True, text=True)


def render_difference(svg: Path, raster: Path) -> float:
    try:
        import cairosvg
    except ImportError as error:
        raise ValueError("CairoSVG is required for render-back QA") from error
    source = Image.open(raster).convert("RGBA")
    rendered_bytes = cairosvg.svg2png(url=str(svg), output_width=source.width, output_height=source.height)
    rendered = Image.open(io.BytesIO(rendered_bytes)).convert("RGBA")
    left = np.asarray(source, dtype=np.float32) / 255.0
    right = np.asarray(rendered, dtype=np.float32) / 255.0
    left_rgb = left[:, :, :3] * left[:, :, 3:4]
    right_rgb = right[:, :, :3] * right[:, :, 3:4]
    rgb_error = np.abs(left_rgb - right_rgb).mean()
    alpha_error = np.abs(left[:, :, 3] - right[:, :, 3]).mean()
    return float(rgb_error * 0.75 + alpha_error * 0.25)


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    assets_dir = Path(args.assets).expanduser().resolve()
    svg_source = Path(args.svg_source).expanduser().resolve() if args.svg_source else assets_dir
    out = Path(args.out).expanduser().resolve()
    svg_dir = out / "svg"
    preview_dir = out / "previews"
    svg_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []

    for asset in manifest.get("assets", []):
        raster = assets_dir / asset["file"]
        stem = Path(asset["file"]).stem
        raw_svg = out / f".{stem}.raw.svg"
        final_svg = svg_dir / f"{stem}.svg"
        record = {"id": asset["id"], "label": asset["label"], "source": asset["file"], "status": "skipped"}
        try:
            if args.mode == "native":
                candidate = svg_source / f"{stem}.svg"
                if not candidate.exists():
                    raise ValueError("matching native SVG source is missing")
                raw_svg.write_bytes(candidate.read_bytes())
                record["vector_mode"] = "native"
            else:
                colors = raster_color_count(raster, args.max_colors)
                record["quantized_color_count"] = colors
                if args.mode == "auto" and colors > args.max_colors:
                    record["reason"] = f"not eligible: more than {args.max_colors} quantized colors"
                    results.append(record)
                    continue
                trace_png(raster, raw_svg)
                record["vector_mode"] = "trace"
            record.update(sanitize_svg(raw_svg, final_svg, args.max_shapes, args.max_bytes))
            error = render_difference(final_svg, raster)
            record["render_error"] = round(error, 6)
            if error > args.max_error:
                final_svg.unlink(missing_ok=True)
                raise ValueError(f"render error {error:.4f} exceeds {args.max_error}")
            shutil.copy2(raster, preview_dir / Path(asset["file"]).name)
            record["status"] = "pass"
            record["file"] = str(final_svg.relative_to(out))
        except (ValueError, ET.ParseError, subprocess.CalledProcessError, OSError) as error:
            final_svg.unlink(missing_ok=True)
            record["status"] = "needs_review"
            record["reason"] = str(error)
        finally:
            raw_svg.unlink(missing_ok=True)
        results.append(record)

    requested = [record for record in results if record["status"] != "skipped"]
    failed = [record for record in requested if record["status"] != "pass"]
    passed = [record for record in results if record["status"] == "pass"]
    report = {
        "status": "pass" if requested and not failed else "needs_review",
        "mode": args.mode, "count": len(results), "vectorized": len(passed),
        "skipped": sum(record["status"] == "skipped" for record in results),
        "failed": len(failed), "assets": results,
    }
    (out / "vectorization-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status'].upper()}: vectorized {len(passed)}/{len(results)} assets: {out}")
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError, FileNotFoundError) as error:
        raise SystemExit(f"ERROR: {error}") from None
