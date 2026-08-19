#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
skills_target="${CODEX_SKILLS_DIR:-${HOME}/.agents/skills}"

mkdir -p "$skills_target"

for skill_name in generate-icon-batch split-icon-sheet; do
  target_dir="$skills_target/$skill_name"
  if [[ -e "$target_dir" ]]; then
    echo "Refusing to overwrite existing skill: $target_dir" >&2
    echo "Move or remove it after reviewing your local changes, then run this installer again." >&2
    exit 1
  fi
done

for skill_name in generate-icon-batch split-icon-sheet; do
  source_dir="$repo_root/skills/$skill_name"
  target_dir="$skills_target/$skill_name"
  cp -R "$source_dir" "$target_dir"
  echo "Installed $skill_name -> $target_dir"
done

echo "Done. Restart Codex or open a new task if the skills are not visible immediately."
