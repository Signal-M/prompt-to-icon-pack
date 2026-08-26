#!/usr/bin/env python3
"""Evaluate splitter alpha output against a generated ground-truth corpus."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SPLITTER = ROOT / "skills/split-icon-sheet/scripts/split_icon_sheet.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, help="Generated corpus directory")
    parser.add_argument("--out", required=True, help="JSON result")
    parser.add_argument("--backend", choices=("boundary", "auto", "birefnet", "sam", "ensemble"), default="boundary")
    parser.add_argument("--rembg-model", default="birefnet-general-lite")
    return parser.parse_args()


def load_splitter():
    spec = importlib.util.spec_from_file_location("benchmark_splitter", SPLITTER)
    if not spec or not spec.loader:
        raise RuntimeError("Unable to import splitter")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {"count": 0}
    fields = ("iou", "foreground_recall", "white_recall", "background_leak_rate")
    result = {"count": len(rows)}
    for field in fields:
        values = [float(row[field]) for row in rows]
        result[f"mean_{field}"] = round(sum(values) / len(values), 6)
        result[f"min_{field}"] = round(min(values), 6)
    result["quality_pass_rate"] = round(sum(row["quality_pass"] for row in rows) / len(rows), 6)
    result["qa_pass_rate"] = round(sum(row["qa_pass"] for row in rows) / len(rows), 6)
    result["false_publish_rate"] = round(sum(row["qa_pass"] and not row["quality_pass"] for row in rows) / len(rows), 6)
    return result


def main() -> int:
    args = parse_args()
    corpus = Path(args.corpus).expanduser().resolve()
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    splitter = load_splitter()
    started = time.perf_counter()
    rows = []
    for case in manifest["cases"]:
        source = Image.open(corpus / case["source"]).convert("RGBA")
        gt = np.asarray(Image.open(corpus / case["alpha"]).convert("L"), dtype=np.uint8) >= 20
        candidates = splitter.segmentation_candidates(source, 238, 18, args.backend, args.rembg_model)
        selected = None
        selected_qa = None
        for name, rgba, _meta in candidates:
            qa = splitter.qa_segment(rgba, source, [0, 0, source.width, source.height], source.size, source.width / 2, (None, None))
            if selected is None or qa["passed"]:
                selected = (name, rgba)
                selected_qa = qa
            if qa["passed"]:
                break
        assert selected is not None and selected_qa is not None
        pred = selected[1][:, :, 3] >= 20
        intersection = int((pred & gt).sum())
        union = int((pred | gt).sum())
        gt_count = int(gt.sum())
        bg_count = int((~gt).sum())
        rgb = np.asarray(source.convert("RGB"), dtype=np.uint8)
        white_gt = gt & (rgb.min(axis=2) >= 238) & ((rgb.max(axis=2) - rgb.min(axis=2)) <= 18)
        iou = intersection / max(1, union)
        recall = intersection / max(1, gt_count)
        white_count = int(white_gt.sum())
        white_recall = int((pred & white_gt).sum()) / white_count if white_count else 1.0
        leak = int((pred & ~gt).sum()) / max(1, bg_count)
        quality_pass = iou >= 0.97 and recall >= 0.98 and white_recall >= 0.95 and leak <= 0.01
        rows.append({
            "id": case["id"], "category": case["category"], "candidate": selected[0],
            "iou": iou, "foreground_recall": recall, "white_recall": white_recall,
            "background_leak_rate": leak, "quality_pass": quality_pass, "qa_pass": bool(selected_qa["passed"]),
        })
    categories = {name: aggregate([row for row in rows if row["category"] == name]) for name in manifest["categories"]}
    result = {
        "version": 1,
        "corpus": manifest["name"],
        "corpus_count": len(rows),
        "backend": args.backend,
        "rembg_model": args.rembg_model if args.backend != "boundary" else None,
        "thresholds": {"iou": 0.97, "foreground_recall": 0.98, "white_recall": 0.95, "background_leak_rate_max": 0.01},
        "summary": aggregate(rows),
        "categories": categories,
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "sample_failures": [row for row in rows if not row["quality_pass"]][:20],
    }
    target = Path(args.out).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
