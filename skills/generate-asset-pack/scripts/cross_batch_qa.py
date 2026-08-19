#!/usr/bin/env python3
"""Run deterministic whole-pack QA across split asset batches."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="batch-plan.json")
    parser.add_argument("--strict", action="store_true", help="Fail on strong style metric drift")
    return parser.parse_args()


def average_hash(image: Image.Image, size: int = 12) -> str:
    rgba = image.convert("RGBA")
    white = Image.new("RGBA", rgba.size, "white")
    white.alpha_composite(rgba)
    gray = white.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    values = np.asarray(gray, dtype=np.float32)
    bits = values > values.mean()
    return "".join("1" if value else "0" for value in bits.ravel())


def hamming(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(left, right))


def metrics(path: Path) -> dict[str, Any]:
    image = Image.open(path).convert("RGBA")
    array = np.asarray(image)
    alpha = array[:, :, 3]
    mask = alpha > 8
    if not mask.any():
        raise ValueError(f"Empty transparent asset: {path}")
    ys, xs = np.where(mask)
    width, height = image.size
    bounds = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    bbox_w, bbox_h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    colors = array[:, :, :3][mask].astype(np.float32)
    return {
        "width": width, "height": height, "bounds": bounds,
        "fill_ratio": float(mask.mean()),
        "bbox_ratio": float(max(bbox_w / width, bbox_h / height)),
        "edge_margin": float(min(bounds[0], bounds[1], width - bounds[2], height - bounds[3]) / max(width, height)),
        "transparent_ratio": float((alpha == 0).mean()),
        "mean_rgb": [round(float(value), 2) for value in colors.mean(axis=0)],
        "hash": average_hash(image),
    }


def coefficient(values: list[float]) -> float:
    mean = sum(values) / len(values)
    if not mean:
        return 0.0
    return float(np.std(values) / mean)


def main() -> int:
    args = parse_args()
    plan_path = Path(args.plan).expanduser().resolve()
    root = plan_path.parent
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    missing: list[str] = []
    for batch in plan["batches"]:
        split_dir = root / batch["split_output"]
        map_path = split_dir / "icon-map.json"
        if not map_path.exists():
            missing.append(str(map_path))
            continue
        mapping = json.loads(map_path.read_text(encoding="utf-8"))
        extracted = mapping.get("icons", [])
        if len(extracted) != batch["count"]:
            missing.append(f"batch {batch['batch']} count {len(extracted)} != {batch['count']}")
            continue
        for planned, item in zip(batch["assets"], extracted):
            path = split_dir / "icons" / item["file"]
            if not path.exists():
                missing.append(str(path))
                continue
            records.append({
                "id": planned["id"], "label": planned["label"], "batch": batch["batch"],
                "file": str(path.relative_to(root)), "metrics": metrics(path),
            })

    duplicate_pairs = []
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            distance = hamming(left["metrics"]["hash"], right["metrics"]["hash"])
            if distance <= 4:
                duplicate_pairs.append({"left": left["id"], "right": right["id"], "hash_distance": distance})

    fills = [record["metrics"]["fill_ratio"] for record in records]
    boxes = [record["metrics"]["bbox_ratio"] for record in records]
    transparent = [record["metrics"]["transparent_ratio"] for record in records]
    clipped = [record["id"] for record in records if record["metrics"]["edge_margin"] < 0.012]
    no_transparency = [record["id"] for record in records if record["metrics"]["transparent_ratio"] < 0.08]
    style_warnings = []
    fill_cv = coefficient(fills) if fills else math.inf
    bbox_cv = coefficient(boxes) if boxes else math.inf
    if fill_cv > 0.42:
        style_warnings.append(f"foreground fill variation is high ({fill_cv:.3f})")
    if bbox_cv > 0.28:
        style_warnings.append(f"subject scale variation is high ({bbox_cv:.3f})")

    checks = {
        "count": not missing and len(records) == plan["count"],
        "transparent_outputs": not no_transparency,
        "safe_padding": not clipped,
        "no_probable_duplicates": not duplicate_pairs,
        "style_metrics": not style_warnings or not args.strict,
    }
    report = {
        "status": "pass" if all(checks.values()) else "needs_review",
        "expected_count": plan["count"], "observed_count": len(records), "checks": checks,
        "summary": {
            "median_fill_ratio": round(median(fills), 4) if fills else None,
            "median_bbox_ratio": round(median(boxes), 4) if boxes else None,
            "median_transparent_ratio": round(median(transparent), 4) if transparent else None,
            "fill_coefficient_of_variation": round(fill_cv, 4) if fills else None,
            "bbox_coefficient_of_variation": round(bbox_cv, 4) if boxes else None,
        },
        "missing_or_mismatched": missing, "clipped": clipped,
        "no_transparency": no_transparency, "probable_duplicates": duplicate_pairs,
        "style_warnings": style_warnings, "assets": records,
    }
    target = root / plan.get("cross_batch_qa", "cross-batch-qa.json")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status'].upper()}: cross-batch QA for {len(records)}/{plan['count']} assets: {target}")
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"ERROR: {error}") from None
