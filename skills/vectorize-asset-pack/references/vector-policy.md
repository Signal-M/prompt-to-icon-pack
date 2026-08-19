# Vector policy

## Prefer native SVG

Use native semantic SVG for icons built from simple geometry, flat fills, consistent strokes, and a small palette. Validate geometry at the intended small display sizes as well as at large preview size.

## Allow tracing

Allow color tracing when the raster has a clean transparent boundary, limited colors, crisp shapes, and little texture. A traced SVG is a visual approximation, not necessarily designer-editable source artwork.

## Retain raster

Keep PNG or WebP for 3D rendering, fur, glass, smoke, soft shadows, photographic texture, dense gradients, translucent materials, or any result whose SVG is larger or visually worse than the raster.

## Publish gate

- XML passes sanitization.
- `viewBox` exists.
- No scripts, events, external references, entities, foreign objects, or embedded raster images exist.
- Path/shape count and file size remain below configured limits.
- SVG renders successfully in a clean renderer.
- Alpha-aware visual difference against the source remains below the configured threshold.
