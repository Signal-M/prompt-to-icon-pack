# Contributing

Contributions are welcome, especially reproducible icon sheets that expose a real generation, detection, background-removal, naming, or QA failure.

## Good issues

Include:

- the source sheet or a minimal shareable reproduction;
- the intended reading-order labels;
- the command or Codex prompt used;
- `qa-report.json`, `detection-debug.png`, and `contact-sheet.png` when available;
- the expected result and the observed failure.

Remove API keys, tokens, private file paths, and assets you do not have permission to redistribute.

## Pull requests

1. Keep each change focused.
2. Add or update a fixture when fixing extraction behavior.
3. Run `./scripts/validate.sh`.
4. Explain whether the change affects generation, extraction, deterministic QA, semantic QA, or packaging.
5. Do not weaken a publish gate merely to make a failing fixture pass.

For skill instruction changes, keep `SKILL.md` concise and update `agents/openai.yaml` when the user-facing behavior changes.
