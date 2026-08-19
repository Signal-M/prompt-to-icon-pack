#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON:-python3}"
fixture_out="$(mktemp -d)"
trap 'rm -rf "$fixture_out"' EXIT

"$python_bin" -m compileall -q "$repo_root/skills" "$repo_root/scripts" "$repo_root/tests"
"$python_bin" -m unittest discover -s "$repo_root/tests" -p 'test_*.py' -v

"$python_bin" "$repo_root/skills/generate-icon-batch/scripts/prepare_icon_batch.py" \
  --spec "$repo_root/tests/fixtures/icon-spec.json" \
  --out "$fixture_out/legacy-plan"

"$python_bin" - "$fixture_out/legacy-plan/batch-plan.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    plan = json.load(handle)

assert plan["count"] == 9
assert len(plan["batches"]) == 1
assert plan["batches"][0]["count"] == 9
assert (plan["batches"][0]["rows"], plan["batches"][0]["columns"]) == (3, 3)
print("PASS: legacy 3x3 planning compatibility")
PY

"$python_bin" - "$repo_root" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
names = []
for skill in sorted((root / "skills").iterdir()):
    path = skill / "SKILL.md"
    if not path.exists():
        continue
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", content, re.S)
    assert match, f"invalid frontmatter: {path}"
    name = re.search(r"^name:\s*(.+)$", match.group(1), re.M).group(1).strip()
    description = re.search(r"^description:\s*(.+)$", match.group(1), re.M).group(1).strip()
    assert name == skill.name
    assert re.fullmatch(r"[a-z0-9-]+", name)
    assert description and len(description) <= 1024
    assert (skill / "agents/openai.yaml").exists(), f"missing agents/openai.yaml: {skill}"
    names.append(name)

for path in (root / ".codex-plugin/plugin.json", root / ".claude-plugin/plugin.json", root / "qwen-extension.json"):
    json.loads(path.read_text(encoding="utf-8"))
print(f"PASS: validated {len(names)} skill frontmatters and platform manifests")
PY
