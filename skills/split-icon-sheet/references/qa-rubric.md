# Visual QA rubric

Evaluate the source and contact sheet pairwise. Return `pass`, `fail`, or `unsure` for every icon and for the complete sheet.

## Per-icon checks

1. **Completeness**: Preserve every meaningful part, including detached sparkles, dots, arrows, badges, shadows, and outline details. Reject any clipped edge.
2. **Isolation**: Include exactly one icon. Reject neighboring icon fragments, caption glyphs, card borders, watermarks, or unrelated marks.
3. **Background**: Require a transparent exterior with no white or gray rectangular panel and no obvious light halo.
4. **White preservation**: Keep white fills and highlights inside outlined icon regions opaque. Reject holes that were created by background removal.
5. **Embedded content**: Preserve text and symbols that belong inside the icon, including examples such as `NEW`, `R`, `COURT`, currency signs, and play symbols.
6. **Naming**: For captioned sheets, match the filename/label to the caption below the source icon and treat uncertain text as `unsure`. For unlabeled sheets, accept stable reading-order names such as `icon-001`; do not require guessed semantic names.
7. **Composition**: Center the complete icon with consistent transparent padding and no unintended distortion.

## Sheet checks

- Match the source icon count exactly.
- Preserve source reading order while allowing different item counts per row.
- Require unique filenames and stable IDs.
- Reject the full run if any icon is `fail` or `unsure`.

## Structured response

```json
{
  "status": "fail",
  "icons": [
    {
      "index": 12,
      "status": "fail",
      "failure_type": "clipped",
      "detail": "The bell decoration is missing on the right.",
      "retry_action": "expand_source_box_right"
    }
  ],
  "count_matches": true,
  "publish": false
}
```

Use these failure types: `clipped`, `missing_component`, `neighbor_contamination`, `background_remaining`, `white_removed`, `caption_remaining`, `embedded_text_removed`, `name_uncertain`, `off_center`, or `wrong_count`.

Map feedback to a targeted retry. Adjust only the affected label or `source_box` in `overrides.json`; do not loosen global thresholds for one local failure. Stop after three total iterations and leave unresolved outputs unpublished.
