#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON:-python3}"
fixture_out="$(mktemp -d)"
trap 'rm -rf "$fixture_out"' EXIT

"$python_bin" -m compileall -q "$repo_root/skills"
"$python_bin" "$repo_root/skills/generate-icon-batch/scripts/prepare_icon_batch.py" \
  --spec "$repo_root/tests/fixtures/icon-spec.json" \
  --out "$fixture_out/plan"
"$python_bin" - "$fixture_out/plan/batch-plan.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    plan = json.load(handle)

assert plan["count"] == 9
assert len(plan["batches"]) == 1
assert plan["batches"][0]["count"] == 9
assert (plan["batches"][0]["rows"], plan["batches"][0]["columns"]) == (3, 3)
print("PASS: Python compilation and 3x3 planning smoke test")
PY
