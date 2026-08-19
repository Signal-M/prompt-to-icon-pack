# Icon-sheet generation contract

Use this contract to convert each planned batch into the final image-generation prompt.

## Prompt structure

```text
Use case: stylized-concept
Asset type: production UI icon sheet for later automatic splitting
Primary request: create exactly N distinct icons in the exact reading order listed below
Shared style: <the user's style contract>
Scene/backdrop: one perfectly uniform bright neutral background across the whole canvas
Composition: R rows by C columns; one compact icon cluster per position; read left-to-right, top-to-bottom; generous equal blank space; no overlap; no shared scene
Ordered icon intents:
1. <label>: <visual description>
2. ...
The labels above are semantic planning names only. Do not render them or any other text in the image.
Constraints: exact count N; every intent appears once; cohesive scale, perspective, stroke weight, lighting, palette, and detail level; each icon fully visible with ample padding; preserve intentional white details; no card frames unless requested
Avoid: captions, labels, letters, numbers, watermarks, logos not requested, duplicate concepts, extra icons, cropped subjects, separators, decorative objects floating between icons, shadows or texture in the exterior background
```

## Reliability rules

- Default to at most 16 icons per sheet. Use 9–12 for detailed characters or 3D scenes. Permit 17–25 only for visually simple sets.
- Prefer a square or near-square layout. The planning script supplies the row and column count.
- Describe each intended icon concretely. A label alone may be ambiguous; add the visible subject and the differentiating action or prop.
- Keep each item as one compact visual cluster. Detached sparkles or badges must remain close enough to belong unambiguously to the icon.
- Use a plain white or near-white exterior background because the splitter removes only bright neutral pixels connected to a local crop edge. Do not ask for transparent generation here.
- If a reference image is supplied, identify it as a style reference, character reference, or edit target. Preserve only the attributes the user requested.
- On retries, keep the original contract and add one short correction block naming the failed positions. Do not rewrite unrelated parts of the prompt.
