#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys, tempfile, unittest

H = pathlib.Path(__file__).resolve().parent.parent / "hooks"
GUARD, BIND, REC, GATE = (H / n for n in ("factory-state-guard.py", "factory-bind.py",
                                           "factory-receipts.py", "factory-stop-gate.py"))


def run(script, stdin="", home=None, args=()):
    env = dict(os.environ, HOME=str(home)) if home else None
    return subprocess.run([sys.executable, str(script), *args], input=stdin, capture_output=True, text=True, env=env)


def guard(tool, **ti):
    return run(GUARD, json.dumps({"tool_name": tool, "tool_input": ti})).returncode


class Guard(unittest.TestCase):
    def test_blocked(self):
        k = os.path.expanduser("~/.config/factory/receipt.key")
        for tool, ti in [("Read", {"file_path": k}), ("Read", {"file_path": "~/.config/factory/bindings.json"}),
                         ("Bash", {"command": "cat ~/.config/factory/receipt.key"}),
                         ("Bash", {"command": "cat $HOME/.config/factory/receipt.key"}),
                         ("Bash", {"command": "cat /Users/bob/.config/factory/x"}),
                         ("Bash", {"command": "cat ~/.config/fac\"\"tory/receipt.key"}),
                         ("Write", {"file_path": "/h/.brain/job/j/relay/receipts/x.jsonl", "content": "x"}),
                         ("Grep", {"pattern": "x", "path": "/h/.brain/job/j/relay/receipts"}),
                         ("Glob", {"pattern": "/h/.config/factory/*"}),
                         ("Bash", {"command": "cat ~/.con\"\"fig/fac\"\"tory/x"}),
                         ("Bash", {"command": "cat ~/.Config/Factory/x"}),
                         ("Read", {"file_path": "~/.Config/Factory/receipt.key"}),
                         ("Bash", {"command": "printf x >| .factory-job"}),
                         ("Bash", {"command": "cat a && rm .factory-job"}),
                         ("Bash", {"command": "rm .factory-job"}), ("Bash", {"command": "echo x > .factory-job"}),
                         ("Bash", {"command": "sed -i s/a/b/ .factory-job"}),
                         ("Bash", {"command": "echo x | tee ../.factory-job"}),
                         ("Write", {"file_path": "/w/.factory-job", "content": "x"}),
                         ("Edit", {"file_path": "/w/.factory-job"})]:
            with self.subTest(tool=tool, ti=ti):
                self.assertEqual(guard(tool, **ti), 2)

    def test_allowed(self):
        for tool, ti in [("Read", {"file_path": "/w/.factory-job"}),
                         ("Grep", {"pattern": "receipt.key", "path": "./hooks"}),
                         ("Grep", {"pattern": "relay/receipts"}),
                         ("Read", {"file_path": "/w/docs/relay/receipts.md"}),
                         ("Bash", {"command": "cat .factory-job && npm install"}),
                         ("Bash", {"command": "cat .factory-job | tee /dev/stderr"}),
                         ("Bash", {"command": "ls .factory-job && cp a b"}),
                         ("Bash", {"command": "grep -rn receipt.key hooks/"}),
                         ("Bash", {"command": "git log -- relay/receipts"}), ("Bash", {"command": "cat .factory-job"}),
                         ("Bash", {"command": "cat .factory-job 2>/dev/null"}),
                         ("Edit", {"file_path": "/w/src/a.py", "old_string": "a", "new_string": "b"}),
                         ("Write", {"file_path": "/w/README.md", "content": "~/.config/factory is protected"}),
                         ("Bash", {"command": "git status"}), ("Grep", {"pattern": "TODO", "path": "/w/src"}),
                         ("Glob", {"pattern": "**/*.py"})]:
            with self.subTest(tool=tool, ti=ti):
                self.assertEqual(guard(tool, **ti), 0)

    def test_flat_path_alone(self):
        # no literal marker anywhere: only the quote-stripped text contains it
        self.assertEqual(guard("Bash", command='cat ~/.con""fig/fac""tory/x'), 2)
        self.assertEqual(guard("Bash", command="cat ~/.con\\fig/fac\\tory/x"), 2)

    def test_malformed(self):
        for s in ["", "junk", "{}", '{"tool_name":"Bash","tool_input":5}']:
            self.assertEqual(run(GUARD, s).returncode, 0)


class Binding(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        base = pathlib.Path(self._td.name).resolve()
        self.home, self.wt = base / "home", base / "wt"
        self.home.mkdir(); self.wt.mkdir()
        subprocess.run(["git", "init", "-q", str(self.wt)], check=True)

    def bind(self, *a):
        return run(BIND, home=self.home, args=a)

    def gate(self, msg="claims:\n- x R-abcdef"):
        e = {"hook_event_name": "SubagentStop", "cwd": str(self.wt), "agent_type": "b", "agent_id": "1",
             "last_assistant_message": msg}
        return run(GATE, json.dumps(e), self.home)

    def test_bind_writes_index_file_exclude(self):
        r = self.bind(str(self.wt), "job-9")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.wt / ".factory-job").read_text().strip(), "job-9")
        idx = json.loads((self.home / ".config/factory/bindings.json").read_text())
        self.assertEqual(idx, {str(self.wt): "job-9"})
        self.assertIn(".factory-job", (self.wt / ".git/info/exclude").read_text())
        self.assertEqual((self.home / ".config/factory/bindings.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.bind(str(self.wt), "Bad Slug").returncode, 1)

    def test_deleted_file_is_tampered(self):
        self.bind(str(self.wt), "job-9")
        (self.wt / ".factory-job").unlink()
        out = json.loads(self.gate().stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("tampered", out["reason"])

    def test_changed_file_is_tampered(self):
        self.bind(str(self.wt), "job-9")
        (self.wt / ".factory-job").write_text("other-job\n")
        self.assertIn("tampered", json.loads(self.gate().stdout)["reason"])

    def test_recorder_uses_index_slug(self):
        self.bind(str(self.wt), "job-9")
        (self.wt / ".factory-job").write_text("other-job\n")
        e = {"hook_event_name": "PostToolUse", "cwd": str(self.wt), "tool_use_id": "t1", "tool_name": "Bash",
             "tool_input": {"command": "ls"}, "tool_response": {"stdout": "x"}}
        run(REC, json.dumps(e), self.home)
        self.assertTrue(list((self.home / ".brain/job/job-9/relay/receipts").glob("*.jsonl")))
        self.assertFalse((self.home / ".brain/job/other-job").exists())

    def test_unbind(self):
        self.bind(str(self.wt), "job-9")
        self.assertEqual(self.bind("--unbind", str(self.wt)).returncode, 0)
        self.assertFalse((self.wt / ".factory-job").exists())
        self.assertEqual(json.loads((self.home / ".config/factory/bindings.json").read_text()), {})
        self.assertEqual(self.gate().stdout, "")

    def test_unreadable_job_file_is_tampered(self):
        self.bind(str(self.wt), "job-9")
        (self.wt / ".factory-job").write_bytes(b"\xff\xfe\x00bad")
        self.assertIn("tampered", json.loads(self.gate().stdout)["reason"])

    def test_corrupt_index_is_tampered(self):
        self.bind(str(self.wt), "job-9")
        (self.home / ".config/factory/bindings.json").write_text("{nope")
        self.assertIn("tampered", json.loads(self.gate().stdout)["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
