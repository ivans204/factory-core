# factory-core

Claude Code plugin skeleton (name `factory`, v0.1.0): the factory contract, git guardrails, receipt hooks, and templates.

**Nothing is installed or registered yet.** No agents or skills exist; no settings, symlinks, or hooks were touched.

## Layout
- `.claude-plugin/plugin.json` plugin manifest
- `knowledge/` contract.md (shared by every agent), README.txt
- `hooks/` hooks.json plus `factory-git-guardrails.sh` (PreToolUse Bash), `factory-receipts.py` (PostToolUse and PostToolUseFailure), `factory-stop-gate.py` (SubagentStop)
- `templates/` agent, skill, recipe, profile and job-file templates, roles roster
- `tests/` hook tests

## Tests
    bash tests/test_guardrails.sh
    python3 tests/test_receipts.py

Needs only bash, jq, python3.
