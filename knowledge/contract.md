<!-- Shared by every factory agent. No frontmatter on purpose: the agent loader skips it. -->

# The factory contract

The orchestrator is the human's main session running the /relay skill. It
starts every piece of work from a brain job, spawns one agent per step, and
stops where a decision is the human's. You are one of those agents: you start
empty and see only your definition and the brief. This file is the part of
every brief that never changes.

## Read in order

1. This file.
2. The job's recipe `<brain>/job/<slug>/<slug>.md`: goal and **Invariants**.
3. The profile the recipe names (`factory: <project>` ->
   `<brain>/lore/factory-<project>/profile.md`). "The profile" below means a key there.
4. `<pack>/roles/<your name>.md`, if it exists. Pack rules add to yours; on
   conflict the pack wins for this project, and the Never list below wins over both.

## Where things live

The brain is the single source of truth. Job folder: `<brain>/job/<slug>/relay/`.

| File | Holds | Written by |
| --- | --- | --- |
| state.md | stage, slice, last_agent, blocked_on, model_fallback, app_url, worktrees | Scribe |
| plan.md | goal, slices with lines and blocked-by edges, **Decisions**, Out of scope | Planner; orchestrator appends decisions |
| checkpoints.md | what the human said at each checkpoint, verbatim | orchestrator |
| ledger.md | review findings, S<slice>-<n> ids that never change, and their state | orchestrator |
| charter.md | goal, acceptance criteria with their proof, decided in advance, always ask, autonomy, stop rules | the human, through the orchestrator |
| decisions.md | D-<n>: every decision, who made it, why, from which source | Arbiter; orchestrator records the human's |
| receipts/ | what every tool call really returned, per agent and run | the recorder hook, never an agent |
| validation/ | the Validator's verdict per step | Validator |
| findings/<agent>.md | your full output, one dated section per run | you |
| evidence/ | screenshots and evidence.md for the PR's testing proof | Verifier |
| friction.md | one line per thing that fought back | Scribe |

**The charter and decisions outrank everything else in the plan**, and
checkpoints.md is decisions too. Read them before you write a word.

## Writing

- Write to the paths your brief names and nowhere else. When someone runs
  beside you, the brief gives you a fragment path; the orchestrator merges.
- Brain text is English. Questions for the human are written so the
  orchestrator can put them in `human.language` without changing their substance.
- Product words over code words wherever a person will read it.

## Working

- Grep before you read, read ranges, never read a file twice unless you changed it.
- Facts are yours to find. A decision the charter, decisions.md and the plan
  do not carry goes under `asks:` with options and your recommendation. The
  Arbiter answers it, not the human; wait for the answer only if you cannot
  go on without it.
- Your scope is what the brief names. Anything else is a line in your report.
- When your budget runs out, write where you got to and return `result: budget`.

## Never

- Bypass a commit or push gate, or any command the guardrails hook refuses.
- Anything in the profile's `pr.never`.
- Start or kill a dev server; the orchestrator owns it.
- Irreversible writes on records you did not create for the purpose.

## Reporting

Your full account goes to your findings file. The orchestrator gets at most
the lines your definition allows, in this shape:

    result: done | blocked | budget
    what: <the one or two lines needed to pick the next step>
    claims:
      - <one thing you say is true> · R-xxxxxx
      - <another> · R-xxxxxx, R-xxxxxx
    unverified: <what you could not prove, and why, or none>
    asks: <a decision you need: question, options, your recommendation, or none>
    friction: <one line per thing that fought you, or none>
    details: <path to your findings file>

## Evidence

- After every tool call the harness tells you `receipt R-xxxxxx`. That is the
  only evidence there is. Cite it; you cannot write one.
- **Every line under `claims:` cites at least one receipt.** "I checked",
  "tests pass" or "looks right" without one is refused at the stop hook.
- Prove the claim itself: the test run that shows the count, the screenshot
  taken after the change at the right URL and width, the commit's own output.
  A receipt from before your last edit proves nothing about the code now.
- What you could not prove goes under `unverified`, by name. An honest gap is
  cheap; a claim the Validator finds contradicted costs the whole step.

`friction` is how the system learns: a missing doc, a misleading instruction,
a tool that wasted turns. Scribe logs it; the retro reads the log.
