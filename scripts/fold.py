#!/usr/bin/env python3
"""Fold edits made in the installed core (a retro's commit, a hand edit) back into kit/.

    python3 scripts/fold.py            # CORE defaults to ~/.claude/factory-core

An agent's model line keeps the kit's {{tier}} placeholder. Afterwards: review
`git diff kit/`, commit, `python3 scripts/build.py`, then `FORCE=1 bash install.sh`
(FORCE because the core's last commit is no longer the installer's).
"""
import os, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
KIT = ROOT / "kit"
CORE = pathlib.Path(os.environ.get("CORE", "~/.claude/factory-core")).expanduser()
MODEL = re.compile(r"^model: .*$", re.M)

changed = []
for src in sorted(CORE.rglob("*")):
    rel = src.relative_to(CORE)
    if not src.is_file() or rel.parts[0] == ".git" or rel.name == ".factory-core":
        continue
    dst = KIT / rel
    text = src.read_text()
    if rel.parts[0] == "agents" and dst.exists():
        placeholder = MODEL.search(dst.read_text())
        if placeholder:
            text = MODEL.sub(lambda _: placeholder.group(0), text, count=1)
    if not dst.exists() or dst.read_text() != text:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text)
        changed.append(rel.as_posix())

missing = sorted(p.relative_to(KIT).as_posix() for p in KIT.rglob("*")
                 if p.is_file() and not (CORE / p.relative_to(KIT)).exists())
print("\n".join(f"folded {c}" for c in changed) or "nothing to fold")
for m in missing:
    print(f"in kit/ but not in {CORE}: {m} (deleted there? remove it here by hand)")
