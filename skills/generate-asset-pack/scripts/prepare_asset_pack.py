#!/usr/bin/env python3
"""Validate a visual asset specification and create style-anchored sheet batches."""

from __future__ import annotations

import argparse
from functools import lru_cache
import json
import math
from pathlib import Path
import re
from typing import Any


ASSET_KINDS = {"icon", "emoji", "sticker", "avatar", "badge", "item-sprite"}
DENSITY_LIMITS = {"quality": 9, "balanced": 15, "economy": 25}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="UTF-8 JSON asset specification")
    parser.add_argument("--out", required=True, help="Directory for the batch plan")
    parser.add_argument("--batch-size", type=int, help="Override the density profile maximum")
    return parser.parse_args()


def preset_catalog() -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / "assets" / "presets.json"
    return json.loads(path.read_text(encoding="utf-8"))


def expand_preset(name: str, catalog: dict[str, Any]) -> tuple[str, list[Any]]:
    if name not in catalog:
        raise ValueError(f"Unknown preset: {name}")
    record = catalog[name]
    items: list[Any] = []
    if record.get("extends"):
        _, inherited = expand_preset(str(record["extends"]), catalog)
        items.extend(inherited)
    items.extend(record.get("items", []))
    return str(record.get("asset_kind", "icon")), items


def normalize_item(raw: Any, index: int) -> dict[str, str]:
    if isinstance(raw, str):
        label = description = raw.strip()
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        label, description = (str(raw[0]).strip(), str(raw[1]).strip())
    elif isinstance(raw, dict):
        label = str(raw.get("label", "")).strip()
        description = str(raw.get("description", label)).strip()
    else:
        raise ValueError(f"Asset {index} must be a string, [label, description], or object")
    if not label or not description:
        raise ValueError(f"Asset {index} requires label and description")
    if "\n" in label:
        raise ValueError(f"Asset {index} label must fit on one line")
    return {"label": label, "description": description}


def load_spec(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("The specification must be a JSON object")

    catalog = preset_catalog()
    preset = str(data.get("preset", "")).strip()
    raw_items = data.get("assets", data.get("icons"))
    preset_kind = "icon"
    if raw_items is None:
        if not preset:
            preset = "universal-ui-24"
        preset_kind, raw_items = expand_preset(preset, catalog)
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("The specification requires assets/icons or a non-empty preset")

    asset_kind = str(data.get("asset_kind", preset_kind)).strip().lower()
    if asset_kind not in ASSET_KINDS:
        raise ValueError(f"asset_kind must be one of: {', '.join(sorted(ASSET_KINDS))}")
    style = str(data.get("style", "")).strip()
    if not style:
        style = "cohesive, friendly, production-ready visual assets with clear silhouettes"
    density = str(data.get("density", "quality" if asset_kind in {"sticker", "avatar"} else "balanced")).strip().lower()
    if density not in DENSITY_LIMITS:
        raise ValueError(f"density must be one of: {', '.join(DENSITY_LIMITS)}")

    requested_count = data.get("count")
    if requested_count is not None:
        requested_count = int(requested_count)
        if requested_count < 1:
            raise ValueError("count must be positive")
        if requested_count > len(raw_items):
            raise ValueError(f"Preset or assets only contains {len(raw_items)} items, fewer than count={requested_count}")
        raw_items = raw_items[:requested_count]

    items = [normalize_item(raw, index) for index, raw in enumerate(raw_items, 1)]
    seen: set[str] = set()
    for item in items:
        key = item["label"].casefold()
        if key in seen:
            raise ValueError(f"Duplicate label: {item['label']}")
        seen.add(key)

    constraints = data.get("constraints", [])
    references = data.get("reference_images", [])
    palette = data.get("palette", [])
    formats = data.get("formats", ["png"])
    targets = data.get("targets", ["generic"])
    for field, value in (("constraints", constraints), ("reference_images", references), ("palette", palette), ("formats", formats), ("targets", targets)):
        if not isinstance(value, list):
            raise ValueError(f"{field} must be an array")

    return {
        "project": str(data.get("project", "asset-pack")).strip() or "asset-pack",
        "asset_kind": asset_kind,
        "preset": preset or None,
        "style": style,
        "density": density,
        "constraints": [str(v).strip() for v in constraints if str(v).strip()],
        "reference_images": [str(v).strip() for v in references if str(v).strip()],
        "palette": [str(v).strip() for v in palette if str(v).strip()],
        "formats": [str(v).strip().lower() for v in formats if str(v).strip()],
        "targets": [str(v).strip().lower() for v in targets if str(v).strip()],
        "assets": items,
    }


def layout_for(count: int) -> tuple[int, int]:
    pairs = [(rows, count // rows) for rows in range(1, math.isqrt(count) + 1) if count % rows == 0]
    return min(pairs, key=lambda pair: (pair[1] / pair[0], pair[1]))


def plan_batch_counts(total: int, maximum: int) -> list[int]:
    candidates: list[int] = []
    for count in range(1, maximum + 1):
        rows, columns = layout_for(count)
        if count <= 3 or (rows >= 2 and columns / rows <= 2.5):
            candidates.append(count)
    candidates.sort(reverse=True)

    @lru_cache(maxsize=None)
    def solve(remaining: int) -> tuple[float, tuple[int, ...]] | None:
        if remaining == 0:
            return 0.0, ()
        best = None
        for count in candidates:
            if count > remaining:
                continue
            child = solve(remaining - count)
            if child is None:
                continue
            rows, columns = layout_for(count)
            penalty = 100.0 + (8.0 if rows == 1 and count > 1 else 0.0) + columns / rows - 1.0
            option = penalty + child[0], (count,) + child[1]
            if best is None or option[0] < best[0] or (option[0] == best[0] and option[1] > best[1]):
                best = option
        return best

    result = solve(total)
    if result is None:
        raise ValueError(f"Cannot partition {total} assets into batches up to {maximum}")
    return list(result[1])


def slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return value or "asset"


def build_prompt(spec: dict[str, Any], items: list[dict[str, str]], rows: int, columns: int, batch_index: int) -> str:
    ordered = "\n".join(f'{i}. {item["label"]}: {item["description"]}' for i, item in enumerate(items, 1))
    constraints = "; ".join(spec["constraints"]) or "none beyond this contract"
    palette = ", ".join(spec["palette"]) or "derive a restrained palette from the shared style"
    reference_note = (
        "Use the supplied reference image(s) only as identity and style anchors; preserve defining geometry, colors, clothing, and accessories."
        if spec["reference_images"] else
        "Use the first approved sheet or pilot asset as the immutable style anchor for later batches."
    )
    return f"""Use case: coherent-{spec['asset_kind']}-pack
Asset type: {spec['asset_kind']} sheet for later automatic splitting
Batch: {batch_index}
Primary request: create exactly {len(items)} distinct assets in the exact reading order below
Shared style contract: {spec['style']}
Palette contract: {palette}
Style-anchor contract: {reference_note}
Scene/backdrop: one perfectly uniform bright neutral white exterior background across the whole canvas
Composition: {rows} rows by {columns} columns; fill left-to-right, top-to-bottom; one compact isolated asset cluster per position; generous blank separation; no overlap or shared scene
Ordered intents:
{ordered}
The labels are planning metadata only. Do not render labels, captions, letters, numbers, or filenames.
User constraints: {constraints}
Consistency: exact count; every intent once; fixed character identity when applicable; cohesive scale, viewpoint, stroke/material, lighting, palette, silhouette language, padding, and detail level across every batch
Avoid: text, watermarks, unrequested logos, duplicate concepts, extra assets, cropped subjects, separator lines, cards, decorative objects between assets, exterior background shadows or texture
"""


def main() -> int:
    args = parse_args()
    spec_path = Path(args.spec).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = load_spec(spec_path)
    maximum = args.batch_size or DENSITY_LIMITS[spec["density"]]
    if not 1 <= maximum <= 25:
        raise ValueError("batch size must be between 1 and 25")

    style_contract = {
        "version": 1,
        "asset_kind": spec["asset_kind"],
        "style": spec["style"],
        "palette": spec["palette"],
        "constraints": spec["constraints"],
        "reference_images": spec["reference_images"],
        "immutable_across_batches": ["identity", "palette", "proportions", "viewpoint", "stroke_or_material", "lighting", "padding"],
    }
    (out_dir / "style-contract.json").write_text(json.dumps(style_contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "asset-spec.normalized.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    batches = []
    start = 0
    counts = plan_batch_counts(len(spec["assets"]), maximum)
    for batch_index, count in enumerate(counts, 1):
        items = spec["assets"][start:start + count]
        rows, columns = layout_for(count)
        name = f"batch-{batch_index:02d}"
        batch_dir = out_dir / name
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / "labels.txt").write_text("\n".join(item["label"] for item in items) + "\n", encoding="utf-8")
        (batch_dir / "generation-prompt.txt").write_text(build_prompt(spec, items, rows, columns, batch_index), encoding="utf-8")
        batch_assets = []
        for local, item in enumerate(items, 1):
            global_index = start + local
            batch_assets.append({**item, "id": f"asset-{global_index:03d}-{slug(item['label'])}", "global_index": global_index})
        batches.append({
            "batch": batch_index, "directory": name, "global_start": start + 1,
            "global_end": start + count, "count": count, "rows": rows, "columns": columns,
            "labels_file": f"{name}/labels.txt", "prompt_file": f"{name}/generation-prompt.txt",
            "source_sheet": f"{name}/generated-sheet.png", "split_output": f"{name}/split",
            "semantic_qa": f"{name}/semantic-qa.json", "assets": batch_assets,
        })
        start += count

    plan = {
        "version": 2, "project": spec["project"], "asset_kind": spec["asset_kind"],
        "preset": spec["preset"], "style": spec["style"], "density": spec["density"],
        "constraints": spec["constraints"], "reference_images": spec["reference_images"],
        "formats": spec["formats"], "targets": spec["targets"], "count": len(spec["assets"]),
        "batch_size": maximum, "style_contract": "style-contract.json",
        "cross_batch_qa": "cross-batch-qa.json", "global_visual_qa": "global-visual-qa.json",
        "requires_style_anchor": len(counts) > 1 or spec["asset_kind"] in {"sticker", "avatar"},
        "batches": batches,
    }
    target = out_dir / "batch-plan.json"
    target.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(batches)} sheet(s) for {plan['count']} {spec['asset_kind']} assets: {target}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"ERROR: {error}") from None
