# factory-core

Claude Code plugin skeleton (name `factory`, v0.1.0): the factory contract, git guardrails, receipt hooks, and templates.

**Nothing is installed or registered yet.** No agents or skills exist; no settings, symlinks, or hooks were touched.

## Layout
- `.claude-plugin/plugin.json` plugin manifest
- `knowledge/` contract.md (shared by every agent), README.txt
- `hooks/` hooks.json plus `factory-git-guardrails.py` (PreToolUse Bash), `factory-state-guard.py` (PreToolUse, protects factory state), `factory-bind.py` (CLI: bind a worktree to a job), `factory-receipts.py` (PostToolUse and PostToolUseFailure), `factory-stop-gate.py` (SubagentStop)
- `templates/` agent, skill, recipe, profile and job-file templates, roles roster
- `tests/` hook tests (test_guardrails.py, test_receipts.py)

## Tests
    python3 tests/test_guardrails.py
    python3 tests/test_receipts.py
    python3 tests/test_state.py

Needs only python3 (stdlib).

## Threat model
- The hooks guard against agent accidents and cheap tricks. They are not a shell parser and not a security boundary.
- The git guardrails are one linear pass (heredocs, `$(...)`, backticks, `eval`, `sh -c`, `find -exec`); computed command names are refused. Variable tricks beyond that, other interpreters and scripts are not inspected.
- The receipt HMAC is tamper-evidence, not secrecy: any process running as the user can read the key.
- The real boundary is the sandbox plus permission deny rules. Recommended (NOT applied by this repo):

```json
{
  "sandbox": {"enabled": true},
  "permissions": {"deny": [
    "Read(~/.config/factory/**)", "Edit(~/.config/factory/**)", "Write(~/.config/factory/**)",
    "Edit(~/.brain/job/*/relay/receipts/**)", "Write(~/.brain/job/*/relay/receipts/**)"
  ]}
}
```

## Proposed core change: job binding
Binding moved from `.factory-job` alone to an index (`~/.config/factory/bindings.json`, `{worktree root: slug}`) plus the `.factory-job` file, written together by `hooks/factory-bind.py <worktree> <slug>` (and `--unbind <worktree>`). The index is authoritative: the recorder records under the index slug, and the stop gate blocks with "job binding tampered" if the file is missing or different. A worktree with no index entry still falls back to a plain `.factory-job`.

## Known limits
- A computed command name (`$VAR`, `$(...)`) is blocked only when the same command also names a git subcommand or a bypass flag.
- Commands with no `git`, `HUSKY`, `LEFTHOOK`, `GIT_CONFIG` or shell word skip the deep scan, so they are never parse-checked.
- Commands that contain `eval` or `sh -c` many times over can take about 200 ms to check.
- The state guard is string based: globs, interpreters and indirect reads get through.
