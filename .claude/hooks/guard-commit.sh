#!/usr/bin/env bash
# Blocks `git commit` while .env* or private/ files are staged, modified, or untracked.
# Root-cause guard: catches `git add -A && git commit`, `git commit -a`, chained commands,
# etc. by checking actual working-tree state at commit time, not the command text.
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HOOK_INPUT="$(cat)"   # read Claude's JSON before python takes over stdin
export HOOK_INPUT
python3 - "$ROOT" <<'PY'
import json, os, re, subprocess, sys

root = sys.argv[1]
try:
    data = json.loads(os.environ.get("HOOK_INPUT", "") or "{}")
except Exception:
    print("guard-commit: could not read hook input", file=sys.stderr); sys.exit(2)

command = (data.get("tool_input") or {}).get("command", "")
if not re.search(r'\bgit\s+commit\b', command):
    sys.exit(0)

try:
    out = subprocess.run(
        ["git", "-C", root, "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
except Exception as e:
    print(f"guard-commit: could not read git status ({e})", file=sys.stderr)
    sys.exit(2)

secret_re = re.compile(r'^(?:\.env(?:\..*)?|private/.*)$')
hits = []
for line in out.splitlines():
    if not line.strip():
        continue
    path = line[3:]
    for p in (path.split(' -> ') if ' -> ' in path else [path]):
        p = p.strip().strip('"')
        if secret_re.match(p):
            hits.append(p)

if hits:
    print(f"Blocked: git commit while secret/private files are staged or dirty: {', '.join(hits)}", file=sys.stderr)
    print("Unstage them or add to .gitignore before committing.", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
