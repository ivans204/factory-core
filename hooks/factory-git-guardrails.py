#!/usr/bin/env python3
# Factory git guardrails (PreToolUse, Bash). Refuses commands that have lost
# work or bypassed the commit gate. Adapted from mattpocock/skills
# git-guardrails-claude-code (MIT). The human can still run any of these with a
# `!` prefix, which no PreToolUse hook sees.
#
# The command is parsed, not grepped: split into simple commands, then each
# git invocation is analysed after its global options. Substitutions, eval and
# `sh -c` strings are checked recursively. Not a sandbox: see README.
import json, os, re, shlex, sys

class Block(Exception):
    def __init__(self, why, instead):
        self.why, self.instead = why, instead

class ParseError(Exception):
    pass

SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
WRAPPERS = {"env", "sudo", "doas", "command", "exec", "time", "nohup", "xargs", "nice", "ionice",
            "timeout", "builtin", "stdbuf", "setsid", "caffeinate", "{", "}", "!", "if", "then",
            "do", "else", "elif", "while", "until"}
ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
BYPASS_ENV = re.compile(r"HUSKY=0|LEFTHOOK=(0|false)")
HEREDOC = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z0-9_.\-]+)\2")
SHELL_WORD = re.compile(r"(^|[\s;&|(`])(\S*/)?(bash|sh|zsh|dash|ksh)(\s|$)")
MAX_DEPTH = 8

def block(why, instead):
    raise Block(why, instead)

def bypass():
    block("commit and push gates are not bypassed by agents.",
          "fix what the gate reports, or stop and say what it reported.")

def grab_paren(text, start):
    """Return (body, index after the closing paren) for a $( ... ) opened before start."""
    depth, j, q, n = 1, start, None, len(text)
    while j < n:
        c = text[j]
        if q == "'":
            if c == "'":
                q = None
        elif c == "\\":
            j += 1
        elif c in "'\"":
            q = None if q == c else (q or c)
        elif q is None and c == "(":
            depth += 1
        elif q is None and c == ")":
            depth -= 1
            if depth == 0:
                return text[start:j], j + 1
        j += 1
    raise ParseError("unbalanced parenthesis")

def strip_heredocs(text):
    """Drop heredoc bodies from text. Returns (text, bodies to check as shell, bodies to scan for substitutions)."""
    out, shell_bodies, sub_bodies = [], [], []
    i, n, q, pending, line_start = 0, len(text), None, [], 0
    while i < n:
        c = text[i]
        if q == "'":
            q = None if c == "'" else q
        elif c == "\\":
            out.append(text[i:i + 2]); i += 2; continue
        elif q == '"':
            q = None if c == '"' else q
        elif c in "'\"":
            q = c
        elif c == "\n" and pending:
            out.append(c); i += 1
            for delim, quoted, shell in pending:
                body = []
                while i < n:
                    j = text.find("\n", i)
                    j = n if j < 0 else j
                    line, i = text[i:j], j + 1
                    if line.strip() == delim:
                        break
                    body.append(line)
                (shell_bodies if shell else ([] if quoted else sub_bodies)).append("\n".join(body))
            pending, line_start = [], i
            continue
        elif text.startswith("<<<", i):
            out.append("<<<"); i += 3; continue
        elif text.startswith("<<", i):
            m = HEREDOC.match(text, i)
            if m:
                shell = bool(SHELL_WORD.search(text[line_start:i]))
                pending.append((m.group(3), bool(m.group(2)), shell))
                out.append(text[i:m.end()]); i = m.end(); continue
        elif c == "\n":
            line_start = i + 1
        out.append(c); i += 1
    return "".join(out), shell_bodies, sub_bodies

def scan(text, heredoc=False):
    """Pull command substitutions out of text. Returns (text with them replaced, [bodies]).
    Newlines outside quotes become ' ; '. Single quotes are inert; double quotes are not."""
    out, subs, i, n = [], [], 0, len(text)
    q = '"' if heredoc else None
    while i < n:
        c = text[i]
        if q == "'":
            out.append(c)
            q = None if c == "'" else q
            i += 1; continue
        if c == "\\":
            if text[i + 1:i + 2] == "\n" and q is None:
                out.append(" ")
            else:
                out.append(text[i:i + 2])
            i += 2; continue
        if c == "$" and text[i + 1:i + 2] == "(":
            body, i = grab_paren(text, i + 2)
            subs.append(body); out.append("SUBST"); continue
        if c == "`":
            j = i + 1
            while j < n and text[j] != "`":
                j += 2 if text[j] == "\\" else 1
            if j >= n:
                raise ParseError("unbalanced backtick")
            subs.append(text[i + 1:j].replace("\\`", "`")); out.append("SUBST"); i = j + 1; continue
        if q is None:
            if c in "<>" and text[i + 1:i + 2] == "(":
                body, i = grab_paren(text, i + 2)
                subs.append(body); out.append("SUBST"); continue
            if c == "$" and text[i + 1:i + 2] in ("'", '"'):
                i += 1; continue                      # $'..' and $".." quoting
            if c in "'\"":
                q = c
            elif c == "\n":
                out.append(" ; "); i += 1; continue
        elif q == '"' and c == '"' and not heredoc:
            q = None
        out.append(c); i += 1
    if q and not heredoc:
        raise ParseError("unbalanced quote")
    return "".join(out), subs

def tokenize(text):
    lex = shlex.shlex(text, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        toks = list(lex)
    except ValueError as ex:
        raise ParseError(str(ex))
    cmds, cur = [], []
    for t in toks:
        if set(t) <= set(";&|()"):
            cmds.append(cur); cur = []
        else:
            cur.append(t)
    cmds.append(cur)
    return [c for c in cmds if c]

def check(text, depth=0):
    if depth > MAX_DEPTH:
        raise ParseError("nested too deep")
    main, shell_bodies, sub_bodies = strip_heredocs(text)
    clean, subs = scan(main)
    for b in sub_bodies:
        subs += scan(b, heredoc=True)[1]
    for cmd in tokenize(clean):
        check_cmd(cmd, depth)
    for s in subs + shell_bodies:
        check(s, depth + 1)

def check_cmd(toks, depth, wrap=True):
    for t in toks:
        if BYPASS_ENV.fullmatch(t):
            bypass()
        if t == "--no-verify":
            bypass()
    for k, t in enumerate(toks):
        if t in ("-exec", "-execdir", "-ok", "-okdir"):
            check_cmd(toks[k + 1:], depth)
    i = 0
    while i < len(toks) and ASSIGN.match(toks[i]):
        i += 1
    if i >= len(toks):
        return
    w, rest = os.path.basename(toks[i]), toks[i + 1:]
    if w == "git":
        check_git(rest)
    elif w == "eval":
        check(" ".join(rest), depth + 1)
    elif w in SHELLS:
        for k, a in enumerate(rest):
            if a.startswith("-") and not a.startswith("--") and "c" in a[1:]:
                if k + 1 < len(rest):
                    check(rest[k + 1], depth + 1)
                break
        if "<<<" in rest and rest.index("<<<") + 1 < len(rest):
            check(rest[rest.index("<<<") + 1], depth + 1)
    elif w in WRAPPERS and wrap:
        for j in range(i + 1, len(toks)):
            check_cmd(toks[j:], depth, wrap=False)
            if w == "env" and re.search(r"\s", toks[j]):
                check(toks[j], depth + 1)           # env -S "git ..."

def shorts(args):
    return [a[1:] for a in args if a.startswith("-") and not a.startswith("--") and len(a) > 1]

def has_short(args, ch):
    return any(ch in s for s in shorts(args))

def long_is(a, name):
    return a.split("=", 1)[0] == "--" + name

def check_git(args):
    i, cfg = 0, []
    while i < len(args):
        a = args[i]
        if a in ("-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix"):
            i += 2
        elif a == "--config-env":
            cfg.append(args[i + 1] if i + 1 < len(args) else ""); i += 2
        elif a.startswith("--config-env="):
            cfg.append(a.split("=", 1)[1]); i += 1
        elif a == "-c":
            cfg.append(args[i + 1] if i + 1 < len(args) else ""); i += 2
        elif a.startswith("-c") and not a.startswith("--"):
            cfg.append(a[2:]); i += 1
        elif a.startswith("-"):
            i += 1
        else:
            break
    for c in cfg:
        key = c.split("=", 1)[0].lower()
        if key == "core.hookspath":
            bypass()
        if key.startswith("alias."):
            block("an inline git alias can hide a blocked command.", "run the real git command.")
    if i >= len(args):
        return
    sub, A = args[i], args[i + 1:]
    if sub == "config" and any(a.lower().startswith(("core.hookspath", "alias.")) for a in A):
        bypass()
    if sub in ("commit", "push", "merge", "rebase", "cherry-pick", "am", "revert"):
        if any(a.startswith("--no-v") and "--no-verify".startswith(a.split("=", 1)[0]) for a in A):
            bypass()
    if sub == "reset" and any(a.startswith("--ha") and "--hard".startswith(a) for a in A):
        block("git reset --hard throws away uncommitted work.", "commit first, or stop and ask the human.")
    elif sub == "checkout" and ("--" in A or "." in A or has_short(A, "f") or any(long_is(a, "force") for a in A)):
        block("git checkout -- / . / -f discards edits, including another agent's.",
              "edit your own file back; leave others alone.")
    elif sub == "switch" and (has_short(A, "f") or any(long_is(a, n) for a in A for n in ("force", "discard-changes"))):
        block("git switch -f discards edits, including another agent's.", "commit or stash-and-say first.")
    elif sub == "restore":
        staged = has_short(A, "S") or any(long_is(a, "staged") for a in A)
        worktree = has_short(A, "W") or any(long_is(a, "worktree") for a in A)
        if not staged or worktree:
            block("git restore discards working-tree edits.", "use --staged to unstage; edit your own file back.")
    elif sub == "clean" and (has_short(A, "f") or any(long_is(a, "force") for a in A)):
        block("git clean -f deletes untracked files for good.", "list them with git clean -n and ask.")
    elif sub == "branch":
        force = has_short(A, "f") or any(long_is(a, "force") for a in A)
        delete = has_short(A, "d") or any(long_is(a, "delete") for a in A)
        if has_short(A, "D") or (delete and force):
            block("git branch -D deletes unmerged work.", "ask, or use -d for a merged branch.")
    elif sub == "stash" and [a for a in A if not a.startswith("-")][:1] in (["drop"], ["clear"]):
        block("stash drop/clear deletes stashed work.", "keep it and say it exists.")
    elif sub == "commit":
        skip = False
        for a in A:
            if skip:
                skip = False
            elif a == "--":
                break
            elif a.startswith("--"):
                if "=" not in a and a.split("=")[0] in ("--message", "--file", "--author", "--date", "--template",
                                                        "--cleanup", "--reuse-message", "--reedit-message",
                                                        "--fixup", "--squash"):
                    skip = True
            elif a.startswith("-") and len(a) > 1:
                for k, ch in enumerate(a[1:]):
                    if ch == "n":
                        bypass()
                    if ch in "mFcCt":
                        skip = k == len(a) - 2
                        break
    elif sub == "push":
        if (has_short(A, "f") or any(long_is(a, "force") for a in A)
                or any(a.startswith("+") and len(a) > 1 for a in A)):
            block("a plain force push can overwrite someone else's commits.",
                  "use --force-with-lease, only on your own branch.")

def main():
    try:
        raw = json.load(sys.stdin)["tool_input"]["command"]
    except Exception:
        return 0
    if not isinstance(raw, str) or not raw.strip():
        return 0
    try:
        check(raw)
    except Block as b:
        print(f"BLOCKED by factory guardrails: {b.why}", file=sys.stderr)
        print(f"Instead: {b.instead}", file=sys.stderr)
        return 2
    except Exception:
        if "git" in raw.lower():
            print("BLOCKED by factory guardrails: could not parse the command.", file=sys.stderr)
            print("Instead: could not parse; simplify the command.", file=sys.stderr)
            return 2
    return 0

sys.exit(main())
