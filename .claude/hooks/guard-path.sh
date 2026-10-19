#!/usr/bin/env bash
# Blocks Write/Edit outside one allowed folder. Usage: guard-path.sh <folder>
# Used by the spec-writer (docs) and bug-hunter (tests) agents.
ALLOWED="${1:?folder required}"
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HOOK_INPUT="$(cat)"   # read Claude's JSON before python takes over stdin
export HOOK_INPUT
python3 - "$ALLOWED" "$ROOT" <<'PY'
import json, os, sys
allowed, root = sys.argv[1], os.path.realpath(sys.argv[2])
try:
    data = json.loads(os.environ.get("HOOK_INPUT", ""))
except Exception:
    print("guard-path: could not read hook input", file=sys.stderr); sys.exit(2)
path = (data.get("tool_input") or {}).get("file_path", "")
if not path:
    print("guard-path: no file_path in tool input", file=sys.stderr); sys.exit(2)
full = os.path.realpath(path if os.path.isabs(path) else os.path.join(root, path))
target = os.path.join(root, allowed)
if full == target or full.startswith(target + os.sep):
    sys.exit(0)
print(f"Blocked: this agent may only write inside {allowed}/ (tried {path})", file=sys.stderr)
sys.exit(2)
PY
