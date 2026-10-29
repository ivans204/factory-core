#!/usr/bin/env python3
import json, pathlib, subprocess, sys, unittest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "hooks/factory-git-guardrails.py"

BLOCK = [
    "git reset --hard", "git checkout -- file", "git checkout .", "git restore file", "git clean -fd",
    "git branch -D x", "git stash drop", "git commit --no-verify -m x", "HUSKY=0 git commit",
    "git push --force origin x", "git push -f", "git -C /tmp/r reset --hard HEAD",
    'git commit -m "$(git reset --hard)"', "git commit -m \"`git reset --hard`\"",
    'eval "git reset --hard"', "bash -c 'git clean -fdx'", "git -c core.hooksPath=/dev/null commit",
    "git --git-dir=.git reset --hard", "git commit -nm x", "git checkout -f", "git switch -f main",
    "git push origin +main", 'git commit -m "unbalanced', "ls && git reset --hard", "ls; git clean -xdf",
    "echo hi | git reset --hard", "git restore --staged --worktree f", "git branch --delete --force x",
    "git stash clear", "git config core.hooksPath /dev/null", "LEFTHOOK=0 git commit -m x",
    "git push --no-verify", "sudo -u bob git reset --hard", "bash <<EOF\ngit reset --hard\nEOF",
    "cat <<EOF\n$(git reset --hard)\nEOF", "git reset --ha", "git -c alias.x='reset --hard' x",
    "git commit -m ok -n", "find . -exec git clean -fd {} ;", "( git reset --hard )",
    "g''it reset --hard", "git reset $'--hard'",
]
PASS = [
    "git status", "git restore --staged f", "git push --force-with-lease", "git branch -d x",
    'git commit -m "do not run git reset --hard"', "git checkout -b feature", "git clean -n", "ls",
    "git commit -F - <<EOF\nnotes: git push --force is bad\nEOF",
    "git commit -m 'fix: $(not run) in single quotes'",
    'echo "git reset --hard is dangerous"', "git log --format='%H'", "git commit -m \"-n is fine\"",
    "git commit -am 'add -n flag'", "git diff | head", "git push origin main", "git checkout main",
    "git stash", "git stash pop", "git switch main", "git -C /tmp/r status",
    "git commit -m \"$(date)\"", "cat <<'EOF'\n$(git reset --hard)\nEOF",
]


def run(cmd):
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_input": {"command": cmd}}),
                       capture_output=True, text=True)
    return r.returncode


class T(unittest.TestCase):
    def test_block(self):
        for c in BLOCK:
            with self.subTest(c=c):
                self.assertEqual(run(c), 2)

    def test_pass(self):
        for c in PASS:
            with self.subTest(c=c):
                self.assertEqual(run(c), 0)

    def test_malformed_input(self):
        for stdin in ["", "not json", "{}", '{"tool_input":{"command":5}}']:
            r = subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)

    def test_message_text(self):
        r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_input": {"command": "git branch -D x"}}),
                           capture_output=True, text=True)
        self.assertIn("BLOCKED by factory guardrails", r.stderr)
        self.assertIn("Instead:", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
