---
name: generate-asset-pack
description: Generate coherent, production-ready batches of icons, emoji, stickers, avatars, badges, or item sprites from a natural-language prompt or reference image. Plan up to 50 or more named assets across style-anchored sheets, split them without assuming a rigid grid, preserve internal white details while removing only exterior backgrounds, run per-sheet and cross-batch closed-loop QA, and package transparent PNG assets with manifests and a ZIP. Use when a user wants a complete visual asset pack rather than a single image. Use split-icon-sheet for splitting an existing sheet only.
---

# Generate Asset Pack

Turn one brief into a coherent, named, QA-gated visual asset pack. Keep the asset specification outside generated pixels and treat it as the naming source of truth.

## Workflow

1. Classify `asset_kind` as `icon`, `emoji`, `sticker`, `avatar`, `badge`, or `item-sprite`.
2. Build an ordered specification. If the user gives no list, select a conservative preset from [preset guidance](references/preset-guide.md). Do not silently use emoji for an app-icon request.
3. Save the specification as JSON and run `scripts/prepare_asset_pack.py`. Prefer `quality` for character art, `balanced` for ordinary icons, and `economy` only when density matters more than detail.
4. Read [provider routing](references/provider-routing.md). For generic icons without reference identity, run library-first resolution. Review exact matches and licenses; never auto-accept an ambiguous semantic candidate.
5. Route unresolved assets deliberately: use Recraft native SVG when editability matters, or continue with sheet-first image generation for reference identity, character art, 3D, stickers, or stronger within-pack cohesion.
6. For character or cross-sheet work, create one style anchor before generating all batches. Keep the same reference image, palette, proportions, viewpoint, material, outline, and lighting contract in every generation.
7. For the sheet route, read [the generation contract](references/generation-contract.md). Generate each planned sheet with the built-in image-generation tool. Never render planning labels or filenames into a sheet.
8. Run `$split-icon-sheet` in unlabeled mode with each batch's `labels.txt`. Prefer its semantic ensemble for white-on-white character art when the optional dependency is available.
9. Inspect each source sheet, detection debug image, `qa-comparison.png`, and transparent outputs. On the colored comparison panels, verify that no source-white semantic region became transparent. Write `semantic-qa.json` using [the QA schema](references/qa-rubric.md). Prefer a fresh independent QA subagent with raw artifacts only.
10. Classify failures before retrying. Regenerate generation failures; rerun extraction for crop or alpha failures; correct only the external mapping for naming failures. Retry a failed batch at most three times.
11. After every sheet batch passes, run `scripts/cross_batch_qa.py`. Compare style and identity visually across all sheets, then write `global-visual-qa.json`.
12. Package with the route-specific gate. Use `package_asset_pack.py` for raster sheets or `package_vector_route.py` for a fully reviewed Iconify/Recraft SVG route. Do not package missing, partial, uncertain, unlicensed, or failed work as complete.

## Commands

```bash
PYTHON scripts/prepare_asset_pack.py \
  --spec /absolute/path/asset-spec.json \
  --out /absolute/path/asset-plan

PYTHON scripts/resolve_icon_sources.py \
  --plan /absolute/path/asset-plan/batch-plan.json \
  --out /absolute/path/library-candidates \
  --download

PYTHON scripts/generate_with_recraft.py \
  --plan /absolute/path/asset-plan/batch-plan.json \
  --library-resolution /absolute/path/library-candidates/library-resolution.json \
  --out /absolute/path/recraft-plan

PYTHON scripts/cross_batch_qa.py \
  --plan /absolute/path/asset-plan/batch-plan.json

PYTHON scripts/package_asset_pack.py \
  --plan /absolute/path/asset-plan/batch-plan.json \
  --out /absolute/path/final-assets
```

Use a Python interpreter containing Pillow and NumPy. In Codex desktop, load the bundled workspace dependencies instead of installing packages.

## Specification

Accept `assets` as the canonical item array and `icons` as a legacy alias. Each item requires a unique `label` and a concrete `description`.

```json
{
  "project": "cat-reactions",
  "asset_kind": "sticker",
  "preset": "character-reactions-24",
  "style": "soft 3D lime-green cat mascot",
  "density": "quality",
  "reference_images": ["/absolute/path/cat.png"],
  "constraints": ["keep the same face, ears, clothes, and proportions"]
}
```

## Guardrails

- Generate multiple complete sheets for large packs; never force 40–50 detailed assets into one canvas.
- Search reviewed libraries before generating generic UI icons. Never use library substitution for reference identity, character art, or an uncertain semantic match.
- Keep paid provider adapters in dry-run mode until the request plan and current pricing have been reviewed.
- Bind names by ordered intent, not OCR or semantic guessing.
- Remove only bright neutral background connected to a local crop boundary. Preserve enclosed white, highlights, eyes, clothes, and embedded art.
- Keep sticker wording out of image generation. Add reliable text after extraction with `$generate-sticker-pack`.
- Use user-owned or authorized character references.
- Withhold the final ZIP when count, semantics, identity, style, crop, alpha, source fidelity, white preservation, naming, or cross-batch QA remains unresolved.
