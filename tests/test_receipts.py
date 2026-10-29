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

    def test_exact_redaction_and_no_control_chars(self):
        run(REC, self.ev(tool_input={"command": "export MY_API_KEY=hunter2 password=abc"}), self.home)
        rec = self.receipts()[0]
        self.assertEqual(rec["input"]["command"], "export MY_API_KEY=[REDACTED] password=[REDACTED]")
        raw = (self.home / ".brain/job/job-1/relay/receipts/builder-a1.jsonl").read_bytes()
        self.assertFalse([b for b in raw if b < 0x20 and b != 0x0a])

    def test_more_patterns(self):
        cmd = 'k sk_live_abcdefgh12345 rk_live_abcdefgh12345 sk_test_abcdefgh12345 token: abc123 "secret": "zzz999"'
        run(REC, self.ev(tool_input={"command": cmd}, tool_response={"stdout": 'api_key: qq77'}), self.home)
        blob = json.dumps(self.receipts()[0])
        for s in ["abcdefgh12345", "abc123", "zzz999", "qq77"]:
            self.assertNotIn(s, blob)

    def test_key_created_private(self):
        run(REC, self.ev(), self.home)
        k = self.home / ".config/factory/receipt.key"
        self.assertEqual(k.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.home / ".config/factory").stat().st_mode & 0o777, 0o700)
        self.assertEqual(len(k.read_bytes()), 32)
        self.assertIn("mac", self.receipts()[0])

    def test_agent_traversal(self):
        run(REC, self.ev(agent_type="../../../x", agent_id="/etc/y"), self.home)
        d = self.home / ".brain/job/job-1/relay/receipts"
        files = list(d.iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].parent.resolve(), d.resolve())
        self.assertFalse((self.home / ".brain/job/x").exists())

    def test_malformed_exit_zero(self):
        for stdin in ["", "garbage", "{}", "[]", '{"cwd": 5}', json.dumps({"cwd": str(self.work)}),
                      json.dumps({"cwd": str(self.work), "hook_event_name": "PostToolUse"})]:
            for script in (REC, GATE):
                r = subprocess.run([sys.executable, str(script)], input=stdin, capture_output=True, text=True,
                                   env=dict(os.environ, HOME=str(self.home)))
                self.assertEqual(r.returncode, 0, (script, stdin, r.stderr))
                self.assertEqual(r.stdout, "")

    def log(self):
        return self.home / ".brain/job/job-1/relay/receipts/builder-a1.jsonl"

    def test_gate_tampered_tail(self):
        run(REC, self.ev(), self.home)
        rec = self.receipts()[0]
        rec["tail"] = "forged"
        self.log().write_text(json.dumps(rec) + "\n")
        out = json.loads(self.gate(f"claims:\n- ok {rec['id']}").stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("bad mac", out["reason"])

    def test_gate_corrupt_line(self):
        run(REC, self.ev(), self.home)
        rid = self.receipts()[0]["id"]
        with open(self.log(), "a") as fh:
            fh.write("{not json\n")
        out = json.loads(self.gate(f"claims:\n- ok {rid}").stdout)
        self.assertIn("corrupt", out["reason"])

    def test_gate_forged_no_mac(self):
        run(REC, self.ev(), self.home)
        with open(self.log(), "a") as fh:
            fh.write(json.dumps({"id": "R-abcdef", "agent": "builder", "run": "a1"}) + "\n")
        out = json.loads(self.gate("claims:\n- ok R-abcdef").stdout)
        self.assertIn("missing mac", out["reason"])

    def test_gate_missing_key(self):
        run(REC, self.ev(), self.home)
        rid = self.receipts()[0]["id"]
        (self.home / ".config/factory/receipt.key").unlink()
        out = json.loads(self.gate(f"claims:\n- ok {rid}").stdout)
        self.assertIn("key is missing", out["reason"])

    def test_gate_every_line_checked(self):
        run(REC, self.ev(), self.home)
        rid = self.receipts()[0]["id"]
        out = json.loads(self.gate(f"claims:\n- ok {rid}\nalso tests pass").stdout)
        self.assertIn("also tests pass", out["reason"])

    def test_gate_stop_hook_active(self):
        r = run(GATE, {"stop_hook_active": True, "cwd": str(self.work), "last_assistant_message": "claims:\n- x"}, self.home)
        self.assertEqual(r.stdout, "")

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
