# claude-kit

A GitHub template for starting any project or hackathon build with Claude Code.
Replace this README with your project's own once the build starts.

## What's inside
| Path | What it does |
| --- | --- |
| CLAUDE.md | Rules Claude reads every session |
| docs/spec.md | The plan: numbered, testable steps |
| docs/research.md | Research blocks pasted from claude.ai |
| DECISIONS.md | What you chose, what you rejected, why |
| .claude/agents/ | researcher, spec-writer, test-runner, code-reviewer, bug-hunter |
| .claude/hooks/guard-path.sh | Stops spec-writer and bug-hunter writing outside docs/ and tests/ |
| .claude/skills/grill-me | The interview skill, shared with teammates |
| .claude/settings.json | Blocks Claude from reading .env and private/ |
| scripts/setup-machine.sh | One-time setup for a new laptop or teammate |
| scripts/init.sh | Run once in each new project |

## Start a project
```bash
cd ~
gh repo create my-app --private --template YOUR_GITHUB_USERNAME/claude-kit --clone
cd my-app && bash scripts/init.sh my-app && code .
```

## Core prompts
Interview (Claude Code, Plan mode):
```text
/grill-me Read CLAUDE.md and docs/research.md first. Idea: <one paragraph>. When we finish, use the spec-writer agent to write docs/spec.md.
```
Build one step (Plan mode, then auto mode once the plan is approved):
```text
Implement step N of docs/spec.md. When done, use the test-runner agent and fix failures until it passes.
```
End of a feature:
```text
Use the code-reviewer agent on this feature, then the bug-hunter agent on <feature>. Fix blocking issues only.
```

Full playbook with examples: see the "Project kickstart" doc.
