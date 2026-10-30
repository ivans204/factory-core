#!/bin/bash
# Git guardrails. Register on PreToolUse, matcher "Bash". Refuses commands that
# lose work or bypass the commit gate. Adapted from mattpocock/skills
# git-guardrails-claude-code (MIT). A person can still run any of these with a
# `!` prefix, which no PreToolUse hook sees.

RAW=$(jq -r '.tool_input.command // empty')
[ -z "$RAW" ] && exit 0
# Reduce the command to what the shell would run, one simple command per line.
# Quotes and escapes go, so "--no-verify" reads as --no-verify. Text stays out:
# heredoc bodies, quoted strings with spaces and commit messages become ''.
# `bash -c`, eval, shell heredocs and $(...) inside double quotes are commands,
# so they are read too. A value in a variable, or a script on disk, is not seen.
COMMANDS=$(printf '%s' "$RAW" | python3 -c '
import re, sys

SHELLS = {"sh", "bash", "zsh", "dash"}

def heredocs(s):
    out = []
    def strip(m):
        start = s.rfind("\n", 0, m.start()) + 1
        words = re.split(r"[\s;&|(]+", s[start:m.start()])
        if any(w.rsplit("/", 1)[-1] in SHELLS for w in words):
            out.append(m.group(3))
        return "\n"
    s = re.sub(r"<<-?\s*([\x27\x22]?)(\w+)\1[^\n]*\n(.*?)\n\s*\2\s*(?:\n|$)", strip, s, flags=re.S)
    return s, out

def parse(s, depth=0):
    if depth > 4:
        return [s]
    s, bodies = heredocs(s)
    lines, seg, inner = [], [], list(bodies)
    tok, quoted, spaced, started = "", False, False, False
    def end_word():
        nonlocal tok, quoted, spaced, started
        if not started:
            return
        prev = seg[-1] if seg else ""
        name = seg[0].rsplit("/", 1)[-1] if seg else ""
        if name == "eval" or (name in SHELLS and re.fullmatch(r"-[a-z]*c", prev)):
            inner.append(tok)
        if re.fullmatch(r"-[a-zA-Z]*m|--message|--body|--title|--grep", prev):
            tok = "\x27\x27"
        elif prev == "-c":
            tok = re.sub(r"\s", "_", tok)
        elif quoted and (spaced or not tok):
            tok = "\x27\x27"
        seg.append(tok)
        tok, quoted, spaced, started = "", False, False, False
    def end_seg():
        end_word()
        if seg:
            lines.append(" ".join(seg))
            seg.clear()
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            if s[i + 1:i + 2] != "\n":
                tok += s[i + 1:i + 2]
                started = True
            i += 2
            continue
        if c == "\x27":
            j = s.find("\x27", i + 1)
            j = n if j < 0 else j
            part = s[i + 1:j]
            tok += part
            quoted, started = True, True
            spaced = spaced or bool(re.search(r"\s", part))
            i = j + 1
            continue
        if c == "\x22":
            quoted, started = True, True
            i += 1
            while i < n and s[i] != "\x22":
                if s[i] == "\\":
                    tok += s[i + 1:i + 2]
                    i += 2
                elif s.startswith("$(", i):
                    level, j = 1, i + 2
                    while j < n and level:
                        level += {"(": 1, ")": -1}.get(s[j], 0)
                        j += 1
                    inner.append(s[i + 2:j - 1])
                    tok += s[i:j]
                    spaced = True
                    i = j
                elif s[i] == "`":
                    j = s.find("`", i + 1)
                    j = n if j < 0 else j
                    inner.append(s[i + 1:j])
                    spaced = True
                    i = j + 1
                else:
                    spaced = spaced or s[i].isspace()
                    tok += s[i]
                    i += 1
            i += 1
            continue
        if c == "&" and (s[i + 1:i + 2] == ">" or tok[-1:] == ">"):
            tok += c
            started = True
        elif c in ";&|()`\n":
            end_seg()
        elif c.isspace():
            end_word()
        else:
            tok += c
            started = True
        i += 1
    end_seg()
    for part in inner:
        lines += parse(part, depth + 1)
    return lines

print("\n".join(parse(sys.stdin.read())))
' 2>/dev/null) || COMMANDS="$RAW"

block() { echo "BLOCKED by factory guardrails: $1" >&2; echo "Instead: $2" >&2; exit 2; }
S='[[:space:]]'
G="git($S+(-[Cc]$S+[^[:space:]]+|--?[^[:space:]]+))*$S+"
# git ignores case in section and key names, so the key matches in any case.
KEY='[cC][oO][rR][eE]\.[hH][oO][oO][kK][sS][pP][aA][tT][hH]'
# Reading the hooks path changes nothing: a read has no value after the key.
READ="git($S+-C$S+[^[:space:]]+)?$S+config($S+(--(local|global|system|get|get-all)|get))*$S+$KEY($S*[0-9]*>&?$S*[^[:space:]]+)*$S*\$"

while IFS= read -r COMMAND; do
  echo "$COMMAND" | grep -qE "${G}reset$S+(.*$S)?--hard" &&
    block "git reset --hard throws away uncommitted work." "commit first, or stop and ask the human."
  echo "$COMMAND" | grep -qE "${G}checkout$S+(.*$S)?(--($S|\$)|\.($S|\$))" &&
    block "git checkout -- / . discards edits, including another agent's." "edit your own file back; leave others alone."
  { echo "$COMMAND" | grep -qE "${G}restore$S" && { ! echo "$COMMAND" | grep -qE -- "$S(--staged|-S)($S|\$)" || echo "$COMMAND" | grep -qE -- "$S(--worktree|-W)($S|\$)"; }; } &&
    block "git restore discards working-tree edits." "use --staged to unstage; edit your own file back."
  echo "$COMMAND" | grep -qE "${G}clean$S+(.*$S)?(-[a-zA-Z]*f|--force)" &&
    block "git clean -f deletes untracked files for good." "list them with git clean -n and ask."
  echo "$COMMAND" | grep -qE "${G}branch$S+(.*$S)?-[a-zA-Z]*D" &&
    block "git branch -D deletes unmerged work." "ask, or use -d for a merged branch."
  echo "$COMMAND" | grep -qE "${G}stash$S+(drop|clear)" &&
    block "git stash drop/clear deletes stashed work." "keep it and say it exists."
  # Add your project's gate-bypass switches to this pattern.
  { echo "$COMMAND" | grep -qE -- "$S--no-verify($S|\$)|(^|$S)LEFTHOOK=(0|false)|(^|$S)HUSKY=0|(^|$S)GIT_CONFIG_(PARAMETERS|COUNT|KEY_[0-9]+)=" ||
    echo "$COMMAND" | grep -qE -- "${G}commit$S+(.*$S)?-[a-zA-Z]*n[a-zA-Z]*($S|\$)" ||
    { echo "$COMMAND" | grep -qE "(^|[/[:space:]])git$S" && echo "$COMMAND" | sed -E "s/$READ//" | grep -qi 'core\.hookspath'; }; } &&
    block "commit and push gates are not bypassed by agents." "fix what the gate reports, or stop and say what it reported."
  echo "$COMMAND" | grep -qE "${G}push$S" && echo "$COMMAND" | grep -qE -- "($S--force($S|\$)|$S-[a-zA-Z]*f[a-zA-Z]*($S|\$)|$S\+[^[:space:]]+)" &&
    block "a plain force push can overwrite someone else's commits." "use --force-with-lease, only on your own branch."
done <<< "$COMMANDS"
exit 0
