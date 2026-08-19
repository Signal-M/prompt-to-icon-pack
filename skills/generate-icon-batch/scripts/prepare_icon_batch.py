#!/usr/bin/env python3
"""Validate an icon specification and create deterministic sheet-generation batches."""

from __future__ import annotations

import argparse
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="UTF-8 JSON icon specification")
    parser.add_argument("--out", required=True, help="Directory for the batch plan")
    parser.add_argument("--batch-size", type=int, default=16, help="Icons per generated sheet")
    return parser.parse_args()


def load_spec(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("The specification must be a JSON object")
    style = str(data.get("style", "")).strip()
    if not style:
        raise ValueError("The specification requires a non-empty 'style'")
    raw_items = data.get("icons")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("The specification requires a non-empty 'icons' array")
    raw_constraints = data.get("constraints", [])
    if not isinstance(raw_constraints, list):
        raise ValueError("'constraints' must be an array of strings")

    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_items, 1):
        if isinstance(raw, str):
            label = description = raw.strip()
        elif isinstance(raw, dict):
            label = str(raw.get("label", "")).strip()
            description = str(raw.get("description", label)).strip()
        else:
            raise ValueError(f"Icon {index} must be a string or object")
        if not label or not description:
            raise ValueError(f"Icon {index} requires label and description")
        if label in seen:
            raise ValueError(f"Duplicate label: {label}")
        if "\n" in label:
            raise ValueError(f"Icon {index} label must fit on one line")
        seen.add(label)
        items.append({"label": label, "description": description})

    return {
        "project": str(data.get("project", "icon-batch")).strip() or "icon-batch",
        "style": style,
        "constraints": [str(value).strip() for value in raw_constraints if str(value).strip()],
        "icons": items,
    }


def layout_for(count: int) -> tuple[int, int]:
    pairs = [
        (rows, count // rows)
        for rows in range(1, math.isqrt(count) + 1)
        if count % rows == 0
    ]
    rows, columns = min(pairs, key=lambda pair: pair[1] / pair[0])
    return rows, columns


def plan_batch_counts(total: int, maximum: int) -> list[int]:
    """Prefer full rectangular layouts over a partially filled final row."""
    candidates = []
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
            shape_penalty = 8.0 if rows == 1 and count > 1 else 0.0
            shape_penalty += columns / rows - 1.0
            score = 100.0 + shape_penalty + child[0]
            option = score, (count,) + child[1]
            if best is None or option[0] < best[0] or (
                option[0] == best[0] and option[1] > best[1]
            ):
                best = option
        return best

    result = solve(total)
    if result is None:
        raise ValueError(f"Cannot partition {total} icons into batches up to {maximum}")
    return list(result[1])


def build_prompt(spec: dict[str, Any], items: list[dict[str, str]], rows: int, columns: int) -> str:
    ordered = "\n".join(
        f'{index}. {item["label"]}: {item["description"]}'
        for index, item in enumerate(items, 1)
    )
    extra = "; ".join(spec["constraints"]) or "none beyond the requirements below"
    return f"""Use case: stylized-concept
Asset type: production UI icon sheet for later automatic splitting
Primary request: create exactly {len(items)} distinct icons in the exact reading order listed below
Shared style: {spec['style']}
Scene/backdrop: one perfectly uniform bright neutral white background across the whole canvas
Composition: {rows} rows by {columns} columns; fill positions left-to-right, top-to-bottom; one compact icon cluster per position; generous equal blank space; no overlap; no shared scene
Ordered icon intents:
{ordered}
The labels above are semantic planning names only. Do not render them or any other text in the image.
User constraints: {extra}
Constraints: exact count {len(items)}; every intent appears once; cohesive scale, perspective, stroke weight, lighting, palette, and detail level; each icon fully visible with ample padding; preserve intentional white details; keep any detached decorations close to their icon
Avoid: captions, labels, letters, numbers, watermarks, unrequested logos, duplicate concepts, extra icons, cropped subjects, separator lines, card frames, decorative objects between icons, shadows or texture in the exterior background
"""


def main() -> int:
    args = parse_args()
    if not 1 <= args.batch_size <= 25:
        raise SystemExit("--batch-size must be between 1 and 25")
    spec_path = Path(args.spec).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = load_spec(spec_path)

    batches = []
    start = 0
    for batch_index, batch_count in enumerate(
        plan_batch_counts(len(spec["icons"]), args.batch_size), 1
    ):
        items = spec["icons"][start : start + batch_count]
        rows, columns = layout_for(len(items))
        batch_name = f"batch-{batch_index:02d}"
        batch_dir = out_dir / batch_name
        batch_dir.mkdir(parents=True, exist_ok=True)
        labels_path = batch_dir / "labels.txt"
        prompt_path = batch_dir / "generation-prompt.txt"
        labels_path.write_text("\n".join(item["label"] for item in items) + "\n", encoding="utf-8")
        prompt_path.write_text(build_prompt(spec, items, rows, columns), encoding="utf-8")
        batches.append(
            {
                "batch": batch_index,
                "directory": batch_name,
                "global_start": start + 1,
                "global_end": start + len(items),
                "count": len(items),
                "rows": rows,
                "columns": columns,
                "labels_file": f"{batch_name}/labels.txt",
                "prompt_file": f"{batch_name}/generation-prompt.txt",
                "source_sheet": f"{batch_name}/generated-sheet.png",
                "split_output": f"{batch_name}/split",
                "semantic_qa": f"{batch_name}/semantic-qa.json",
                "icons": items,
            }
        )
        start += batch_count

    plan = {
        "version": 1,
        "project": spec["project"],
        "style": spec["style"],
        "constraints": spec["constraints"],
        "count": len(spec["icons"]),
        "batch_size": args.batch_size,
        "batches": batches,
    }
    plan_path = out_dir / "batch-plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(batches)} sheet(s) for {len(spec['icons'])} icons: {plan_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"ERROR: {error}") from None
