# Benchmarks and cost model

Measured on the deterministic `white-safe-icon-alpha-1000` corpus (1000 cases). Generated test art and ground-truth masks are CC0; reproduce them with the commands below.

## Alpha quality

| Backend | Mean IoU | Mean foreground recall | Mean white recall | Quality pass | False publish | Runtime |
|---|---:|---:|---:|---:|---:|---:|
| boundary | 93.9% | 96.3% | 87.5% | 75.0% | 12.5% | 14.26s |

A false publish means deterministic QA passed even though ground-truth IoU, recall, white retention, or leakage missed the published threshold. This is the most important safety metric for white-on-white failures.

## 25-icon cost model

| Route | Paid generation operations | Known API cost | What it optimizes |
|---|---:|---:|---|
| Iconify library-first | 0 | $0.00 | Existing generic UI concepts; verify icon-set license |
| Sheet-first raster (9 + 8 + 8) | 3 | Provider-dependent | 88.0% fewer generation calls than 25 separate generations |
| Recraft V4.1 Vector, one SVG per icon | 25 | $2.00 | Native editable SVG and deterministic file-to-intent mapping |
| Recraft background removal, 25 files | 25 | $0.25 | Optional utility route, not needed for native SVG |

Prices are configuration data reviewed on `2026-08-26` and should be rechecked before purchase: https://www.recraft.ai/pricing?tab=api.

## Reproduce

```bash
python3 benchmarks/generate_synthetic_corpus.py --out /tmp/icon-alpha-1000
python3 benchmarks/run_alpha_benchmark.py --corpus /tmp/icon-alpha-1000 --backend boundary --out benchmarks/results/boundary-1000.json
python3 benchmarks/build_public_report.py --result benchmarks/results/boundary-1000.json
```

For BiRefNet/SAM comparisons, install `requirements-segmentation.txt` and rerun with `--backend ensemble` or the selected backend. Model identity and version belong in the result JSON.
