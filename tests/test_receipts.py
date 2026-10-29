#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
REC = ROOT / "hooks/factory-receipts.py"
GATE = ROOT / "hooks/factory-stop-gate.py"


def run(script, event, home):
    env = dict(os.environ, HOME=str(home))
    return subprocess.run([sys.executable, str(script)], input=json.dumps(event),
                          capture_output=True, text=True, env=env)


class T(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self._td.name) / "home"
        self.work = pathlib.Path(self._td.name) / "work"
        self.home.mkdir(); self.work.mkdir()
        (self.work / ".factory-job").write_text("job-1\n")
        self.addCleanup(self._td.cleanup)

    def ev(self, **kw):
        e = {"hook_event_name": "PostToolUse", "cwd": str(self.work), "tool_use_id": "toolu_1",
             "tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_response": {"stdout": "ok"},
             "agent_type": "builder", "agent_id": "a1"}
        e.update(kw)
        return e

    def receipts(self, job="job-1"):
        d = self.home / ".brain/job" / job / "relay/receipts"
        return [json.loads(l) for f in sorted(d.glob("*.jsonl")) for l in f.read_text().splitlines()] if d.exists() else []

    def test_written(self):
        r = run(REC, self.ev(), self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        recs = self.receipts()
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0]["id"].startswith("R-"))
        self.assertTrue((self.home / ".brain/job/job-1/relay/receipts/builder-a1.jsonl").exists())

    def test_redaction(self):
        secrets = ["sk-abcdefghijklmnop1234", "ghp_abcdefghijklmnop1234", "gho_abcdefghijklmnop1234",
                   "xoxb-1234567890-abcdef", "AKIAABCDEFGHIJKLMNOP", "Bearer abc.def-ghi123"]
        cmd = "curl " + " ".join(secrets) + " && export MY_API_KEY=hunter2value DB_PASSWORD=pw12345"
        out = "GITHUB_TOKEN=tok_zzzzzz123\nok " + secrets[0]
        run(REC, self.ev(tool_input={"command": cmd}, tool_response={"stdout": out}), self.home)
        rec = self.receipts()[0]
        blob = json.dumps(rec)
        for s in secrets + ["hunter2value", "pw12345", "tok_zzzzzz123"]:
            self.assertNotIn(s, blob)
        self.assertIn("[REDACTED]", rec["input"]["command"])
        self.assertIn("[REDACTED]", rec["tail"])
        import hashlib
        orig = json.dumps({"stdout": out}, ensure_ascii=False)
        self.assertEqual(rec["sha256"], hashlib.sha256(orig.encode()).hexdigest())

    def test_failure_event(self):
        run(REC, self.ev(hook_event_name="PostToolUseFailure", error="Exit code 1"), self.home)
        self.assertFalse(self.receipts()[0]["ok"])

    def test_bad_slug(self):
        (self.work / ".factory-job").write_text("../../etc")
        r = run(REC, self.ev(), self.home)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")
        self.assertFalse((self.home / ".brain").exists())
        self.assertFalse((self.home.parent / "etc").exists())
        g = run(GATE, self.ev(hook_event_name="SubagentStop",
                              last_assistant_message="claims:\n- did it"), self.home)
        self.assertEqual((g.returncode, g.stdout), (0, ""))

    def gate(self, msg):
        return run(GATE, {"hook_event_name": "SubagentStop", "cwd": str(self.work),
                          "agent_type": "builder", "agent_id": "a1",
                          "last_assistant_message": msg}, self.home)

    def test_gate_blocks_bare_claim(self):
        r = self.gate("claims:\n- tests pass")
        self.assertEqual(json.loads(r.stdout)["decision"], "block")

    def test_gate_passes_recorded(self):
        run(REC, self.ev(), self.home)
        rid = self.receipts()[0]["id"]
        r = self.gate(f"claims:\n- tests pass {rid}")
        self.assertEqual(r.stdout, "")
        r = self.gate("claims:\n- tests pass R-ffffff")
        self.assertEqual(json.loads(r.stdout)["decision"], "block")

    def test_gate_no_claims(self):
        self.assertEqual(self.gate("done").stdout, "")


if __name__ == "__main__":
    unittest.main(verbosity=1)
