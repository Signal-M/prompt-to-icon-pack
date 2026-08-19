---
name: export-asset-pack
description: Export an existing transparent visual asset pack into production-oriented PNG and WebP size variants, a packed sprite sheet, CSS variables and classes, TypeScript mappings, target metadata, and a ZIP. Use when a user needs generated icons, emoji, stickers, avatars, badges, or sprites prepared for web, mini-program, React, Vue, iOS, Android, or generic application integration. Do not generate or split source art with this skill.
---

# Export Asset Pack

Convert a passing `asset-map.json` and transparent source assets into application-ready derivatives without modifying the originals.

## Run

```bash
PYTHON scripts/export_asset_pack.py \
  --manifest /absolute/path/asset-map.json \
  --assets /absolute/path/assets \
  --out /absolute/path/exported \
  --formats png,webp \
  --sizes 64,128,256 \
  --sprite \
  --targets web,mini-program
```

Use `contain` resizing: preserve aspect ratio, center optical content, and never stretch. Read [target guidance](references/targets.md) when the user names a platform.

## Outputs

- `png/<size>/` and `webp/<size>/`: normalized variants.
- `sprite/asset-sprite.png` and `sprite/asset-sprite.css`: packed raster sprite.
- `assets.ts`: typed asset metadata and paths.
- `assets.css`: CSS custom properties for web use.
- `export-manifest.json`: generated sizes, formats, targets, and provenance.
- `asset-export.zip`: all deployable outputs.

## Guardrails

- Require transparent PNG originals and a matching manifest.
- Never upscale unless the user explicitly requests it; upscaling does not create detail.
- Preserve stable IDs and labels across every format.
- Do not claim SVG support here; invoke `$vectorize-asset-pack` separately.
- Treat platform presets as packaging conventions, not as permission to publish externally.
