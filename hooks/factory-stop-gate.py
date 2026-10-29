#!/usr/bin/env python3
# Stop gate. Register on SubagentStop. An agent may not return a claim
# without a receipt it recorded in this run. Once a job is bound it fails
# CLOSED: a corrupt, forged or unverifiable log blocks. Malformed stdin: exit 0.
import hmac, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_common as fc

ID = re.compile(r"R-[0-9a-f]{6}")


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


try:
    e = json.load(sys.stdin)
    if not isinstance(e, dict) or e.get("stop_hook_active"):
        sys.exit(0)                     # one retry, never a loop
    msg = e.get("last_assistant_message") or ""
    if not isinstance(msg, str) or "claims:" not in msg:
        sys.exit(0)                     # nothing claimed (Scribe), nothing to check
    agent, run = fc.agent_run(e)
except SystemExit:
    raise
except Exception:
    sys.exit(0)
try:
    job = fc.job_of(e.get("cwd", "."))
except Exception:
    try:
        bound = fc.index_path().exists()
    except Exception:
        bound = False
    if bound:
        block("Job binding could not be read: the binding index exists but the job lookup failed. "
              "Stop and tell the human.")
    sys.exit(0)
if not job:
    sys.exit(0)

if job.tampered:
    block(f"Job binding tampered: the binding index for job {job} and its .factory-job file disagree. "
          "Stop and tell the human; do not edit either.")

section = msg.split("claims:", 1)[1]
section = re.split(r"\n\s*(unverified|asks|friction|details):", section)[0]
claims = [l.strip() for l in section.splitlines() if l.strip()]
if not claims:
    sys.exit(0)

try:
    key = fc.load_key(create=False)
    if key is None:
        block("Receipt key is missing (~/.config/factory/receipt.key): receipts cannot be verified.")
    log = fc.log_path(job, agent, run)
    known, problems = set(), []
    lines = log.read_text().splitlines() if log.exists() else []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            if not isinstance(rec, dict) or not ID.fullmatch(str(rec.get("id", ""))):
                raise ValueError
        except ValueError:
            problems.append(f"corrupt log line {n}")
            continue
        mac = rec.get("mac")
        if not isinstance(mac, str):
            problems.append(f"missing mac on line {n}")
        elif not hmac.compare_digest(mac, fc.mac_of(key, rec)):
            problems.append(f"bad mac on line {n}")
        elif fc.safe_name(rec.get("agent"), "") != agent or fc.safe_name(rec.get("run"), "") != run:
            problems.append(f"record on line {n} belongs to another run")
        else:
            known.add(rec["id"])
    if problems:
        block("Receipt log failed verification (" + "; ".join(problems[:5]) + "). Do not edit the log; "
              "re-run the checks to record fresh receipts, or move the claims under unverified.")
except SystemExit:
    raise
except Exception as ex:
    block(f"Receipt log could not be verified ({type(ex).__name__}).")

bare = [c for c in claims if not ID.search(c)]
unknown = sorted(set(ID.findall(section)) - known)
if bare or unknown:
    reason = "Every claim cites a receipt you recorded in this run."
    if bare:
        reason += " No receipt: " + " | ".join(bare[:5]) + "."
    if unknown:
        reason += " Not in your log: " + ", ".join(unknown) + "."
    reason += " Prove it now, or move it under unverified."
    block(reason)
