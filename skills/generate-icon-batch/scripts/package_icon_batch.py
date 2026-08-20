#!/usr/bin/env python3
"""Gate and combine split icon-sheet batches into one production package."""

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


REQUIRED_CHECKS = (
    "count",
    "order_and_semantics",
    "style_consistency",
    "no_duplicates_or_omissions",
    "crop_and_alpha",
    "source_fidelity",
    "white_preservation",
    "naming",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="batch-plan.json from prepare_icon_batch.py")
    parser.add_argument("--out", required=True, help="Fresh output directory")
    return parser.parse_args()


def safe_label(label: str) -> str:
    normalized = unicodedata.normalize("NFKC", label).strip()
    normalized = re.sub(r"[\\/:*?\"<>|]+", "-", normalized)
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-.")
    return normalized or "icon"


def font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
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


def make_contact_sheet(entries: list[dict[str, Any]], icons_dir: Path, target: Path) -> None:
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
        icon = Image.open(icons_dir / entry["file"]).convert("RGBA")
        icon.thumbnail((tile - 16, tile - 16), Image.Resampling.LANCZOS)
        bg.paste(icon, ((tile - icon.width) // 2, (tile - icon.height) // 2), icon)
        sheet.paste(bg, (x, y))
        draw.text((x + 5, y + tile + 6), f'{entry["index"]:02d} {entry["label"]}', fill=(20, 20, 20), font=label_font)
    sheet.save(target)


def write_typescript(entries: list[dict[str, Any]], path: Path) -> None:
    lines = ["export const Icons = {"]
    lines.extend(f'  {entry["id"]}: "/assets/icons/{entry["file"]}",' for entry in entries)
    lines.append("} as const;\n")
    lines.append("export const IconLabels: Record<keyof typeof Icons, string> = {")
    lines.extend(f'  {entry["id"]}: {json.dumps(entry["label"], ensure_ascii=False)},' for entry in entries)
    lines.extend(["};", "", "export type IconName = keyof typeof Icons;", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def validate_semantic_qa(path: Path, batch: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Missing semantic QA: {path}")
    qa = json.loads(path.read_text(encoding="utf-8"))
    checks = qa.get("checks", {})
    failed = [name for name in REQUIRED_CHECKS if checks.get(name) is not True]
    if qa.get("status") != "pass" or failed:
        raise ValueError(f"Semantic QA did not pass for batch {batch['batch']}: {failed or qa.get('notes', [])}")
    if qa.get("expected_count") != batch["count"] or qa.get("observed_count") != batch["count"]:
        raise ValueError(f"Semantic QA count mismatch for batch {batch['batch']}")
    return qa


def main() -> int:
    args = parse_args()
    plan_path = Path(args.plan).expanduser().resolve()
    plan_root = plan_path.parent
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out).expanduser().resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output directory: {out_dir}")

    entries: list[dict[str, Any]] = []
    batch_summaries = []
    copy_jobs: list[tuple[Path, str]] = []
    for batch in plan["batches"]:
        split_dir = plan_root / batch["split_output"]
        split_report_path = split_dir / "qa-report.json"
        split_map_path = split_dir / "icon-map.json"
        if not split_report_path.exists() or not split_map_path.exists():
            raise ValueError(f"Missing splitter outputs for batch {batch['batch']}: {split_dir}")
        split_report = json.loads(split_report_path.read_text(encoding="utf-8"))
        split_map = json.loads(split_map_path.read_text(encoding="utf-8"))
        if split_report.get("status") != "pass" or split_report.get("publish_gate", {}).get("passed") is not True:
            raise ValueError(f"Splitter QA did not pass for batch {batch['batch']}")
        if split_map.get("count") != batch["count"]:
            raise ValueError(f"Splitter count mismatch for batch {batch['batch']}")
        semantic_qa = validate_semantic_qa(plan_root / batch["semantic_qa"], batch)

        for local_index, (planned, extracted) in enumerate(zip(batch["icons"], split_map["icons"]), 1):
            if extracted.get("label") != planned["label"]:
                raise ValueError(
                    f"Naming mismatch in batch {batch['batch']} item {local_index}: "
                    f"{extracted.get('label')!r} != {planned['label']!r}"
                )
            global_index = batch["global_start"] + local_index - 1
            filename = f"{global_index:03d}-{safe_label(planned['label'])}.png"
            source_icon = split_dir / "icons" / extracted["file"]
            if not source_icon.exists():
                raise ValueError(f"Missing extracted icon: {source_icon}")
            copy_jobs.append((source_icon, filename))
            entries.append(
                {
                    "index": global_index,
                    "id": f"icon{global_index:03d}",
                    "label": planned["label"],
                    "description": planned["description"],
                    "file": filename,
                    "batch": batch["batch"],
                    "batch_index": local_index,
                }
            )
        batch_summaries.append(
            {
                "batch": batch["batch"],
                "count": batch["count"],
                "splitter_status": split_report["status"],
                "semantic_status": semantic_qa["status"],
            }
        )

    if len(entries) != plan["count"]:
        raise ValueError(f"Final count {len(entries)} does not match plan count {plan['count']}")

    icons_dir = out_dir / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)
    for source_icon, filename in copy_jobs:
        shutil.copy2(source_icon, icons_dir / filename)

    manifest = {
        "project": plan["project"],
        "style": plan["style"],
        "count": len(entries),
        "icons": entries,
    }
    (out_dir / "icon-map.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qa_summary = {"status": "pass", "count": len(entries), "batches": batch_summaries}
    (out_dir / "qa-summary.json").write_text(json.dumps(qa_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_typescript(entries, out_dir / "icons.ts")
    make_contact_sheet(entries, icons_dir, out_dir / "contact-sheet.png")

    zip_path = out_dir / "icons.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(icons_dir.glob("*.png")):
            archive.write(path, path.relative_to(out_dir))
        for name in ("icon-map.json", "icons.ts", "qa-summary.json"):
            archive.write(out_dir / name, name)
    print(f"PASS: packaged {len(entries)} icons: {zip_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"ERROR: {error}") from None
