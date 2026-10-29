#!/usr/bin/env python3
import pathlib, re, unittest

A = pathlib.Path(__file__).resolve().parent.parent / "agents"
CONTRACT = "~/orca/factory-core/knowledge/contract.md"
MODELS = {"fable", "opus", "sonnet", "haiku"}
FORBIDDEN = ["npm ", "php artisan", "semaphore", "/orca/callega"]


def front(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    return dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)


class Agents(unittest.TestCase):
    def files(self):
        fs = sorted(A.glob("*.md"))
        self.assertTrue(fs)
        return fs

    def test_frontmatter(self):
        for f in self.files():
            fm = {k.strip(): v.strip() for k, v in front(f.read_text()).items()}
            for k in ("name", "description", "tools", "model"):
                self.assertTrue(fm.get(k), f"{f.name}: missing {k}")
            self.assertIn(fm["model"], MODELS, f.name)
            self.assertEqual(fm["name"], f.stem)

    def test_no_project_literals(self):
        for f in self.files():
            t = f.read_text().lower()
            for bad in FORBIDDEN:
                self.assertNotIn(bad, t, f"{f.name}: {bad}")

    def test_contract_path(self):
        for f in self.files():
            self.assertIn(CONTRACT, f.read_text(), f.name)

    def test_no_skill_md(self):
        self.assertEqual(list(A.rglob("SKILL.md")), [])


if __name__ == "__main__":
    unittest.main()
