#!/usr/bin/env python3
# Stop gate. Register on SubagentStop. An agent may not return a claim
# without a receipt it recorded in this run.
import json, os, pathlib, re, sys

e = json.load(sys.stdin)
if e.get("stop_hook_active"):
    sys.exit(0)  # one retry, never a loop
msg = e.get("last_assistant_message") or ""
if "claims:" not in msg:
    sys.exit(0)  # nothing claimed (scribe), nothing to check

BRAIN = pathlib.Path(os.environ.get("FACTORY_BRAIN", "~/.brain")).expanduser()


def job_of(cwd):
    for d in [pathlib.Path(cwd), *pathlib.Path(cwd).parents]:
        f = d / ".factory-job"
        if f.is_file():
            return f.read_text().strip()


job = job_of(e.get("cwd", "."))
if not job:
    sys.exit(0)

block = msg.split("claims:", 1)[1]
block = re.split(r"\n\s*(unverified|asks|friction|details):", block)[0]
claims = [l.strip() for l in block.splitlines() if l.strip().startswith("-")]
log = BRAIN / "job" / job / "relay" / "receipts" / f"{e.get('agent_type')}-{e.get('agent_id')}.jsonl"
known = {json.loads(l)["id"] for l in log.read_text().splitlines() if l.strip()} if log.exists() else set()

bare = [c for c in claims if not re.search(r"R-[0-9a-f]{6}", c)]
unknown = sorted(set(re.findall(r"R-[0-9a-f]{6}", block)) - known)
if bare or unknown:
    reason = "Every claim cites a receipt you recorded in this run."
    if bare:
        reason += " No receipt: " + " | ".join(bare[:5]) + "."
    if unknown:
        reason += " Not in your log: " + ", ".join(unknown) + "."
    reason += " Prove it now, or move it under unverified."
    print(json.dumps({"decision": "block", "reason": reason}))
