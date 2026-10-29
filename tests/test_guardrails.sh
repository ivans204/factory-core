#!/bin/bash
# Feeds {"tool_input":{"command":...}} to the guardrails hook and asserts exit codes.
HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/factory-git-guardrails.sh"
pass=0; fail=0
run() { # expected_exit command
  local want=$1 cmd=$2 got
  jq -n --arg c "$cmd" '{tool_input:{command:$c}}' | bash "$HOOK" >/dev/null 2>&1
  got=$?
  if [ "$got" = "$want" ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL (want $want, got $got): $cmd"; fi
}
for c in 'git reset --hard' 'git checkout -- file' 'git checkout .' 'git restore file' 'git clean -fd' \
  'git branch -D x' 'git stash drop' 'git commit --no-verify -m x' 'HUSKY=0 git commit' \
  'git push --force origin x' 'git push -f' 'git -C /tmp/r reset --hard HEAD'; do run 2 "$c"; done
for c in 'git status' 'git restore --staged f' 'git push --force-with-lease' 'git branch -d x' \
  'git commit -m "do not run git reset --hard"' 'git checkout -b feature' 'git clean -n' 'ls'; do run 0 "$c"; done
run 0 "$(printf 'git commit -F - <<EOF\nnotes: git push --force is bad\nEOF')"
echo "guardrails: $pass passed, $fail failed"
[ "$fail" = 0 ]
