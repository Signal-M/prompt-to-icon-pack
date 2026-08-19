# Platform packaging

The canonical source uses the open Agent Skills folder format. Platform-specific manifests and installers are thin adapters around the same `skills/` directory.

## Codex

The repository is a Codex plugin through `.codex-plugin/plugin.json`. For a personal skill-only installation:

```bash
python3 scripts/install-platform.py codex
```

## Claude Code

The repository includes `.claude-plugin/plugin.json`. For a personal skills installation:

```bash
python3 scripts/install-platform.py claude-code
```

## Qwen Code

The repository includes `qwen-extension.json` with its `skills` directory. For a personal skills installation:

```bash
python3 scripts/install-platform.py qwen-code
```

## WorkBuddy

The adapter uses the `~/.workbuddy/skills` layout used by the tested local WorkBuddy setup:

```bash
python3 scripts/install-platform.py workbuddy
```

WorkBuddy products and versions may differ. Inspect the target installation's skill directory before using `--force`.

## QwenWork / 千问办公

Build a reviewable upload bundle:

```bash
python3 scripts/install-platform.py qwenwork
```

This creates `dist/qwenwork-skill-bundle.zip`. Availability of personal or public marketplace uploads depends on the current QwenWork account and organization policy; generating a bundle does not publish it.
