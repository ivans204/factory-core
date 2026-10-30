# Contributing to factory-core

factory-core is a Claude Code plugin. Read `README.md` for the layout and threat model, and `HANDOFF.md` for current state, decisions and traps.

## Setup
Needs only python3 (stdlib). Don't add dependencies.

The plugin is installed from the local marketplace, so Claude Code loads hooks straight from the repo: edits are live as soon as you save. Plugin agents load at session start, so start a fresh session after changing `agents/`.

## Tests
    python3 tests/test_guardrails.py
    python3 tests/test_receipts.py
    python3 tests/test_state.py
    python3 tests/test_agents.py

All four must pass before a PR.

After any hook change, also run the live smoke test yourself, outside any Claude sandbox:

    ! bash ~/orca/factory-core/tests/smoke.sh

It can't run from inside a sandboxed Claude session.

## Rules
- Hooks guard against agent mistakes and cheap tricks. They are not a shell parser and not a security boundary; the sandbox and permission deny rules are. Don't propose a complete shell parser: two attempts failed review.
- A guardrail change needs a test for what it blocks and for the normal commands it must still allow. False positives on everyday commits count as bugs.
- New limits of a hook go in README "Known limits".
- Never put `SKILL.md` in `agents/`. README files there and in `knowledge/` are `.txt`.
- Never commit keys, receipts or `.factory-job` files.
- If your change makes a decision or finishes a phase, update `HANDOFF.md` in the same PR.

## Commits and PRs
- Commit subjects start with the area: `factory-core: R3 Scribe and Shipwright`, `HANDOFF: resume point`.
- Branch from `main`; don't push to `main` directly. Keep a PR to one change and fill in the template.
- Don't use `--no-verify` or `reset --hard`; the guardrails block them.

By contributing, you agree your work is licensed under the MIT License (`LICENSE`).
