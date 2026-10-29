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


def run(cmd, agent=None, cwd=None):
    p = {"tool_input": {"command": cmd}}
    if agent:
        p["agent_type"] = agent
    if cwd:
        p["cwd"] = cwd
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(p), capture_output=True, text=True)
    return r.returncode


FACTORY_BLOCK = [
    "gh pr merge 5 --squash", "gh -R o/r pr merge", "gh pr edit 5 --add-label ready", "gh pr edit --add-label=x",
    "gh api graphql -f query='mutation { resolveReviewThread(input:{threadId:\"x\"}) { clientMutationId } }'",
    "gh api graphql -F query=@- <<'EOF'\nmutation { resolveReviewThread(input:{}) {x} }\nEOF",
    "git branch -m new", "git branch -M new", "git branch --move a b", "git push origin main", "git push -u origin main",
    "git push origin master", "git push origin HEAD:main", "git push origin HEAD:refs/heads/master",
    "git push origin +main", "git push origin feat:main",
]
FACTORY_PASS = ["git push origin feat", "git push -u origin feat", "git push --force-with-lease origin feat",
                "git push origin HEAD:feat", "gh pr create --draft", "gh pr view 5", "gh pr edit 5 --title x",
                "gh api graphql -f query='{ viewer { login } }'", "git branch -d x", "git branch feat"]


class T(unittest.TestCase):
    def test_block(self):
        for c in BLOCK:
            with self.subTest(c=c):
                self.assertEqual(run(c), 2)

    def test_pass(self):
        for c in PASS:
            with self.subTest(c=c):
                self.assertEqual(run(c), 0)

    def test_factory_agents(self):
        for agent in ("factory:shipwright", "shipwright", "factory:scribe"):
            for c in FACTORY_BLOCK:
                with self.subTest(a=agent, c=c):
                    if c.startswith("git push origin +main"):
                        continue                       # blocked for everyone already
                    self.assertEqual(run(c, agent), 2)
            for c in FACTORY_PASS:
                with self.subTest(a=agent, c=c):
                    self.assertEqual(run(c, agent), 0)

    def test_non_factory_unaffected(self):
        for agent in (None, "builder", "factory:builder", "", "factory:"):
            for c in FACTORY_BLOCK:
                if c.startswith("git push origin +main"):
                    continue
                with self.subTest(a=agent, c=c):
                    self.assertEqual(run(c, agent), 0)

    def test_factory_plain_push_on_main(self):
        import tempfile
        for br, want in (("main", 2), ("feat", 0)):
            with tempfile.TemporaryDirectory() as d:
                subprocess.run(["git", "init", "-q", "-b", br, d], check=True)
                subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                                "--allow-empty", "-m", "x"], check=True)
                self.assertEqual(run("git push", "factory:shipwright", d), want, br)
                self.assertEqual(run("git push origin", "shipwright", d), want, br)
                self.assertEqual(run("git push origin HEAD", "shipwright", d), want, br)
                self.assertEqual(run("git push", None, d), 0, br)
                self.assertEqual(run("git push", "shipwright", d + "/nope"), 0)   # rev-parse fails -> skip

    def test_checkout_sides(self):
        for c in ("git checkout --theirs -- src/a.py", "git checkout --ours -- src/a.py", "git checkout --ours -- a b"):
            self.assertEqual(run(c), 0, c)
        for c in ("git checkout -- src/a.py", "git checkout --theirs --", "git checkout --ours ."):
            self.assertEqual(run(c), 2, c)

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
