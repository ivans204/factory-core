# factory-core

The source of the software factory core (`/relay`, 17 agents, contract, hooks,
templates) and of the cookbook page that ships it:
https://claude.ai/artifact/HWw6sKXZuBHWSvSH64TZh9

| Path | What |
| --- | --- |
| `kit/` | the core, exactly as it installs to `~/.claude/factory-core/`. Agents carry `model: {{tier}}`. **Edit here.** |
| `install.sh` | built from `kit/`. Writes the core to `~/.claude/factory-core`, links agents into `~/.claude/agents/` and `/relay` into `~/.claude/skills/relay`. |
| `cookbook/kuharica.html` | the page. Prose is edited by hand; every `data-path` block (the Kit) is generated. |
| `scripts/build.py` | rebuilds `install.sh` and the page's Kit from `kit/`. `--check` fails when either is stale. |
| `scripts/fold.py` | brings edits made in `~/.claude/factory-core` (retro, hand edit) back into `kit/`. |
| `tests/test_hooks.sh` | guardrails and stop gate on a few must-block / must-pass inputs. |

## Change relay (or any core file)

    $EDITOR kit/skills/relay/SKILL.md
    python3 scripts/build.py      # install.sh + page Kit
    bash install.sh               # updates ~/.claude/factory-core in place; links already point there
    git commit -am "relay: <the lesson>" && git push

`install.sh` remembers the model tiers from the last run in
`~/.claude/factory-core/.factory-core`, so a rerun needs no variables. First
install on a machine: `DECIDE=fable bash install.sh`.

## Everywhere else

- **Another machine of mine:** `git clone` (or `git pull`), then `bash install.sh`.
- **Someone without this repo:** the cookbook page. After a change, ask Claude to
  publish `cookbook/kuharica.html` to the artifact URL above; its `install.sh`
  is the one built here, and rerunning it updates their core in place.

## A change made in the installed core

`install.sh` refuses to overwrite `~/.claude/factory-core` when it has commits
or edits since the last install. Fold them back first:

    python3 scripts/fold.py && git diff kit/
    git commit -am "<what and why>" && python3 scripts/build.py
    FORCE=1 bash install.sh

## History

Tag `r1-plugin` is the earlier `factory` plugin (Python guardrails with HMAC
receipts, job binding index, scribe and shipwright only), built from the first
version of the cookbook. The kit replaced it on 2026-10-30.
