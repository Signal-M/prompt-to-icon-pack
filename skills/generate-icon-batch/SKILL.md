---
name: generate-icon-batch
description: Compatibility entry point for generating a coherent batch of app, mini-program, game, or UI icons from a natural-language prompt, with sheet-first generation, non-grid splitting, white-safe transparency, semantic naming, QA, and ZIP packaging. Use for existing prompts that explicitly invoke generate-icon-batch. Delegate new work to generate-asset-pack with asset_kind icon; use split-icon-sheet when the user only wants to split an existing sheet.
---

# Generate Icon Batch

Preserve the original `$generate-icon-batch` interface while using the stronger generic pipeline.

1. Invoke `$generate-asset-pack` with `asset_kind: icon`.
2. Accept legacy specifications containing `icons`; the generic planner treats them as the canonical `assets` array.
3. Default to `balanced` density. Use `quality` for detailed 3D mascots and `economy` only for simple flat assets.
4. Follow the generic style-anchor, per-sheet QA, cross-batch QA, packaging, and retry gates.
5. Preserve legacy output expectations by including transparent PNGs, a manifest, TypeScript mapping, contact sheet, QA summary, and ZIP.

The original scripts remain bundled for reproducibility of v0.1 plans. Use the scripts in `$generate-asset-pack` for all new plans.
