# Contributing

Contributions are welcome, especially reproducible sheets or character packs that expose generation, identity, detection, background-removal, naming, vectorization, export, or QA failures.

## Good issues

Include:

- the source sheet or smallest shareable reproduction;
- the ordered intended labels and asset kind;
- the prompt, preset, density, and style constraints;
- `batch-plan.json`, `qa-report.json`, `cross-batch-qa.json`, debug image, and contact sheet when available;
- the expected result and observed failure.

Remove secrets, personal paths, private assets, and references you do not have permission to redistribute.

## Pull requests

1. Keep each change focused.
2. Add or update a fixture for behavior changes.
3. Run `./scripts/validate.sh`.
4. Explain whether the change affects planning, generation, identity, extraction, deterministic QA, visual QA, vectorization, export, or platform packaging.
5. Never weaken a publish gate merely to make a failing fixture pass.
6. Preserve compatibility with `generate-icon-batch` and legacy `icons` specifications unless the change is explicitly documented as breaking.

Keep every `SKILL.md` concise and focused. Put detailed schemas or variant guidance in `references/`, deterministic behavior in `scripts/`, and refresh `agents/openai.yaml` when user-facing behavior changes.
