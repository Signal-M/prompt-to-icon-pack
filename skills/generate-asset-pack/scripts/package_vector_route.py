#!/usr/bin/env python3
"""Package a fully reviewed mixed Iconify/Recraft native-SVG route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import zipfile

from resolve_icon_sources import sanitize_svg


REQUIRED_QA = ("semantic_mapping", "style_consistency", "license_review", "svg_safety")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--library-resolution", required=True)
    parser.add_argument("--recraft-run")
    parser.add_argument("--visual-qa", required=True, help="Reviewed JSON approving semantics, style, license, and SVG safety")
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "icon"


def main() -> int:
    args = parse_args()
    plan_path = Path(args.plan).expanduser().resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assets = [asset for batch in plan.get("batches", []) for asset in batch.get("assets", [])]
    qa = json.loads(Path(args.visual_qa).read_text(encoding="utf-8"))
    failed = [name for name in REQUIRED_QA if qa.get("checks", {}).get(name) is not True]
    if qa.get("status") != "pass" or failed:
        raise ValueError(f"Vector-route visual QA did not pass: {failed}")

    library_path = Path(args.library_resolution).expanduser().resolve()
    library = json.loads(library_path.read_text(encoding="utf-8"))
    sources = {}
    for item in library.get("resolutions", []):
        if item.get("status") == "accepted" and item.get("file"):
            sources[str(item["id"])] = (library_path.parent / item["file"], "iconify", item.get("selected", {}).get("name"))
    if args.recraft_run:
        recraft_path = Path(args.recraft_run).expanduser().resolve()
        recraft = json.loads(recraft_path.read_text(encoding="utf-8"))
        if recraft.get("status") != "complete":
            raise ValueError("Recraft run is not complete")
        for item in recraft.get("outputs", []):
            sources[str(item["id"])] = (recraft_path.parent / item["file"], "recraft", recraft.get("model"))

    missing = [str(asset.get("id")) for asset in assets if str(asset.get("id")) not in sources]
    if missing:
        raise ValueError(f"Missing reviewed SVG source(s): {', '.join(missing)}")
    out_dir = Path(args.out).expanduser().resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError(f"Refusing to overwrite non-empty directory: {out_dir}")
    svg_dir = out_dir / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for index, asset in enumerate(assets, 1):
        source, provider, provider_asset = sources[str(asset["id"])]
        if not source.exists():
            raise ValueError(f"Missing SVG file: {source}")
        filename = f"{index:03d}-{safe_slug(str(asset['label']))}.svg"
        (svg_dir / filename).write_bytes(sanitize_svg(source.read_bytes()))
        entries.append({
            "index": index, "id": asset["id"], "label": asset["label"],
            "description": asset["description"], "file": f"svg/{filename}",
            "format": "svg", "provider": provider, "provider_asset": provider_asset,
        })
    manifest = {
        "schema_version": 1, "project": plan.get("project"), "asset_kind": "icon",
        "style": plan.get("style"), "count": len(entries), "formats": ["svg"], "assets": entries,
    }
    (out_dir / "asset-map.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(args.visual_qa, out_dir / "qa-summary.json")
    lines = ["export const Assets = {"]
    for entry in entries:
        key = re.sub(r"[^A-Za-z0-9_$]", "_", entry["id"])
        lines.append(f'  {key}: "./{entry["file"]}",')
    lines.extend(["} as const;", "", "export type AssetName = keyof typeof Assets;", ""])
    (out_dir / "assets.ts").write_text("\n".join(lines), encoding="utf-8")
    zip_path = out_dir / "asset-pack-svg.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(svg_dir.glob("*.svg")):
            archive.write(path, path.relative_to(out_dir))
        for name in ("asset-map.json", "assets.ts", "qa-summary.json"):
            archive.write(out_dir / name, name)
    print(f"PASS: packaged {len(entries)} reviewed SVG icons: {zip_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"ERROR: {error}")
