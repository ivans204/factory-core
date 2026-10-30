## What and why
<!-- The change and the reason for it. Link the issue or job if there is one. -->

## Tests
<!-- Tick what you ran. Note anything skipped and why. -->
- [ ] `python3 tests/test_guardrails.py`
- [ ] `python3 tests/test_receipts.py`
- [ ] `python3 tests/test_state.py`
- [ ] `python3 tests/test_agents.py`
- [ ] Hooks changed: `tests/smoke.sh` run outside the sandbox (paste the result)

## Checklist
- [ ] Guardrail changes test both what is blocked and what must still pass
- [ ] New hook limits are in README "Known limits"
- [ ] `HANDOFF.md` updated if this makes a decision or finishes a phase
- [ ] No keys, receipts or `.factory-job` files
