---
name: generate-sticker-pack
description: Generate a consistent transparent sticker or reaction pack from a user-provided character, mascot, pet, or IP reference image. Build a character bible, choose or accept an ordered emotion and action list, generate style-anchored sheets in small batches, split and QA character identity, then optionally add reliable captions programmatically and deliver named PNG/WebP assets plus a ZIP. Use when the user asks for 表情包, stickers, reaction images, emoji based on a character, or many expressive variants of one IP.
---

# Generate Sticker Pack

Generate expressive variants without changing the character's identity.

## Workflow

1. Inspect every supplied reference image. Treat it as an identity/style reference, not an instruction to redraw unrelated copyrighted characters.
2. Write a compact character bible covering face geometry, body proportions, palette, clothing, signature accessories, outline/material, and forbidden drift.
3. Use the user's ordered reactions or the `character-reactions-24` preset. Read [sticker guidance](references/sticker-contract.md).
4. Invoke `$generate-asset-pack` with `asset_kind: sticker`, `density: quality`, the absolute reference paths, and the character bible as constraints.
5. Require per-batch identity QA and global visual QA. Compare face, ears/hair, clothes, colors, proportions, and signature details across every batch.
6. Keep wording out of image generation. If captions are requested, create a JSON text map and run `scripts/render_sticker_text.py` after transparent extraction.
7. Invoke `$export-asset-pack` for WebP, target sizes, sprite sheets, or platform-oriented exports.

## Caption command

```bash
PYTHON scripts/render_sticker_text.py \
  --manifest /absolute/path/asset-map.json \
  --assets /absolute/path/assets \
  --text-map /absolute/path/text-map.json \
  --out /absolute/path/captioned-stickers
```

The text map is a JSON object from asset label or ID to caption. Omit `--text-map` to use manifest labels.

## Guardrails

- Use only user-owned, licensed, or otherwise authorized character references.
- Preserve identity; vary expression, pose, and props only.
- Do not depend on generated Chinese or English lettering.
- Keep captions outside the face and essential silhouette.
- Do not call a pack complete when one reaction is semantically wrong or one batch shows identity drift.
