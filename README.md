# factory-core

Claude Code plugin skeleton (name `factory`, v0.1.0): the factory contract, git guardrails, receipt hooks, and templates.

**Nothing is installed or registered yet.** No agents or skills exist; no settings, symlinks, or hooks were touched.

## Layout
- `.claude-plugin/plugin.json` plugin manifest
- `knowledge/` contract.md (shared by every agent), README.txt
- `hooks/` hooks.json plus `factory-git-guardrails.py` (PreToolUse Bash), `factory-receipts.py` (PostToolUse and PostToolUseFailure), `factory-stop-gate.py` (SubagentStop)
- `templates/` agent, skill, recipe, profile and job-file templates, roles roster
- `tests/` hook tests (test_guardrails.py, test_receipts.py)

## Tests
    python3 tests/test_guardrails.py
    python3 tests/test_receipts.py

Needs only python3 (stdlib).

## Threat model
- Guards against agent mistakes and naive prompt injection; it is not a sandbox.
- Git commands are parsed (shlex, substitutions, eval, `sh -c`), but variable expansion (`git${IFS}reset`), other interpreters (`python -c`) and scripts are not inspected.
- Receipts carry an HMAC (key: `~/.config/factory/receipt.key`, mode 0600); the stop gate fails closed on a bad or missing mac.
- The key is readable by any process running as the user, so the HMAC only holds if permissions block the agent from it.
- Pair with these rules in settings (NOT applied by this repo):

```json
{"permissions": {"deny": [
  "Read(~/.config/factory/**)", "Edit(~/.config/factory/**)", "Write(~/.config/factory/**)",
  "Edit(~/.brain/job/*/relay/receipts/**)", "Write(~/.brain/job/*/relay/receipts/**)"
]}}
```
