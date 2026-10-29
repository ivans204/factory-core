#!/usr/bin/env python3
# Factory git guardrails (PreToolUse, Bash). Catches agent mistakes and cheap
# tricks around destructive git commands and commit-gate bypasses. Adapted from
# mattpocock/skills git-guardrails-claude-code (MIT). The human can still run
# any of these with a `!` prefix, which no PreToolUse hook sees.
#
# NOT a shell parser and NOT a security boundary (that is the sandbox's job).
# One linear pass: heredoc bodies out, then $(...)/backtick bodies out, then
# shlex tokens split into simple commands. Every body is checked exactly once.
import collections, json, os, re, shlex, signal, sys

class Block(Exception):
    def __init__(self, why, instead):
        self.why, self.instead = why, instead

class ParseError(Exception):
    pass

SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "for", "case", "esac", "{", "}", "!"}
# wrapper -> options that consume the next token
WRAPPERS = {
    "sudo": set("-u -g -h -p -U -r -t -C -D -R -T".split()), "doas": {"-u", "-C"},
    "env": {"-u", "-C", "-S"}, "time": set(), "nohup": set(), "nice": {"-n"}, "ionice": {"-c", "-n", "-p"},
    "command": set(), "exec": {"-a"}, "builtin": set(), "setsid": set(), "stdbuf": set(),
    "xargs": set("-I -n -P -d -L -E -s -a -l -i".split()), "timeout": {"-k", "-s"},
}
ASSIGN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.S)
DECLARE = {"export", "declare", "typeset", "readonly", "local"}
SHELL_WORD = re.compile(r"""(^|[\s;&|(`"'])(\S*/)?(bash|sh|zsh|eval|source|\.)(\s|$)""")
HEREDOC = re.compile(r"""(?<!<)<<(?!<)(-?)\s*(['"]?)([A-Za-z0-9_.\-]+)\2""")
SPECIAL = re.compile(r"""[\\'"$`()#\n<>]""")
PLACEHOLDER = "@@SUBST@@"
GIT_PUSHLIKE = {"commit", "push", "merge", "rebase", "am", "cherry-pick"}

def block(why, instead):
    raise Block(why, instead)

def bypass():
    block("commit and push gates are not bypassed by agents.",
          "fix what the gate reports, or stop and say what it reported.")

def check_assignment(name, value):
    if ((name == "HUSKY" and value == "0") or (name == "LEFTHOOK" and value in ("0", "false"))
            or name in ("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT")
            or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))):
        bypass()

def split_heredocs(text):
    """Cut heredoc bodies out. Returns (text, bodies that feed a shell, unquoted non-shell bodies)."""
    if "<<" not in text:
        return text, [], []
    lines, out, shell_b, sub_b, i = text.split("\n"), [], [], [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        ops = HEREDOC.findall(line)
        if not ops:
            continue
        j, found = i, []
        for _dash, quote, delim in ops:
            k = j
            while k < len(lines) and lines[k].strip() != delim:
                k += 1
            if k >= len(lines):
                found = None            # no terminator: not a heredoc, keep the lines as text
                break
            found.append((bool(quote), "\n".join(lines[j:k])))
            j = k + 1
        if found is None:
            continue
        i = j
        is_shell = bool(SHELL_WORD.search(line))
        for quoted, body in found:
            if is_shell:
                shell_b.append(body)
            elif not quoted:
                sub_b.append(body)      # unquoted heredocs still run $(...)
    return "\n".join(out), shell_b, sub_b

class Ctx:
    __slots__ = ("kind", "buf", "q", "depth")
    def __init__(self, kind, q=None):
        self.kind, self.buf, self.q, self.depth = kind, [], q, 0

def scan(text, literal=False):
    """One linear pass. Returns (text with $(...)/backtick bodies replaced by a placeholder, [bodies]).
    Single quotes are inert, double quotes are not. Comments are dropped, newlines outside quotes
    become ' ; '. literal=True scans heredoc text: quotes never open."""
    stack, bodies, i, n = [Ctx("root", '"' if literal else None)], [], 0, len(text)

    def close():
        c = stack.pop()
        if c.q and not literal:
            raise ParseError("unbalanced quote")
        bodies.append("".join(c.buf))
        stack[-1].buf.append(PLACEHOLDER)

    while i < n:
        m = SPECIAL.search(text, i)
        cur = stack[-1]
        if not m:
            cur.buf.append(text[i:])
            break
        j = m.start()
        if j > i:
            cur.buf.append(text[i:j])
        c, i, q = text[j], j + 1, cur.q
        if q == "'":
            cur.buf.append(c)
            if c == "'":
                cur.q = None
        elif literal and c in "'\"":
            cur.buf.append(c)
        elif c == "\\":
            nxt = text[i:i + 1]
            i += 1 if nxt else 0
            if nxt == "\n" and q is None:
                cur.buf.append(" ")
            elif nxt == "`" and cur.kind == "bt":
                cur.buf.append("`")
            else:
                cur.buf.append("\\" + nxt)
        elif c == "'":
            cur.buf.append(c)
            if q is None:
                cur.q = "'"
        elif c == '"':
            cur.buf.append(c)
            cur.q = '"' if q is None else None
        elif c == "$":
            nxt = text[i:i + 1]
            if nxt == "(":
                stack.append(Ctx("dollar")); i += 1
            elif nxt in ("'", '"') and q is None:
                pass                                    # $'..' / $".." quoting
            else:
                cur.buf.append(c)
        elif c == "`":
            if cur.kind == "bt":
                close()
            else:
                stack.append(Ctx("bt"))
        elif c in "<>" and q is None and text[i:i + 1] == "(":
            stack.append(Ctx("proc")); i += 1
        elif c == "(":
            cur.buf.append(c)
            if q is None:
                cur.depth += 1
        elif c == ")":
            if q is None and cur.kind in ("dollar", "proc") and cur.depth == 0:
                close()
            else:
                cur.buf.append(c)
                if q is None:
                    cur.depth = max(0, cur.depth - 1)
        elif c == "#":
            if q is None and (j == 0 or text[j - 1] in " \t\n;&|("):
                k = text.find("\n", i)
                i = n if k < 0 else k                   # comment: drop to end of line
            else:
                cur.buf.append(c)
        elif c == "\n":
            cur.buf.append(" ; " if q is None else c)
        else:
            cur.buf.append(c)                           # < or > not opening a process substitution
    if len(stack) > 1 or (stack[0].q and not literal):
        raise ParseError("unbalanced quote or substitution")
    return "".join(stack[0].buf), bodies

def tokenize(text):
    lex = shlex.shlex(text, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""                                 # scan() already dropped comments
    toks = list(lex)                                    # ValueError on unbalanced quotes
    cmds, cur, at_start, skip_to = [], [], True, None
    for t in toks:
        if set(t) <= set(";&|()"):
            if cur:
                cmds.append(cur)
            cur, at_start, skip_to = [], True, None
        elif skip_to is not None:
            if t == skip_to:
                skip_to = None
                at_start = True
        elif at_start and t in KEYWORDS:
            if t == "for":
                skip_to, at_start = "do", False          # `for x in ...` header: skip to do
                cur = []
            elif t == "case":
                skip_to, at_start = "in", False
                cur = []
        else:
            at_start = False
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds

def analyze(toks, work):
    i, n = 0, len(toks)
    while i < n:
        a = ASSIGN.fullmatch(toks[i])
        if a:
            check_assignment(a.group(1), a.group(2)); i += 1; continue
        w = os.path.basename(toks[i])
        if w in WRAPPERS:
            takes = WRAPPERS[w]
            i += 1
            while i < n and (toks[i].startswith("-") or (w == "timeout" and re.fullmatch(r"[0-9.]+[smhd]?", toks[i]))):
                i += 2 if toks[i] in takes else 1
                if w == "timeout" and i <= n and re.fullmatch(r"[0-9.]+[smhd]?", toks[i - 1]):
                    break
            if w == "timeout" and i < n and re.fullmatch(r"[0-9.]+[smhd]?", toks[i]):
                i += 1
            continue
        break
    if i >= n:
        return
    word, rest = toks[i], toks[i + 1:]
    if "$" in word or "`" in word or PLACEHOLDER in word:
        block("command name is computed.", "write the command name literally.")
    w = os.path.basename(word)
    if w == "git":
        check_git(rest)
    elif w == "eval":
        work.append(("text", " ".join(rest)))
    elif w in SHELLS:
        for k, a in enumerate(rest):
            if a.startswith("-") and not a.startswith("--") and "c" in a[1:]:
                if k + 1 < len(rest):
                    work.append(("text", rest[k + 1]))
                break
    elif w in DECLARE:
        for a in rest:
            m = ASSIGN.fullmatch(a)
            if m:
                check_assignment(m.group(1), m.group(2))
    elif w == "find":
        k = 0
        while k < len(rest):
            if rest[k] in ("-exec", "-execdir", "-ok", "-okdir"):
                e = k + 1
                while e < len(rest) and rest[e] not in (";", "+"):
                    e += 1
                analyze(rest[k + 1:e], work)            # one simple command per -exec, each token once
                k = e
            k += 1

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
    if sub in GIT_PUSHLIKE and any(a.startswith("--no-v") and "--no-verify".startswith(a.split("=", 1)[0]) for a in A):
        bypass()
    if sub == "reset" and any(a.startswith("--ha") and "--hard".startswith(a) for a in A):
        block("git reset --hard throws away uncommitted work.", "commit first, or stop and ask the human.")
    elif sub == "checkout":
        dd = A.index("--") if "--" in A else -1
        has_ref = dd > 0 and any(not a.startswith("-") for a in A[:dd])
        if ((dd >= 0 and not has_ref) or "." in A or has_short(A, "f") or any(long_is(a, "force") for a in A)):
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
                if "=" not in a and a in ("--message", "--file", "--author", "--date", "--template", "--cleanup",
                                          "--reuse-message", "--reedit-message", "--fixup", "--squash"):
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

def check(raw):
    work, budget = collections.deque([("text", raw)]), 4 * len(raw) + 10000
    while work:
        kind, text = work.popleft()
        budget -= len(text)
        if budget < 0:
            raise TimeoutError
        if kind == "text":
            text, shell_bodies, sub_bodies = split_heredocs(text)
            text, bodies = scan(text)
            for b in sub_bodies:
                bodies += scan(b, literal=True)[1]
            work.extend(("text", b) for b in shell_bodies)
            work.extend(("body", b) for b in bodies)
        for cmd in tokenize(text):
            analyze(cmd, work)

def on_alarm(*_):
    raise TimeoutError

def main():
    try:
        raw = json.load(sys.stdin)["tool_input"]["command"]
    except Exception:
        return 0
    if not isinstance(raw, str) or not raw.strip():
        return 0
    signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(1)
    try:
        check(raw)
    except Block as b:
        print(f"BLOCKED by factory guardrails: {b.why}", file=sys.stderr)
        print(f"Instead: {b.instead}", file=sys.stderr)
        return 2
    except (ParseError, ValueError):
        print("BLOCKED by factory guardrails: could not parse the command.", file=sys.stderr)
        print("Instead: could not parse; simplify the command.", file=sys.stderr)
        return 2
    except (TimeoutError, RecursionError):
        print("BLOCKED by factory guardrails: command too complex to check.", file=sys.stderr)
        print("Instead: too complex; split it into simpler commands.", file=sys.stderr)
        return 2
    except Exception:
        return 0                                        # a bug here must not wedge normal work
    finally:
        signal.alarm(0)
    return 0

sys.exit(main())
