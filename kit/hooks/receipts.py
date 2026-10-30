#!/usr/bin/env python3
# Receipts hook. Register on PostToolUse and PostToolUseFailure, matcher "*".
# The harness records what a tool really returned; an agent can only cite it.
import hashlib, json, os, pathlib, re, sys, time

e = json.load(sys.stdin)
BRAIN = pathlib.Path(os.environ.get("FACTORY_BRAIN", "~/.brain")).expanduser()

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN[^-]*PRIVATE KEY-----.*?(?:-----END[^-]*PRIVATE KEY-----|$)", re.S),
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"xox[abp]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/\-]+=*"),
]
SECRET_KEY = r"[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_?KEY)[A-Za-z0-9_]*"
# KEY=value, KEY: value, "KEY": "value"
KV = re.compile(
    r"""(?i)(?P<k>\b""" + SECRET_KEY +
    r"""(?:\\?["'])?\s*[=:]\s*(?:\\?["'])?)(?P<v>[^\s"',}\\]+)"""
)


def redact(s):
    for p in SECRET_PATTERNS:
        s = p.sub("[REDACTED]", s)
    return KV.sub(r"\g<k>[REDACTED]", s)


def redact_obj(o, key=""):
    if isinstance(o, str):
        return "[REDACTED]" if re.fullmatch(SECRET_KEY, key, re.I) else redact(o)
    if isinstance(o, list):
        return [redact_obj(x, key) for x in o]
    if isinstance(o, dict):
        return {k: redact_obj(v, str(k)) for k, v in o.items()}
    return o


def job_of(cwd):
    # scribe bind-worktree writes the job slug to .factory-job at the worktree
    # root (listed in .git/info/exclude, so it is never committed).
    for d in [pathlib.Path(cwd), *pathlib.Path(cwd).parents]:
        f = d / ".factory-job"
        if f.is_file():
            return f.read_text().strip()


job = job_of(e.get("cwd", "."))
# A slug that could leave the brain (../..) is not a job.
if not job or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", job):
    sys.exit(0)

failed = e.get("hook_event_name") == "PostToolUseFailure"
body = e.get("error") if failed else e.get("tool_response")  # Bash: stdout, stderr, interrupted
text = json.dumps(body, ensure_ascii=False)
rid = "R-" + hashlib.sha1(e["tool_use_id"].encode()).hexdigest()[:6]
# Normal names pass unchanged, so the stop gate still finds the log.
agent = re.sub(r"[^A-Za-z0-9_.:-]", "_", e.get("agent_type") or "relay")
run = re.sub(r"[^A-Za-z0-9_.:-]", "_", e.get("agent_id") or "main")

rec = {
    "id": rid,
    "tool_use_id": e["tool_use_id"],
    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "agent": agent,
    "run": run,
    "cwd": e.get("cwd"),
    "tool": e.get("tool_name"),
    "input": redact_obj(e.get("tool_input")),
    "ok": not failed,  # a failed Bash call's error starts "Exit code N"
    "sha256": hashlib.sha256(text.encode()).hexdigest(),  # of the original text
    "tail": redact(text)[-4000:],
}
out = BRAIN / "job" / job / "relay" / "receipts"
out.mkdir(parents=True, exist_ok=True, mode=0o700)
fd = os.open(out / f"{agent}-{run}.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
with os.fdopen(fd, "a") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

# additionalContext is documented for PostToolUse; check your Claude Code
# version shows it on PostToolUseFailure too.
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": e.get("hook_event_name", "PostToolUse"),
    "additionalContext": f"receipt {rid}",
}}))
