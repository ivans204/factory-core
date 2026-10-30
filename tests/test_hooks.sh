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
blocks 'git config core.hooksPath /dev/null'
blocks "git config core.hooksPath ''"
blocks 'git config --global core.hooksPath /dev/null'
blocks 'git config --unset core.hooksPath'
blocks 'git -c core.hooksPath=/dev/null commit -m x'
blocks 'git config --get core.hooksPath; git config core.hooksPath /dev/null'
blocks 'git config core.hooksPath 2>/dev/null /dev/null'
passes 'git config core.hooksPath'
passes 'git config --get core.hooksPath'
passes 'git -C /repo config --local --get core.hooksPath'
passes 'git config get core.hooksPath'
passes 'git config core.hooksPath 2>/dev/null; echo done'
passes 'ls .git/hooks; git config core.hooksPath; git log -1'
passes 'x=$(git config core.hooksPath)'
passes 'git commit -m "never run git reset --hard"'
passes 'git restore --staged src/a.ts'
passes 'git push --force-with-lease origin feature'
passes 'git checkout -b feature'
passes "git commit -F - <<'EOF'
mention git reset --hard in the body
EOF"

# Stop gate: a claim must cite a receipt the agent recorded in this run.
tmp=$(mktemp -d "${TMPDIR:-/tmp}/test_hooks.XXXXXX") || exit 1; trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/wt" "$tmp/brain/job/demo/relay/receipts"
echo demo > "$tmp/wt/.factory-job"
echo '{"id": "R-abc123"}' > "$tmp/brain/job/demo/relay/receipts/builder-a1.jsonl"
gate() { jq -n --arg m "$1" --arg cwd "$tmp/wt" \
  '{last_assistant_message: $m, cwd: $cwd, agent_type: "builder", agent_id: "a1"}' |
  FACTORY_BRAIN="$tmp/brain" python3 "$HOOKS/stop-gate.py"; }
case "$(gate $'claims:\n- tests pass R-abc123')" in "") echo "ok   gate passes a cited receipt";; *) echo "FAIL gate passes a cited receipt"; fail=1;; esac
case "$(gate $'claims:\n- tests pass')" in *block*) echo "ok   gate blocks a bare claim";; *) echo "FAIL gate blocks a bare claim"; fail=1;; esac
case "$(gate $'claims:\n- tests pass R-ffffff')" in *block*) echo "ok   gate blocks an unknown receipt";; *) echo "FAIL gate blocks an unknown receipt"; fail=1;; esac

# Receipts: secrets never reach the log, a bad slug or agent never leaves the brain.
rec() { jq -n --arg cwd "$tmp/wt" --arg a "${1:-builder}" '{hook_event_name: "PostToolUse", cwd: $cwd,
  tool_use_id: "t1", tool_name: "Bash", agent_type: $a, agent_id: "a2",
  tool_input: {command: "curl -H \"Authorization: Bearer abc.def\" -d API_KEY=hunter2", env: {DB_PASSWORD: "plainpw"}},
  tool_response: {stdout: "ok ghp_abcdefgh12345678 PASSWORD=hunter3 -----BEGIN RSA PRIVATE KEY-----\nMIIEkey\n-----END RSA PRIVATE KEY-----"}}' |
  FACTORY_BRAIN="$tmp/brain" python3 "$HOOKS/receipts.py"; }
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
out=$(rec); log="$tmp/brain/job/demo/relay/receipts/builder-a2.jsonl"
check "receipt is announced" '[[ $out == *"receipt R-"* ]]'
check "receipt keeps the output" 'grep -q "ok \[REDACTED\]" "$log"'
check "receipt redacts secrets" '[ -s "$log" ] && ! grep -qE "abc\.def|hunter2|hunter3|plainpw|ghp_|MIIEkey" "$log"'
check "receipt log is owner-only" '[ "$(stat -f %Lp "$log" 2>/dev/null || stat -c %a "$log")" = 600 ]'
rec "../../../../escaped" >/dev/null
check "agent name cannot leave the log directory" '[ -z "$(find "$tmp" -name "*escaped*" ! -path "$tmp/brain/job/demo/relay/receipts/*")" ]'
echo '../../outside' > "$tmp/wt/.factory-job"; rec >/dev/null
check "bad slug writes nothing" '[ ! -e "$tmp/outside" ] && [ ! -e "$tmp/brain/outside" ]'
echo demo > "$tmp/wt/.factory-job"

exit $fail
