#!/usr/bin/env python3
"""Gate and package passing split-sheet batches into one visual asset pack."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


REQUIRED_BATCH_CHECKS = (
    "count", "order_and_semantics", "style_consistency", "identity_consistency",
    "no_duplicates_or_omissions", "crop_and_alpha", "naming",
)
REQUIRED_GLOBAL_CHECKS = (
    "style_anchor_adherence", "cross_batch_palette", "cross_batch_scale_and_padding",
    "character_identity", "global_semantic_coverage",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="batch-plan.json")
    parser.add_argument("--out", required=True, help="Fresh output directory")
    return parser.parse_args()


def safe_label(label: str) -> str:
    value = unicodedata.normalize("NFKC", label).strip()
    value = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    value = re.sub(r"\s+", "-", value)
    return re.sub(r"-+", "-", value).strip("-.") or "asset"


def font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def checkerboard(size: int) -> Image.Image:
    image = Image.new("RGB", (size, size), (244, 244, 244))
    draw = ImageDraw.Draw(image)
    square = 12
    for y in range(0, size, square):
        for x in range(0, size, square):
            if (x // square + y // square) % 2:
                draw.rectangle((x, y, x + square - 1, y + square - 1), fill=(218, 218, 218))
    return image


def contact_sheet(entries: list[dict[str, Any]], assets_dir: Path, target: Path) -> None:
    columns = min(6, max(1, math.ceil(math.sqrt(len(entries)))))
    tile, label_height = 150, 34
    rows = math.ceil(len(entries) / columns)
    sheet = Image.new("RGB", (columns * tile, rows * (tile + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    label_font = font(13)
    for offset, entry in enumerate(entries):
        row, column = divmod(offset, columns)
        x, y = column * tile, row * (tile + label_height)
        bg = checkerboard(tile)
        image = Image.open(assets_dir / entry["file"]).convert("RGBA")
        image.thumbnail((tile - 16, tile - 16), Image.Resampling.LANCZOS)
        bg.paste(image, ((tile - image.width) // 2, (tile - image.height) // 2), image)
        sheet.paste(bg, (x, y))
        draw.text((x + 5, y + tile + 6), f'{entry["index"]:02d} {entry["label"]}', fill=(20, 20, 20), font=label_font)
    sheet.save(target)


def write_typescript(entries: list[dict[str, Any]], path: Path) -> None:
    lines = ["export const Assets = {"]
    for entry in entries:
        key = re.sub(r"[^A-Za-z0-9_$]", "_", entry["id"])
        lines.append(f'  {key}: "./assets/{entry["file"]}",')
    lines.extend(["} as const;", "", "export type AssetName = keyof typeof Assets;", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def load_passing_json(path: Path, required: tuple[str, ...], label: str) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Missing {label}: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    failed = [name for name in required if data.get("checks", {}).get(name) is not True]
    if data.get("status") != "pass" or failed:
        raise ValueError(f"{label} did not pass: {failed or data.get('notes', [])}")
    return data


def main() -> int:
    args = parse_args()
    plan_path = Path(args.plan).expanduser().resolve()
    root = plan_path.parent
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out).expanduser().resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output directory: {out_dir}")

    cross = load_passing_json(root / plan.get("cross_batch_qa", "cross-batch-qa.json"),
                              ("count", "transparent_outputs", "safe_padding", "no_probable_duplicates", "style_metrics"),
                              "cross-batch deterministic QA")
    global_visual = load_passing_json(root / plan.get("global_visual_qa", "global-visual-qa.json"),
                                     REQUIRED_GLOBAL_CHECKS, "global visual QA")

    entries: list[dict[str, Any]] = []
    jobs: list[tuple[Path, str]] = []
    batch_summaries = []
    for batch in plan["batches"]:
        split_dir = root / batch["split_output"]
        split_report = load_passing_json(split_dir / "qa-report.json", (), f"splitter QA batch {batch['batch']}")
        if split_report.get("publish_gate", {}).get("passed") is not True:
            raise ValueError(f"Splitter publish gate failed for batch {batch['batch']}")
        mapping = json.loads((split_dir / "icon-map.json").read_text(encoding="utf-8"))
        if mapping.get("count") != batch["count"]:
            raise ValueError(f"Splitter count mismatch for batch {batch['batch']}")
        semantic = load_passing_json(root / batch["semantic_qa"], REQUIRED_BATCH_CHECKS,
                                     f"semantic QA batch {batch['batch']}")
        if semantic.get("expected_count") != batch["count"] or semantic.get("observed_count") != batch["count"]:
            raise ValueError(f"Semantic QA count mismatch for batch {batch['batch']}")
        for local, (planned, extracted) in enumerate(zip(batch["assets"], mapping["icons"]), 1):
            if extracted.get("label") != planned["label"]:
                raise ValueError(f"Naming mismatch in batch {batch['batch']} item {local}")
            index = planned["global_index"]
            filename = f"{index:03d}-{safe_label(planned['label'])}.png"
            source = split_dir / "icons" / extracted["file"]
            if not source.exists():
                raise ValueError(f"Missing extracted asset: {source}")
            jobs.append((source, filename))
            entries.append({
                "index": index, "id": planned["id"], "label": planned["label"],
                "description": planned["description"], "file": filename,
                "kind": plan["asset_kind"], "batch": batch["batch"], "batch_index": local,
            })
        batch_summaries.append({"batch": batch["batch"], "count": batch["count"], "status": "pass"})

    if len(entries) != plan["count"]:
        raise ValueError(f"Final count {len(entries)} does not match plan count {plan['count']}")
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for source, filename in jobs:
        shutil.copy2(source, assets_dir / filename)

    manifest = {
        "schema_version": 1, "project": plan["project"], "asset_kind": plan["asset_kind"],
        "style": plan["style"], "preset": plan.get("preset"), "count": len(entries),
        "formats": ["png"], "targets": plan.get("targets", ["generic"]), "assets": entries,
    }
    (out_dir / "asset-map.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qa = {"status": "pass", "count": len(entries), "batches": batch_summaries,
          "cross_batch": cross["summary"], "global_visual": global_visual["checks"]}
    (out_dir / "qa-summary.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_typescript(entries, out_dir / "assets.ts")
    contact_sheet(entries, assets_dir, out_dir / "contact-sheet.png")
    zip_path = out_dir / "asset-pack.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(assets_dir.glob("*.png")):
            archive.write(path, path.relative_to(out_dir))
        for name in ("asset-map.json", "assets.ts", "qa-summary.json", "contact-sheet.png"):
            archive.write(out_dir / name, name)
    print(f"PASS: packaged {len(entries)} assets: {zip_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError, FileNotFoundError) as error:
        raise SystemExit(f"ERROR: {error}") from None
