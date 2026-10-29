# ~/.brain/lore/factory-<project>/profile.md
# One YAML block. Every agent reads it. Delete an optional block to switch its roles off.
project: <name>

human:
  name: <who approves>
  language: <hr | en | ...>      # how the orchestrator talks; brain and agent files stay English
  style: short, product words, no file paths unless asked

brain:
  root: ~/.brain
  recipe: job/{slug}/{slug}.md
  relay: job/{slug}/relay/
  recall: <command that searches the brain>        # grep -ril works to start
  close_ritual: <file with your chunk-close steps>
  persist: [<reindex>, <re-embed>, git commit]
  after_close: <optional: board sync>

repo:
  path: <abs path>
  default_branch: main
  rules: [<AGENTS.md or CONTRIBUTING.md>, <knowledge index>]
  worktree_setup: <what a fresh worktree needs before any check>

checks:
  fast: <typecheck + tests related to {files}>     # Builder, every slice
  full: <everything CI runs>                       # final gate
  commit_gate: <hook that runs on commit and push> # never bypassed

limits: { in_flight: 3, builders: 2, review_rounds: 2 }

models:                          # tier -> alias written into agent frontmatter
  decide: <strongest>            # planner, challenger, escalation, risky review
  build: <strong>                # relay, builder, diagnostician, designer, correctness
  read: <mid>                    # scout, verifier, ds-guard, shipwright, spec + standards
  clerk: <small>                 # scribe
  decide_fallback: <build tier at its highest effort>

risky_paths: [<where a bug costs money or access>]
shared_files: [<files only one lane may touch>]

ci:
  read_with: <skill or CLI that reads pipeline logs>
  green_means: <every check on the head commit passes>

pr:
  rules: [<docs every PR follows>]
  title: <convention>
  open_as: draft
  testing_proof: <what counts as proof, or a doc that says>
  never: [<what only the human does>]

policy:                          # standing decisions for every job on this project
  autonomy_default: guided       # guided | supervised | autopilot; a job's charter may change it
  always_ask: [<decisions only the human makes here>]
  arbiter_may_decide: [<kinds of question the Arbiter settles alone>]
  confidence_floor: medium       # below this the Arbiter escalates

evidence:
  receipts: job/{slug}/relay/receipts/
  rerun_seconds: 120             # the Validator reruns anything faster than this
  research_sample: 3             # claims checked per research report

# ---- optional blocks ----
tracker:
  find_my_tasks: <how to list the human's open tasks>

app:                             # off -> no Verifier, no checkpoint URL
  dev: <command that starts the app on {port}>
  port_range: <from-to>
  data: <real-api | mock | seed>
  test_account: <which account the agents' browser uses>

ui:                              # off -> no Designer, no DS Guard
  catalog: <components to build with>
  tokens: <design tokens>
  rules: <UI rules lint does not catch>
  design_skill: <skill that draws options as a page>

legacy:                          # off -> no "port X" entry
  name: <old system>
  repos: [<paths>]
  sources: knowledge/port/sources.md      # inside this pack
  doc_template: knowledge/port/doc-template.md
  doc_home: <where port docs live in the repo>

specs:
  kind: <spec language>
  build_skill: <skill that turns a spec into tested code>
