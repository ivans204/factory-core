# factory-core

A software factory for Claude Code: one orchestrator session (`/relay`) hands
each step to a specialist agent, every claim is backed by a receipt the harness
recorded and checked by a validator, an arbiter answers the agents' questions
from what the human already decided, and the human decides up front (the
charter) and only where it matters during the run. The brain — a folder of
markdown in git — is the single source of truth: no state lives only in a
conversation.

Three layers, and one test for where a sentence goes: *would it be true in a
different repo?*

| Layer | Where | Holds |
| --- | --- | --- |
| core | `~/.claude/factory-core/` (this folder) | the contract, 17 agents, `/relay`, hooks, templates |
| pack | `<brain>/lore/factory-<project>/` | `profile.md`, `roles/<agent>.md`, `knowledge/`, project-only `agents/` |
| job | `<brain>/job/<slug>/` + `relay/` | recipe, charter, plan, decisions, receipts, verdicts, evidence |

Precedence: the contract's *Never* list > the job's invariants > the human's
decisions > the pack > a core definition.

## Layout

    factory-core/
      README.md                 this file
      knowledge/contract.md     every agent reads it first
      agents/*.md               17 agents, symlinked into ~/.claude/agents
      skills/relay/             the orchestrator, symlinked into ~/.claude/skills/relay
      hooks/                    git-guardrails.sh, receipts.py, stop-gate.py
      settings-hooks.json       the hook registrations to merge into ~/.claude/settings.json
      templates/                profile, recipe, charter, state, decision, question, verdict,
                                close ritual, role addendum, agent skeleton

## After install.sh

1. Merge `settings-hooks.json` into `~/.claude/settings.json` (keep the hooks
   you already have). Restart Claude Code. `ls ~/.claude/agents` should list the
   17 agents; Claude Code no longer has an `/agents` screen to show them in.
2. Check the guardrails: ask Claude to run `git reset --hard` in a scratch repo;
   it must be blocked. A commit message that mentions it must pass.
3. Brain: if you have none, `mkdir -p ~/.brain/{job,lore} && git -C ~/.brain init`.
   Set `FACTORY_BRAIN` if it lives elsewhere. The minimum it needs: a folder per
   job with a recipe (`templates/recipe.md`), chunks for prose with a one-line
   index, the close ritual (`templates/close-ritual.md`), something that
   searches it (grep is enough), and git.

## Make a pack for a project

1. `mkdir -p <brain>/lore/factory-<project>/{roles,knowledge,agents}` and copy
   `templates/profile.md` to `profile.md` there. Fill every key from the repo:
   package scripts, CI config, contributing docs, PR template, design system.
   Delete optional blocks that do not apply (`tracker`, `app`, `ui`, `legacy`,
   `specs`): the roles that depend on them switch off.
2. `roles/<agent>.md` (from `templates/role-addendum.md`) only for an agent
   that needs a rule true in this repo and not in others. An empty pack beats
   an invented rule.
3. Models: if your tiers differ from what install.sh wrote, rerun it with
   `DECIDE=… BUILD=… READ=… CLERK=…`.
4. Project-only agents go in the pack's `agents/` and are symlinked into the
   repo's `.claude/agents/`.

Or let Claude do it: in the repo, say *"Read ~/.claude/factory-core/README.md
and make the factory pack for this repo. Fill what you can read, delete what
does not apply, ask me the rest, at most four questions at once, each with
your recommendation. Do not change any core file."*

## First job

In the repo, `/relay <what you want>`. Relay creates the job, has the scout
gather facts, then asks you for the charter: the goal, acceptance criteria and
how each is proven, what is out of scope, what you decide in advance, what you
always want to be asked, and how autonomous the run is (`guided`,
`supervised`, `autopilot`). From there it runs; "continue" after `/clear`
resumes from the brain.

## Changing the core

Agents never edit their definitions. Lessons come from friction (logged by the
scribe) and the retro, which proposes each change as core, pack, charter or
repo. A core change is a commit here with the reason in the message; a pack
change is a brain commit.

## Credits

Method text adapted from mattpocock/skills (MIT): writing-for-agents, grilling,
code-review, to-tickets, implement-spec, diagnosing-bugs, wayfinder,
git-guardrails-claude-code, pr, retro, wait-what.

Cookbook: https://claude.ai/artifact/HWw6sKXZuBHWSvSH64TZh9
