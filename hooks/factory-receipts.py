#!/usr/bin/env python3
# Receipt recorder. Register on PostToolUse and PostToolUseFailure, matcher "*".
# The harness records what a tool really returned; an agent can only cite it.
import hashlib, json, pathlib, re, sys, time
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"gh[po]_[A-Za-z0-9]{8,}"),
    re.compile(r"xox[abp]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/\-]+=*"),
]
# KEY=value where KEY contains TOKEN|SECRET|PASSWORD|API_KEY: keep the key.
KV = re.compile(r"""(?i)(\b[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)[A-Za-z0-9_]*\s*=\s*)[^\s"',}\\]+""")

def redact(s):
    for p in SECRET_PATTERNS:
        s = p.sub("[REDACTED]", s)
    return KV.sub(r"[REDACTED]", s)

def redact_obj(o):
    if isinstance(o, str):
        return redact(o)
    if isinstance(o, list):
        return [redact_obj(x) for x in o]
    if isinstance(o, dict):
        return {k: redact_obj(v) for k, v in o.items()}
    return o

e = json.load(sys.stdin)

def job_of(cwd):
    # The orchestrator binds a worktree to a job with a .factory-job file at
    # its root, listed in .git/info/exclude so it is never committed.
    for d in [pathlib.Path(cwd), *pathlib.Path(cwd).parents]:
        f = d / ".factory-job"
        if f.is_file():
            slug = f.read_text().strip()
            return slug if SLUG.fullmatch(slug) else None

job = job_of(e.get("cwd", "."))
if not job:
    sys.exit(0)

failed = e["hook_event_name"] == "PostToolUseFailure"
body = e.get("error") if failed else e.get("tool_response")   # Bash: stdout, stderr, interrupted
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
    "tool": e["tool_name"],
    "input": redact_obj(e.get("tool_input")),
    "ok": not failed,                  # a failed Bash call's error starts "Exit code N"
    "sha256": hashlib.sha256(text.encode()).hexdigest(),
    "tail": redact(text)[-4000:],
}
out = pathlib.Path.home() / ".brain/job" / job / "relay/receipts"
out.mkdir(parents=True, exist_ok=True)
with open(out / f"{agent}-{run}.jsonl", "a") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

# Documented for PostToolUse; check your version honours it on PostToolUseFailure.
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": e["hook_event_name"],
    "additionalContext": f"receipt {rid}",
}}))
