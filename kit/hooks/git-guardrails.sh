#!/bin/bash
# Git guardrails. Register on PreToolUse, matcher "Bash". Refuses commands that
# lose work or bypass the commit gate. Adapted from mattpocock/skills
# git-guardrails-claude-code (MIT). A person can still run any of these with a
# `!` prefix, which no PreToolUse hook sees.

RAW=$(jq -r '.tool_input.command // empty')
[ -z "$RAW" ] && exit 0
# Match command words only: heredoc bodies and quoted strings (commit messages,
# PR bodies) are text, not commands. Trade-off: `bash -c '...'` is not inspected.
COMMAND=$(printf '%s' "$RAW" | python3 -c '
import re, sys
s = sys.stdin.read()
s = re.sub(r"<<-?\s*([\x27\x22]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(\n|$)", " ", s, flags=re.S)
s = re.sub(r"\x27[^\x27]*\x27", "\x27\x27", s)
s = re.sub(r"\x22(?:[^\x22\\\\]|\\\\.)*\x22", "\x22\x22", s)
print(s)
' 2>/dev/null || printf '%s' "$RAW")

block() { echo "BLOCKED by factory guardrails: $1" >&2; echo "Instead: $2" >&2; exit 2; }
G='git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+'

echo "$COMMAND" | grep -qE 'reset[[:space:]]+(.*[[:space:]])?--hard' &&
  block "git reset --hard throws away uncommitted work." "commit first, or stop and ask the human."
echo "$COMMAND" | grep -qE "${G}checkout[[:space:]]+(.*[[:space:]])?(--([[:space:]]|\$)|\.([[:space:]]|\$))" &&
  block "git checkout -- / . discards edits, including another agent's." "edit your own file back; leave others alone."
echo "$COMMAND" | grep -qE "${G}restore[[:space:]]" && ! echo "$COMMAND" | grep -qE -- '--staged' &&
  block "git restore discards working-tree edits." "use --staged to unstage; edit your own file back."
echo "$COMMAND" | grep -qE "${G}clean[[:space:]]+(.*[[:space:]])?-[a-zA-Z]*f" &&
  block "git clean -f deletes untracked files for good." "list them with git clean -n and ask."
echo "$COMMAND" | grep -qE "${G}branch[[:space:]]+(.*[[:space:]])?-D" &&
  block "git branch -D deletes unmerged work." "ask, or use -d for a merged branch."
echo "$COMMAND" | grep -qE "${G}stash[[:space:]]+(drop|clear)" &&
  block "git stash drop/clear deletes stashed work." "keep it and say it exists."
# Add your project's gate-bypass switches to this pattern.
echo "$COMMAND" | grep -qE -- '--no-verify|(^|[[:space:]])LEFTHOOK=(0|false)|(^|[[:space:]])HUSKY=0|core\.hooksPath' &&
  block "commit and push gates are not bypassed by agents." "fix what the gate reports, or stop and say what it reported."
echo "$COMMAND" | grep -qE "${G}push[[:space:]]" && echo "$COMMAND" | grep -qE -- '(--force([[:space:]]|$)|[[:space:]]-f([[:space:]]|$)|[[:space:]]\+[^[:space:]]+)' &&
  block "a plain force push can overwrite someone else's commits." "use --force-with-lease, only on your own branch."
exit 0
