---
name: split-icon-sheet
description: Split AI-generated icon sheets into individually named transparent PNG files without assuming a uniform grid. Use for PNG, JPEG, or WebP sheets containing multiple separated icons, with or without captions, especially when rows have different item counts, spacing is irregular, internal white areas or embedded text must be preserved, captions may need OCR naming, and outputs require closed-loop visual QA before ZIP delivery. For unlabeled sheets, detect foreground objects and assign stable numbered names; do not invent semantic names. Do not use for ordinary single-photo background removal.
---

# Split Icon Sheet

Extract labeled or unlabeled icons from irregular AI-generated sheets. Preserve enclosed white fills and embedded icon text such as `NEW`, `R`, or `COURT`; remove only the exterior background, card frame, and any caption below each icon.

## Run the workflow

1. Inspect the source image before processing. Count obvious caption rows, note embedded text, detached decorations, and any icons near neighbors.
2. Locate a Python interpreter containing Pillow and NumPy. In Codex desktop, call `load_workspace_dependencies` and use the returned Python executable. Do not install packages when the bundled runtime is available.
3. Run the splitter from this skill directory:

```bash
PYTHON scripts/split_icon_sheet.py \
  --image /absolute/path/icon-sheet.jpg \
  --out /absolute/path/output
```

Use `--mode unlabeled` when the sheet has no captions. This skips OCR, detects separated foreground objects directly, and names them `icon-001`, `icon-002`, and so on in reading order:

```bash
PYTHON scripts/split_icon_sheet.py \
  --mode unlabeled \
  --image /absolute/path/icon-sheet.png \
  --out /absolute/path/output
```

Leave the default `--mode auto` when uncertain. It tries caption detection first and falls back to unlabeled object detection only when no caption rows exist.

The default alpha route is the dependency-free `boundary` method. For white hats, shirts, shoes, or other white-on-white character details, install the optional dependency and explicitly evaluate semantic and conservative-union candidates:

```bash
PYTHON scripts/split_icon_sheet.py \
  --mode unlabeled \
  --segmentation-backend ensemble \
  --rembg-model birefnet-general-lite \
  --image /absolute/path/icon-sheet.png \
  --out /absolute/path/output
```

`--segmentation-backend sam` exposes the locally installed rembg SAM backend for reviewed cases. Model weights may download on first use. Do not treat any model as an automatic publish authority; the source comparison remains mandatory.

The script uses macOS Vision for local Chinese/English OCR. If Vision is blocked by the sandbox, rerun the same command with user approval. It does not upload the image.

4. Read `qa-report.json`. For a captioned sheet, if it reports uncertain OCR names, inspect the numbered `detection-debug.png` against the source, create a UTF-8 labels file with one corrected caption per icon in numbered reading order, and rerun:

```bash
PYTHON scripts/split_icon_sheet.py \
  --image /absolute/path/icon-sheet.jpg \
  --labels /absolute/path/labels.txt \
  --out /absolute/path/output
```

5. Compare every row of `qa-comparison.png`: source crop, checkerboard output, and output on navy/magenta. The colored panels are mandatory for detecting white parts that became transparent. Use [the QA rubric](references/qa-rubric.md). When subagents are available, launch a fresh independent QA subagent with only the source image, QA comparison, detection debug image, and rubric; do not reveal expected failures. A deterministic `pass` is not visual approval.
6. If QA finds a localized crop, naming, or alpha error, write `overrides.json` and rerun with `--overrides`. Use `source_box` for crop errors. For a confirmed white-on-white semantic region, provide a tightly traced source-coordinate `protected_polygons`; never use a rectangular opaque patch:

```json
{
  "icons": {
    "12": {"label": "消息通知"},
    "37": {"source_box": [650, 320, 744, 397]},
    "4": {
      "protected_polygons": [[[118, 183], [126, 132], [170, 98], [248, 96], [294, 132], [301, 181]]]
    }
  }
}
```

7. Write a structured visual QA result with explicit `source_fidelity` and `white_preservation` checks. Repeat extraction and QA for at most three iterations. Deliver `icons.zip` only when deterministic QA and visual QA both pass. If an icon remains uncertain, leave the run in `needs_review`; never describe it as complete.
8. For repeated production use, follow [the closed-loop improvement policy](references/self-improvement.md). Record failures and promote parameter or code changes only after regression tests pass; do not let one QA verdict rewrite global thresholds live.

## Understand the outputs

- `icons/`: transparent 256×256 PNG files with stable numbered, caption-derived names.
- `icon-map.json`: ordered icon IDs, labels, filenames, rows, and columns.
- `icons.ts`: mini-program-friendly asset constants and label mapping.
- `qa-report.json`: per-icon extraction attempts, clipping checks, component counts, preserved white-pixel counts, and publish status.
- `detection-debug.png`: source image with numbered icon regions and OCR caption boxes.
- `contact-sheet.png`: checkerboard preview for visual comparison.
- `qa-comparison.png`: source/output comparison on checkerboard and high-contrast backgrounds; use this for white-preservation QA.
- `icons.zip`: icons plus runtime mappings and QA report; debug previews stay outside the archive.

## Guardrails

- Detect each caption row independently. Never force a single global row/column grid.
- For an unlabeled sheet, identify separated foreground objects and cluster their centers into reading-order rows. Use numbered names unless the user supplies an ordered labels file.
- Remove background only when bright neutral pixels are connected to a local crop boundary. Keep enclosed white pixels opaque.
- Treat white-on-white foreground as semantically ambiguous. Require source comparison, and use tightly scoped protected polygons or a semantic matting fallback after visual QA flags it.
- Treat detected `white_removed` risk as a hard deterministic failure. A semantic candidate can recover it, but cannot waive visual source-fidelity QA.
- Exclude captions geometrically below the icon region. Never globally erase every OCR text box because embedded icon text must survive.
- Keep detached components unless they are tiny noise or a frame touching at least three crop sides.
- Treat low-confidence OCR as a review condition, not a successful automatic name.
- Prefer a coverage failure over publishing a damaged icon. Never use `--allow-failures` for a user-facing deliverable.
