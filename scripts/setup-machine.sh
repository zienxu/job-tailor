#!/usr/bin/env bash
# One-time setup for a fresh or borrowed machine, or a teammate's laptop.
# Safe to re-run. Usage: bash scripts/setup-machine.sh
set -u
ok()   { printf '  ok   %s\n' "$1"; }
miss() { printf '  MISSING  %s -> %s\n' "$1" "$2"; MISSING=1; }
MISSING=0

echo "Checking tools..."
command -v git     >/dev/null && ok git     || miss git     "xcode-select --install"
command -v python3 >/dev/null && ok python3 || miss python3 "xcode-select --install (or python.org)"
command -v node    >/dev/null && ok node    || miss node    "https://nodejs.org (LTS)"
command -v gh      >/dev/null && ok gh      || miss gh      "brew install gh, then gh auth login"
command -v claude  >/dev/null && ok claude  || miss claude  "install Claude Code: https://code.claude.com/docs"

if [ "$MISSING" = 1 ]; then
  echo "Install the missing tools above, then re-run this script."
  exit 1
fi

echo "Installing user-scope plugins (skips any already installed)..."
claude plugin marketplace add anthropics/claude-plugins-official 2>/dev/null || true
claude plugin marketplace add forrestchang/andrej-karpathy-skills 2>/dev/null || true
claude plugin marketplace add DietrichGebert/ponytail 2>/dev/null || true
claude plugin install andrej-karpathy-skills@karpathy-skills --scope user || true
claude plugin install ponytail@ponytail --scope user || true
claude plugin install claude-code-setup@claude-plugins-official --scope user || true

echo
echo "Done. Next:"
echo "  1. Restart Claude Code."
echo "  2. Run /plugin and check the three plugins are listed."
echo "  3. Press Shift+Tab in Claude Code and check that 'auto' is one of the modes."
echo "grill-me and the five agents ship inside each project, so nothing else is needed."
