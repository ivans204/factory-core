#!/usr/bin/env python3
# State guard (PreToolUse). Keeps agents away from factory state: the receipt key,
# binding index and receipts, and writes to .factory-job. String based and fast;
# a guard against accidents and cheap tricks, not a sandbox (use permissions.deny
# and the sandbox for that). Malformed input: exit 0.
import json, os, pathlib, re, sys

MARKERS = (".config/factory", "relay/receipts", "receipt.key")
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PATH_KEYS = ("file_path", "path", "notebook_path", "pattern")
BASH_WRITE = re.compile(
    r"(>>?\s*\S*\.factory-job|\b(rm|mv|cp|tee|truncate|unlink|shred|dd|install|ln)\b"
    r"|\bsed\b[^|;&\n]*\s-[a-zA-Z]*i|\bperl\b[^|;&\n]*\s-[a-zA-Z]*i)")


def denied(why):
    print(f"BLOCKED by factory state guard: {why}", file=sys.stderr)
    print("Instead: factory state is managed by the harness; ask the human.", file=sys.stderr)
    sys.exit(2)


def marked(s):
    # also look at the text with quotes and backslashes removed (.config/fac""tory)
    flat = re.sub(r"""['"\\]""", "", s)
    return any(m in s or m in flat for m in MARKERS)


def main():
    e = json.load(sys.stdin)
    tool, ti = e.get("tool_name"), e.get("tool_input")
    if not isinstance(ti, dict):
        return
    if tool == "Bash":
        cmd = ti.get("command")
        if not isinstance(cmd, str):
            return
        if marked(cmd):
            denied("the command references factory state (~/.config/factory or relay/receipts).")
        if ".factory-job" in cmd and BASH_WRITE.search(cmd):
            denied("the command modifies .factory-job.")
        return
    for k in PATH_KEYS:
        v = ti.get(k)
        if not isinstance(v, str):
            continue
        cands = {v}
        if k != "pattern":
            cands.add(os.path.realpath(os.path.expanduser(v)))
        if any(marked(c) for c in cands):
            denied(f"{k} points into factory state.")
        if tool in WRITE_TOOLS and pathlib.PurePath(v).name == ".factory-job":
            denied(".factory-job is bound by the harness, not edited by agents.")


try:
    main()
except SystemExit:
    raise
except Exception:
    pass
sys.exit(0)
