# Provider routing

Choose the cheapest route that can still meet the visual contract. Never mix routes silently.

## 1. Library first

Use Iconify only for generic `asset_kind=icon` work without character/IP references. Run `resolve_icon_sources.py` after planning. It searches only configured icon sets, records ranked candidates, downloads only high-confidence matches, sanitizes SVG, and leaves ambiguous concepts in `review`.

An exact name match is not proof of semantic or license fitness. Review the icon visually and verify the selected icon-set license before redistribution. Do not substitute a library icon for branded, character-specific, 3D, sticker, emoji, avatar, badge, or item-sprite work.

## 2. Native SVG generation

Use `generate_with_recraft.py` for unresolved generic icons when editable vector output is part of the request. The default is a dry run: it writes the full request plan and reviewed cost estimate without sending paid requests. `--execute` requires `RECRAFT_API_TOKEN`.

The V4.1 Vector route generates one named icon per request. This costs more operations than sheet-first raster generation, but avoids raster tracing, gives deterministic intent-to-file mapping, and produces editable SVG. Recraft V4 styles are prompt-controlled; `style_id` is restricted to compatible V3 models.

## 3. Sheet-first generation

Use the built-in image generation route for reference identity, 3D or painterly styles, character packs, stickers, and cases where cross-item visual cohesion matters more than editability. Preserve the original multi-sheet QA workflow.

## Packaging

- Raster sheet route: `package_asset_pack.py` after per-sheet and cross-batch QA.
- Mixed Iconify/Recraft SVG route: `package_vector_route.py` after a reviewed visual-QA JSON passes `semantic_mapping`, `style_consistency`, `license_review`, and `svg_safety`.
- Mixed raster and SVG packs require an explicit export plan; do not pretend the two sources share style without visual evidence.

Pricing is configuration, not a guarantee. Review `assets/provider-pricing.json` and its official source date before any paid run.
