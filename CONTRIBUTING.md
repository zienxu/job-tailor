# Working as a team

For teammates with or without Claude Code.

- **One owner per area.** Split by folder (e.g. frontend/, backend/), never by file, so nobody edits the same lines.
- **One branch per person:** `git switch -c <name>/<feature>`. Merge to main only when tests pass.
- **docs/spec.md is the plan for everyone.** Claim a step by writing your name next to it before starting.
- **Pull before every session:** `git pull --rebase origin main`.
- **Never commit** .env or anything in private/. Share secrets in person or a password manager, not chat or git.

## With Claude Code
- Run `bash scripts/setup-machine.sh` once on your laptop.
- Open the repo folder in VS Code; CLAUDE.md, the agents and grill-me load automatically.
- Accept the workspace-trust prompt, or the agents' safety hooks will not run.

## Without Claude Code
- Read CLAUDE.md for the rules and docs/spec.md for your step. That's all the context you need.
