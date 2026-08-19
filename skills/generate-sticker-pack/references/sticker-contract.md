# Sticker contract

## Character bible

Record these immutable attributes before generation:

- head and face geometry;
- eye, nose, mouth, ear, hair, or whisker shapes;
- body-to-head ratio;
- exact dominant colors;
- clothing and signature accessories;
- rendering material, outline, and lighting;
- details that must never disappear or move.

## Generation

- Prefer nine stickers per sheet.
- Exaggerate pose and facial expression while preserving identity.
- Keep hands, ears, tails, props, sparkles, and tears fully visible.
- Use no captions or speech bubbles during generation.
- Keep the exterior background uniformly bright and neutral.

## QA

Judge both emotion and identity. A beautiful sticker fails when the requested emotion is unclear, the character changes clothing or face shape, detached details are clipped, or the alpha mask damages white features.

## Captions

Render captions after splitting. Use a font with the required glyph coverage, high-contrast fill, and an outline. Keep the text map independent from filenames so wording can be localized without regenerating art.
