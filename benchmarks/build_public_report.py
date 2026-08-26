#!/usr/bin/env python3
"""Render evidence-based benchmark and 25-icon cost metrics as Markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True)
    parser.add_argument("--out", default=str(ROOT / "BENCHMARKS.md"))
    return parser.parse_args()


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> int:
    args = parse_args()
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    pricing_path = ROOT / "skills/generate-asset-pack/assets/provider-pricing.json"
    pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
    summary = result["summary"]
    recraft = pricing["providers"]["recraft"]
    direct_vector = 25 * float(recraft["recraftv4_1_vector"])
    three_sheets = 3
    call_saving = 1 - three_sheets / 25
    lines = [
        "# Benchmarks and cost model",
        "",
        f"Measured on the deterministic `{result['corpus']}` corpus ({result['corpus_count']} cases). Generated test art and ground-truth masks are CC0; reproduce them with the commands below.",
        "",
        "## Alpha quality",
        "",
        "| Backend | Mean IoU | Mean foreground recall | Mean white recall | Quality pass | False publish | Runtime |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| {result['backend']} | {pct(summary['mean_iou'])} | {pct(summary['mean_foreground_recall'])} | {pct(summary['mean_white_recall'])} | {pct(summary['quality_pass_rate'])} | {pct(summary['false_publish_rate'])} | {result['runtime_seconds']:.2f}s |",
        "",
        "A false publish means deterministic QA passed even though ground-truth IoU, recall, white retention, or leakage missed the published threshold. This is the most important safety metric for white-on-white failures.",
        "",
        "## 25-icon cost model",
        "",
        "| Route | Paid generation operations | Known API cost | What it optimizes |",
        "|---|---:|---:|---|",
        "| Iconify library-first | 0 | $0.00 | Existing generic UI concepts; verify icon-set license |",
        f"| Sheet-first raster (9 + 8 + 8) | {three_sheets} | Provider-dependent | {pct(call_saving)} fewer generation calls than 25 separate generations |",
        f"| Recraft V4.1 Vector, one SVG per icon | 25 | ${direct_vector:.2f} | Native editable SVG and deterministic file-to-intent mapping |",
        f"| Recraft background removal, 25 files | 25 | ${25 * float(recraft['remove_background']):.2f} | Optional utility route, not needed for native SVG |",
        "",
        f"Prices are configuration data reviewed on `{pricing['as_of']}` and should be rechecked before purchase: {pricing['sources']['recraft']}.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "python3 benchmarks/generate_synthetic_corpus.py --out /tmp/icon-alpha-1000",
        "python3 benchmarks/run_alpha_benchmark.py --corpus /tmp/icon-alpha-1000 --backend boundary --out benchmarks/results/boundary-1000.json",
        "python3 benchmarks/build_public_report.py --result benchmarks/results/boundary-1000.json",
        "```",
        "",
        "For BiRefNet/SAM comparisons, install `requirements-segmentation.txt` and rerun with `--backend ensemble` or the selected backend. Model identity and version belong in the result JSON.",
    ]
    target = Path(args.out).expanduser().resolve()
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
