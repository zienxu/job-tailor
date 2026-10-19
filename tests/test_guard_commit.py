#!/usr/bin/env python3
"""Self-check for .claude/hooks/guard-commit.sh. Run: python3 tests/test_guard_commit.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks", "guard-commit.sh")


def run_hook(repo, command):
    payload = json.dumps({"tool_input": {"command": command}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": repo}
    result = subprocess.run([HOOK], input=payload, text=True, capture_output=True, env=env)
    return result.returncode


def main():
    repo = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)

        with open(os.path.join(repo, "a.txt"), "w") as f:
            f.write("hi")
        subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
        rc = run_hook(repo, "git commit -m x")
        assert rc == 0, f"expected allow on clean tree, got {rc}"

        os.makedirs(os.path.join(repo, "private"), exist_ok=True)
        with open(os.path.join(repo, "private", "secret.txt"), "w") as f:
            f.write("ssn")
        rc = run_hook(repo, "git add -A && git commit -m x")
        assert rc == 2, f"expected block with private/ dirty, got {rc}"

        with open(os.path.join(repo, ".env"), "w") as f:
            f.write("KEY=1")
        rc = run_hook(repo, "git commit -am x")
        assert rc == 2, f"expected block with .env dirty, got {rc}"

        rc = run_hook(repo, "git status")
        assert rc == 0, f"expected non-commit command to pass through, got {rc}"

        print("ok")
    finally:
        shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    main()
