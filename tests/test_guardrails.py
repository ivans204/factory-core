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
    "git commit -m ok -n", 'env -S "git reset --hard"', "env --split-string='git clean -fd'",
    "env -Sgit\\ reset\\ --hard", "bash <<< 'git reset --hard'", "eval <<< 'git clean -fd'",
    "source <<< 'git reset --hard'", "${GIT:-git} reset --hard", "$GIT checkout -f", "git${IFS}reset --hard", "$(echo git) reset --hard",
    "GIT_CONFIG_PARAMETERS=\"'core.hooksPath=/x'\" git commit", "export GIT_CONFIG_COUNT=1",
    "cat <<EOF | bash\ngit reset --hard\nEOF", "git checkout -- src/a.py", "export HUSKY=0",
    "env GIT_CONFIG_KEY_0=core.hooksPath git commit", "timeout 5 git reset --hard", "time git clean -fd",
    "xargs -I{} git reset --hard", "git commit -m 'unbalanced", "`git reset --hard`",
    "for f in a; do git reset --hard; done", "if true; then git clean -fd; fi",
    "find . -exec true {} + ; git reset --hard", "git am --no-verify x.patch", "find . -exec git clean -fd {} ;", "( git reset --hard )",
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
    "git commit -m \"$(date)\"",
    "$HOME/bin/tool --version", '"$(pwd)/scripts/run.sh" arg', "$HOME/.local/bin/uv sync", '"$PYTHON" -m pytest',
    "${EDITOR:-vi} --version", "$(npm bin)/eslint .", "`which python3` --version", '"$HOME/bin/tool" x',
    '"${HOME}"/bin/x', '"$(git rev-parse --show-toplevel)/scripts/test.sh"', "$VIRTUAL_ENV/bin/python -m pytest",
    '"$PWD/bin/x"', "env -S 'echo hi'", "echo foo#bar's",
    "git commit -m \"$(cat <<'EOF'\nfix: don't crash (really)\nEOF\n)\"",
    "gh pr create --body \"$(cat <<'EOF'\nit's (really) done\nEOF\n)\"",
    "grep -- --no-verify README.md", "rg -e --no-verify .", "ls # it's a comment with git",
    "for f in a b; do echo git push --force; done", "if true; then echo git reset --hard; fi",
    "git checkout feature -- src/a.py", "npm test -- --no-verify-something", "git log --oneline | head -5",
    "cd /tmp && git status", "echo $HOME", "ls $(pwd)", "git diff $(git merge-base HEAD main)",
    "git commit -m \"msg\" 2>&1 | tail -3", "python3 -c 'print(1)'", "x=1; echo $x", "cat <<'EOF'\n$(git reset --hard)\nEOF",
]


def timed(cmd):
    import time
    best = 9
    for _ in range(3):
        t = time.perf_counter()
        r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_input": {"command": cmd}}),
                           capture_output=True, text=True)
        best = min(best, time.perf_counter() - t)
    return r.returncode, best


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

    def test_perf(self):
        import random, string
        random.seed(1)
        rnd = " ".join("".join(random.choices(string.ascii_lowercase, k=random.randint(2, 9))) for _ in range(7000))[:50000]
        cases = [("find . " + "-exec x {} + " * 40 + "; git reset --hard", 2),
                 ("time " + "a " * 10000, 0), (rnd, 0), ("x " + "$(a " * 300 + ")" * 300, 0),
                 ("echo " + "(" * 2000, 0)]
        for cmd, want in cases:
            code, secs = timed(cmd)
            print(f"perf {len(cmd)}B exit={code} {secs * 1000:.0f}ms")
            self.assertEqual(code, want, cmd[:40])
            self.assertLess(secs, 0.1, cmd[:40])

    def test_unexpected_exception(self):
        import importlib.util
        src = HOOK.read_text().replace("def check(raw):", "def check(raw):\n    raise KeyError('boom')\n\ndef _unused(raw):", 1)
        tmp = HOOK.parent.parent / "tests" / "_boom_guard.py"
        tmp.write_text(src)
        try:
            for cmd, want in (("git status", 2), ("GIT status", 2), ("echo sh -c ls", 0)):
                r = subprocess.run([sys.executable, str(tmp)], input=json.dumps({"tool_input": {"command": cmd}}),
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, want, cmd)
                if want == 2:
                    self.assertIn("guardrail error", r.stderr)
        finally:
            tmp.unlink()

    def test_perf2(self):
        cases = [("echo " + "$(a)" * 12400, 0), ('""' * 24990, 0), ("echo " + "<(a)" * 12400, 0),
                 ("echo " + "`a`" * 12000, 0)]
        for cmd, want in cases:
            code, secs = timed(cmd)
            print(f"perf2 {len(cmd)}B exit={code} {secs * 1000:.0f}ms")
            self.assertEqual(code, want)
            self.assertLess(secs, 0.1)

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
