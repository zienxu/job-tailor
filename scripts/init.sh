#!/usr/bin/env bash
# Run once inside a project created from the template. Usage: bash scripts/init.sh <project-name>
set -e
NAME="${1:?usage: bash scripts/init.sh <project-name>}"
cd "$(dirname "$0")/.."

sed -i.bak "s/PROJECT_NAME/$NAME/" CLAUDE.md && rm -f CLAUDE.md.bak
chmod +x .claude/hooks/*.sh scripts/*.sh
mkdir -p src tests private
[ -f .env ] || cp .env.example .env

git add -A
git commit -qm "init: $NAME from template" || true
echo "Initialised $NAME."
echo "Next: open this folder in VS Code, run the research prompt, then /grill-me (see README)."
