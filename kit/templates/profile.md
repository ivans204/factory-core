# Factory profile — <project>

Every factory agent reads this. Keys are referred to as `block.key`. Delete an
optional block to switch off the roles that depend on it.

```yaml
project: <name>

human:
  name: <who approves>
  language: <en | hr | ...>      # how the orchestrator talks; brain and agent files stay English
  style: short, product words, no file paths unless asked

brain:
  recall: <command that searches the brain for {query}>   # grep -ril works to start
  close_ritual: <file with your chunk-close steps>          # templates/close-ritual.md if you have none
  persist: [<reindex>, <re-embed>, git -C <brain> commit -am "<msg>"]
  after_close: <optional command, e.g. a board sync>

repo:
  path: <abs path>
  default_branch: main
  rules: [<AGENTS.md or CONTRIBUTING.md>, <knowledge index>]
  worktree_setup: <what a fresh worktree needs before any check, e.g. npm ci>

checks:
  fast: <typecheck + only the test files that cover {files}>  # builder, every slice; never the whole suite
  lint: <the repo's full lint>                      # once per job, at the lint pass; never per slice
  full: <what CI runs that fast and lint did not, short of the whole suite CI runs anyway>  # final gate
  commit_gate: <hook that runs on commit and push>  # never bypassed

limits: { in_flight: 3, builders: 2, review_rounds: 2, test_rounds: 2 }

tests:                           # test-auditor
  run_one: <run one test file or one title, per layer>
  layers: [<unit>, <integration/acceptance>, <e2e>]
  mutate_in: own-worktree        # or slice-worktree-exclusive: relay holds every other agent off it
  mutants_per_hunk: 2
  budget_mutants: 12
  flake_runs: 3
  env_variants: []               # e.g. TZ=America/New_York, random order
  mock_truth: <where the real contract is, to compare mocks with: an OpenAPI file, the API repo>
  date_caveat: <anything that keeps a date bug from failing a test here>

models:                          # tier -> alias; install.sh writes these into agent frontmatter
  decide: <strongest>            # arbiter, planner, challenger, retro, escalation
  build: <strong>                # builder, diagnostician, designer, correctness, test-auditor
  read: <mid>                    # scout, verifier, ds-guard, shipwright, validator, spec + standards
  clerk: <small>                 # scribe
  decide_fallback: <build tier at its highest effort>

risky_paths: [<where a bug costs money or access>]
shared_files: [<files only one lane may touch>]

ci:
  read_with: <skill or CLI that reads pipeline logs>
  green_means: <e.g. every check on the head commit passes>

pr:
  rules: [<docs every PR follows>]
  template: <path to the PR template>
  title: <convention>
  branch: <convention, e.g. type/slug>
  open_as: draft
  testing_proof: <what counts as proof, or the doc that says>
  evidence_hosting: <where PR screenshots live; never a public host unless allowed>
  never: [<what only the human does: merge label, resolve threads, mark ready>]

policy:                          # standing decisions for every job on this project
  autonomy_default: guided       # guided | supervised | autopilot
  always_ask: [<decisions only the human makes here>]
  arbiter_may_decide: [<kinds of question the arbiter settles alone>]
  confidence_floor: medium       # below this the arbiter escalates

evidence:
  rerun_seconds: 120             # the validator reruns anything faster than this
  research_sample: 3             # claims checked per research report

# ---- optional blocks ----
tracker:
  find_my_tasks: <how to list the human's open tasks>

app:                             # off -> no verifier, no checkpoint URL
  dev: <command that starts the app on {port}>
  port_range: <from-to>
  data: <real-api | mock | seed>
  test_account: <which account the agents' browser uses>

ui:                              # off -> no designer, no ds-guard
  catalog: <components to build with>
  tokens: <design tokens>
  rules: <UI rules lint does not catch>
  edit_hook: <hook that checks UI edits, if any>
  design_skill: <skill that draws options as a page, if any>

legacy:                          # off -> no "port X" entry
  name: <old system>
  repos: [<paths>]
  sources: knowledge/port-sources.md       # inside this pack
  doc_template: knowledge/port-doc.md      # inside this pack
  doc_home: <where port docs live in the repo>

specs:
  kind: <spec language>
  build_skill: <skill that turns a spec into tested code>
```
