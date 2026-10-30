#!/bin/bash
# Must-block and must-pass inputs for kit/hooks. Run from anywhere: bash tests/test_hooks.sh
set -uo pipefail
HOOKS="$(cd "$(dirname "$0")/../kit/hooks" && pwd)"
fail=0

guard() { jq -n --arg c "$1" '{tool_input: {command: $c}}' | bash "$HOOKS/git-guardrails.sh" 2>/dev/null; }
blocks() { guard "$1"; [ $? -eq 2 ] && echo "ok   blocks: $1" || { echo "FAIL blocks: $1"; fail=1; }; }
passes() { guard "$1"; [ $? -eq 0 ] && echo "ok   passes: $1" || { echo "FAIL passes: $1"; fail=1; }; }

blocks 'git reset --hard HEAD~1'
blocks 'git checkout -- src/a.ts'
blocks 'git restore src/a.ts'
blocks 'git clean -fd'
blocks 'git branch -D feature'
blocks 'git stash drop'
blocks 'git commit --no-verify -m x'
blocks 'HUSKY=0 git commit -m x'
blocks 'git push --force origin feature'
passes 'git commit -m "never run git reset --hard"'
passes 'git restore --staged src/a.ts'
passes 'git push --force-with-lease origin feature'
passes 'git checkout -b feature'
passes "git commit -F - <<'EOF'
mention git reset --hard in the body
EOF"

# Stop gate: a claim must cite a receipt the agent recorded in this run.
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/wt" "$tmp/brain/job/demo/relay/receipts"
echo demo > "$tmp/wt/.factory-job"
echo '{"id": "R-abc123"}' > "$tmp/brain/job/demo/relay/receipts/builder-a1.jsonl"
gate() { jq -n --arg m "$1" --arg cwd "$tmp/wt" \
  '{last_assistant_message: $m, cwd: $cwd, agent_type: "builder", agent_id: "a1"}' |
  FACTORY_BRAIN="$tmp/brain" python3 "$HOOKS/stop-gate.py"; }
case "$(gate $'claims:\n- tests pass R-abc123')" in "") echo "ok   gate passes a cited receipt";; *) echo "FAIL gate passes a cited receipt"; fail=1;; esac
case "$(gate $'claims:\n- tests pass')" in *block*) echo "ok   gate blocks a bare claim";; *) echo "FAIL gate blocks a bare claim"; fail=1;; esac
case "$(gate $'claims:\n- tests pass R-ffffff')" in *block*) echo "ok   gate blocks an unknown receipt";; *) echo "FAIL gate blocks an unknown receipt"; fail=1;; esac

exit $fail
