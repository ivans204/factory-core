#!/usr/bin/env python3
# State guard (PreToolUse). Keeps agents away from factory state: the receipt key,
# binding index and receipts, and writes to .factory-job. String based and fast;
# a guard against accidents and cheap tricks, not a sandbox (use permissions.deny
# and the sandbox for that). Malformed input: exit 0.
import json, os, pathlib, re, sys

# Path arguments: path-segment matches, case-insensitive (macOS volumes are).
PATH_MARKERS = re.compile(r"(^|/)\.config/factory(/|$)|(^|/)relay/receipts(/|$)|(^|/)receipt\.key$", re.I)
# Bash text: the same idea, but anywhere in the command.
BASH_MARKERS = re.compile(r"\.config/factory(?![\w-])|/relay/receipts(/|\s|$|['\"])|/receipt\.key", re.I)
PATH_KEYS = {"Grep": ("path", "glob"), "Glob": ("pattern", "path")}
DEFAULT_KEYS = ("file_path", "path", "notebook_path")
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
JOB_REDIRECT = re.compile(r">>?\s*\S*\.factory-job")
JOB_VERB = re.compile(r"\b(rm|mv|cp|tee|truncate|unlink|shred|dd|install|ln)\b"
                      r"|\b(sed|perl)\b[^|;&\n]*\s-[a-zA-Z]*i")


def denied(why):
    print(f"BLOCKED by factory state guard: {why}", file=sys.stderr)
    print("Instead: factory state is managed by the harness; ask the human.", file=sys.stderr)
    sys.exit(2)


def bash_text(cmd):
    # also look at the text with quotes and backslashes removed (.con""fig/fac""tory)
    flat = re.sub(r"""['"\\]""", "", cmd)
    if BASH_MARKERS.search(cmd) or BASH_MARKERS.search(flat):
        denied("the command references factory state (~/.config/factory or relay/receipts).")
    if ".factory-job" in cmd:
        # a write verb or redirect only counts inside the simple command that names .factory-job
        for seg in re.split(r"&&|\|\||[;|&\n]", cmd.replace(">|", ">")):
            if ".factory-job" in seg and (JOB_REDIRECT.search(seg) or JOB_VERB.search(seg)):
                denied("the command modifies .factory-job.")


def main():
    e = json.load(sys.stdin)
    tool, ti = e.get("tool_name"), e.get("tool_input")
    if not isinstance(ti, dict):
        return
    if tool == "Bash":
        if isinstance(ti.get("command"), str):
            bash_text(ti["command"])
        return
    for k in PATH_KEYS.get(tool, DEFAULT_KEYS):
        v = ti.get(k)
        if not isinstance(v, str):
            continue
        cands = {v}
        if k != "pattern":
            cands.add(os.path.realpath(os.path.expanduser(v)))
        if any(PATH_MARKERS.search(c) for c in cands):
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
