#!/usr/bin/env python3
# Receipt recorder. Register on PostToolUse and PostToolUseFailure, matcher "*".
# The harness records what a tool really returned; an agent can only cite it.
# Each record carries an HMAC so the stop gate can tell it from a forged line.
# Any malformed input: exit 0 silently (a hook must never break the session).
import hashlib, json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_common as fc

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{8,}"),
    re.compile(r"gh[po]_[A-Za-z0-9]{8,}"),
    re.compile(r"xox[abp]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/\-]+=*"),
]
# KEY=value, KEY: value, "KEY": "value" where KEY contains TOKEN|SECRET|PASSWORD|API_KEY.
KV = re.compile(
    r"""(?i)(?P<k>\b[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_?KEY)[A-Za-z0-9_]*"""
    r"""(?:\\?["'])?\s*[=:]\s*(?:\\?["'])?)(?P<v>[^\s"',}\\]+)"""
)


def redact(s):
    for p in SECRET_PATTERNS:
        s = p.sub("[REDACTED]", s)
    return KV.sub(r"\g<k>[REDACTED]", s)


def redact_obj(o):
    if isinstance(o, str):
        return redact(o)
    if isinstance(o, list):
        return [redact_obj(x) for x in o]
    if isinstance(o, dict):
        return {k: redact_obj(v) for k, v in o.items()}
    return o


def main():
    e = json.load(sys.stdin)
    job = fc.job_of(e.get("cwd", "."))
    if not job:
        return
    failed = e["hook_event_name"] == "PostToolUseFailure"
    body = e.get("error") if failed else e.get("tool_response")   # Bash: stdout, stderr, interrupted
    text = json.dumps(body, ensure_ascii=False)
    tuid = e["tool_use_id"]
    if not isinstance(tuid, str) or not isinstance(e["tool_name"], str):
        return
    agent, run = fc.agent_run(e)
    rec = {
        "id": "R-" + hashlib.sha1(tuid.encode()).hexdigest()[:6],
        "tool_use_id": tuid,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "agent": agent,
        "run": run,
        "tool": e["tool_name"],
        "input": redact_obj(e.get("tool_input")),
        "ok": not failed,                  # a failed Bash call's error starts "Exit code N"
        "sha256": hashlib.sha256(text.encode()).hexdigest(),   # of the original, unredacted text
        "tail": redact(text)[-4000:],
    }
    key = fc.load_key(create=True)
    rec["mac"] = fc.mac_of(key, rec)
    path = fc.log_path(job, agent, run)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": e["hook_event_name"],
        "additionalContext": f"receipt {rec['id']}",
    }}))


try:
    main()
except Exception:
    pass
sys.exit(0)
