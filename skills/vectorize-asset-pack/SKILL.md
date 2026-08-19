---
name: vectorize-asset-pack
description: Produce safe, optimized, QA-validated SVG assets from an icon or visual asset pack using either native semantic SVG artwork or optional color raster tracing. Use for flat, outline, solid, limited-palette, logo-like, or simple UI assets that benefit from editable vectors. Sanitize SVG content, optimize it, render it back to PNG, compare it with the source, and keep raster fallbacks for gradients, 3D art, fur, glass, soft shadows, or overly complex traced output.
---

# Vectorize Asset Pack

Create SVG only when it is an improvement over the raster source.

## Choose a mode

- `native`: prefer for flat, outline, solid, or limited-palette UI icons. Create semantic SVG markup with a stable `viewBox`, consistent strokes, reusable palette tokens, and few paths.
- `trace`: use VTracer for suitable existing PNG assets when reproducing their shapes matters more than editability.
- `auto`: trace only assets that pass limited-palette eligibility; retain PNG for the rest.

Read [vector policy](references/vector-policy.md) before choosing. Do not trace detailed 3D stickers merely to claim SVG support.

## Run

```bash
PYTHON scripts/vectorize_asset_pack.py \
  --manifest /absolute/path/asset-map.json \
  --assets /absolute/path/assets \
  --out /absolute/path/vectorized \
  --mode auto
```

For `native`, place source SVG files named after the raster stems in the assets directory or a separate `--svg-source` directory.

The script sanitizes the XML, rejects active/external content, limits path complexity and file size, renders each SVG with CairoSVG, and performs alpha-aware pixel QA against the matching PNG. It writes `vectorization-report.json` and returns a non-zero status when any requested SVG remains unverified.

## Dependencies

- VTracer CLI for `trace` or `auto` conversion.
- CairoSVG for mandatory render-back QA.
- SVGO is recommended as an additional optimization pass after validation, never as the security boundary.

## Guardrails

- Keep the original PNG/WebP as the canonical fallback.
- Reject scripts, event handlers, foreign objects, entities, external URLs, and embedded raster images.
- Require a `viewBox` and a successful render-back comparison.
- Skip SVG when it has excessive paths, excessive bytes, or unacceptable visual error.
- Never describe traced gradients or photographs as clean editable vector artwork.
