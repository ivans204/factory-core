#!/usr/bin/env python3
# Receipts hook. Register on PostToolUse and PostToolUseFailure, matcher "*".
# The harness records what a tool really returned; an agent can only cite it.
import hashlib, json, os, pathlib, sys, time

e = json.load(sys.stdin)
BRAIN = pathlib.Path(os.environ.get("FACTORY_BRAIN", "~/.brain")).expanduser()


def job_of(cwd):
    # scribe bind-worktree writes the job slug to .factory-job at the worktree
    # root (listed in .git/info/exclude, so it is never committed).
    for d in [pathlib.Path(cwd), *pathlib.Path(cwd).parents]:
        f = d / ".factory-job"
        if f.is_file():
            return f.read_text().strip()


job = job_of(e.get("cwd", "."))
if not job:
    sys.exit(0)

failed = e.get("hook_event_name") == "PostToolUseFailure"
body = e.get("error") if failed else e.get("tool_response")  # Bash: stdout, stderr, interrupted
text = json.dumps(body, ensure_ascii=False)
rid = "R-" + hashlib.sha1(e["tool_use_id"].encode()).hexdigest()[:6]
agent = e.get("agent_type") or "relay"
run = e.get("agent_id") or "main"

rec = {
    "id": rid,
    "tool_use_id": e["tool_use_id"],
    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "agent": agent,
    "run": run,
    "cwd": e.get("cwd"),
    "tool": e.get("tool_name"),
    "input": e.get("tool_input"),
    "ok": not failed,  # a failed Bash call's error starts "Exit code N"
    "sha256": hashlib.sha256(text.encode()).hexdigest(),
    "tail": text[-4000:],
}
out = BRAIN / "job" / job / "relay" / "receipts"
out.mkdir(parents=True, exist_ok=True)
with open(out / f"{agent}-{run}.jsonl", "a") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

# additionalContext is documented for PostToolUse; check your Claude Code
# version shows it on PostToolUseFailure too.
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": e.get("hook_event_name", "PostToolUse"),
    "additionalContext": f"receipt {rid}",
}}))
