---
name: generate-icon-batch
description: Generate a coherent batch of app, mini-program, game, or UI icons from a natural-language prompt by first creating one or more icon-sheet images, then detecting the icons without assuming a strict grid, removing only the exterior background, assigning user-facing names from an ordered specification, running closed-loop deterministic and visual QA, and delivering transparent PNG files plus manifests and a ZIP. Use when the user asks to create an icon set, icon library, icon pack, or many named icons from a prompt. Do not use when the user only wants to split an existing sheet; use split-icon-sheet instead.
---

# Generate Icon Batch

Turn one prompt into production-ready, named transparent PNG icons. Treat the ordered icon specification as the naming source of truth; never depend on generated captions or OCR.

## Required pipeline

1. Parse the request into:
   - a concise shared style contract;
   - an ordered list of unique `label` and `description` pairs;
   - any reference image roles and non-negotiable constraints.
2. Ask only when a missing decision would materially change the requested set. Otherwise make conservative assumptions and show the interpreted list before or alongside execution.
3. Save the specification as JSON and run `scripts/prepare_icon_batch.py`. Use 16 icons per sheet by default; use fewer for detailed 3D characters and never exceed 25.
4. Read [the generation contract](references/generation-contract.md), then call the built-in image-generation tool once for each planned sheet. This composite-sheet generation is intentional for this skill. Do not switch to an API/CLI path merely because the request says “batch.”
5. Copy every generated source sheet into the active workspace. Keep the exact generation prompt in the batch plan.
6. Run `$split-icon-sheet` in unlabeled mode with the batch's `labels.txt`:

```bash
PYTHON /absolute/path/to/split-icon-sheet/scripts/split_icon_sheet.py \
  --mode unlabeled \
  --image /absolute/path/to/generated-sheet.png \
  --labels /absolute/path/to/batch-01/labels.txt \
  --out /absolute/path/to/batch-01/split
```

7. Read [the QA rubric](references/qa-rubric.md). Compare the source sheet, detection debug image, contact sheet, ordered intent list, and transparent PNGs. When subagents are available, require an independent QA agent that receives only those artifacts and the rubric.
8. Write `semantic-qa.json` into each `batch-NN` directory. Use the schema in the rubric. Do not mark it `pass` unless every required check is true.
9. Classify failures before retrying:
   - wrong count, wrong concept, duplicate, order mismatch, or style drift: regenerate that whole sheet with one targeted correction;
   - bad crop, merged neighbors, lost detached detail, or alpha damage: rerun the splitter, add an override, or reduce the sheet size;
   - ambiguous intended name: correct the external specification; never ask OCR to recover a name that was already known.
10. Retry at most three times per batch. Do not package partial or uncertain results as complete.
11. Run `scripts/package_icon_batch.py` only after every splitter report and semantic QA gate passes. Deliver its ZIP, `icons/`, `icon-map.json`, `icons.ts`, combined contact sheet, and QA summary.

## Commands

Prepare a plan:

```bash
PYTHON scripts/prepare_icon_batch.py \
  --spec /absolute/path/icon-spec.json \
  --out /absolute/path/icon-batch-plan
```

Package passing batches:

```bash
PYTHON scripts/package_icon_batch.py \
  --plan /absolute/path/icon-batch-plan/batch-plan.json \
  --out /absolute/path/final-icons
```

Use a Python interpreter containing Pillow for packaging. In Codex desktop, load the bundled workspace dependencies instead of installing packages.

## Guardrails

- Never render captions, labels, numbers, or filenames inside a generated sheet.
- Keep ordered labels outside the image and bind them to detected icons in reading order.
- Require one isolated, compact icon cluster per planned item, generous blank separation, and no shared scene across cells.
- Use a uniform bright neutral exterior background. Preserve white details enclosed inside icons; remove only background connected to each local crop boundary.
- Do not infer semantic names from unlabeled pixels when the prompt already supplies or implies the names.
- Preserve the user's specificity. Do not add branded symbols, slogans, mascots, or narrative elements they did not request.
- Do not publish when the generated count differs from the plan, even if the sheet looks attractive.
