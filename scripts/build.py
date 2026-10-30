#!/usr/bin/env python3
"""Build install.sh from kit/ and refresh the kit blocks in cookbook/kuharica.html.

    python3 scripts/build.py           # write both
    python3 scripts/build.py --check   # exit 1 if either is out of date with kit/

kit/ is the source of truth. The page's prose is edited in cookbook/kuharica.html
by hand; every <script type="text/plain" data-path="..."> block in it is generated.
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
KIT = ROOT / "kit"
INSTALL = ROOT / "install.sh"
PAGE = ROOT / "cookbook" / "kuharica.html"

HEAD = '''#!/bin/bash
# factory-core installer. Writes the software factory core to $CORE and links its
# 17 agents and the /relay skill into ~/.claude. Never overwrites an agent or skill
# that is not its own unless FORCE=1, which first moves the old one to ~/.claude/factory-backups/.
#   DECIDE=fable bash install.sh      # pick model aliases per tier
# A rerun updates the core in place and keeps the tiers chosen last time.
set -euo pipefail
CORE="${CORE:-$HOME/.claude/factory-core}"
saved() { { sed -n "s/^$1=//p" "$CORE/.factory-core" 2>/dev/null || true; } | tail -1; }
DECIDE="${DECIDE:-$(saved DECIDE)}"; DECIDE="${DECIDE:-opus}"    # arbiter, planner, challenger, retro (fable if your plan has it)
BUILD="${BUILD:-$(saved BUILD)}";    BUILD="${BUILD:-opus}"      # builder, diagnostician, designer, reviewer-correctness
READ="${READ:-$(saved READ)}";       READ="${READ:-sonnet}"      # scout, verifier, ds-guard, shipwright, validator, reviewers
CLERK="${CLERK:-$(saved CLERK)}";    CLERK="${CLERK:-haiku}"     # scribe
FORCE="${FORCE:-0}"
BACKUP="$HOME/.claude/factory-backups/$(date +%Y%m%d%H%M%S)"

for t in git jq python3; do command -v "$t" >/dev/null || { echo "missing: $t" >&2; exit 1; }; done
# An update must not overwrite changes made in the core since the last install
# (a retro's commit, a hand edit): fold them into the kit you install from first.
if [ -d "$CORE/.git" ] && [ "$FORCE" != 1 ]; then
  if [ -n "$(git -C "$CORE" status --porcelain)" ] || [ "$(git -C "$CORE" log -1 --format=%s)" != "factory-core: install or update" ]; then
    echo "$CORE has changes since the last install (git -C $CORE log). Fold them into this kit, or rerun with FORCE=1 to overwrite them." >&2; exit 1
  fi
fi
if [ -d "$CORE" ] && [ ! -f "$CORE/.factory-core" ] && [ -n "$(ls -A "$CORE")" ] && [ "$FORCE" != 1 ]; then
  echo "$CORE exists and is not a factory-core install. Rerun with FORCE=1 to write into it." >&2; exit 1
fi
mkdir -p "$CORE"
printf 'DECIDE=%s\\nBUILD=%s\\nREAD=%s\\nCLERK=%s\\n' "$DECIDE" "$BUILD" "$READ" "$CLERK" > "$CORE/.factory-core"
w() { mkdir -p "$(dirname "$CORE/$1")"; cat > "$CORE/$1"; }
'''

TAIL = '''
for f in "$CORE"/agents/*.md; do
  sed -e "s/{{decide}}/$DECIDE/" -e "s/{{build}}/$BUILD/" -e "s/{{read}}/$READ/" -e "s/{{clerk}}/$CLERK/" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
chmod +x "$CORE"/hooks/*

link() {
  local src="$1" dst="$2"
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    # Backups go outside agents/ and skills/: a skill folder left beside the
    # new one would load as a second skill of the same name.
    if [ "$FORCE" = 1 ]; then mkdir -p "$BACKUP" && mv "$dst" "$BACKUP/" && echo "backed up $dst to $BACKUP/"
    else echo "skipped $dst: it exists and is not a factory link (FORCE=1 backs it up and links)"; return; fi
  fi
  ln -sfn "$src" "$dst"
}
mkdir -p "$HOME/.claude/agents" "$HOME/.claude/skills"
for f in "$CORE"/agents/*.md; do link "$f" "$HOME/.claude/agents/$(basename "$f")"; done
link "$CORE/skills/relay" "$HOME/.claude/skills/relay"

if [ ! -d "$CORE/.git" ]; then git -C "$CORE" init -q; fi
git -C "$CORE" add -A
git -C "$CORE" diff --cached --quiet || git -C "$CORE" commit -qm "factory-core: install or update"

echo
echo "factory-core is in $CORE (models: decide=$DECIDE build=$BUILD read=$READ clerk=$CLERK)."
echo "Next: merge $CORE/settings-hooks.json into ~/.claude/settings.json, restart Claude Code,"
echo "then follow $CORE/README.md: make a pack for your project, then /relay."
'''

BLOCK = re.compile(r'<script type="text/plain" data-path="[^"]+">\n.*?</script>\n', re.S)


def kit_files():
    return [(p.relative_to(KIT).as_posix(), p.read_text()) for p in sorted(KIT.rglob("*")) if p.is_file()]


def build_install(files):
    parts = [HEAD]
    for rel, body in files:
        assert "\nFACTORY_EOF\n" not in "\n" + body + "\n", rel
        parts.append(f"\nw {rel} <<'FACTORY_EOF'\n{body.rstrip(chr(10))}\nFACTORY_EOF\n")
    parts.append(TAIL)
    return "".join(parts)


def build_page(files, install):
    html = PAGE.read_text()
    first = BLOCK.search(html)
    assert first, "no data-path blocks in the page"
    blocks = []
    for rel, body in files + [("install.sh", install)]:
        assert "</script" not in body.lower(), rel
        blocks.append(f'<script type="text/plain" data-path="{rel}">\n{body}</script>\n')
    rest = BLOCK.sub("", html[first.start():])
    return html[:first.start()] + "".join(blocks) + rest


def main():
    files = kit_files()
    install = build_install(files)
    page = build_page(files, install)
    stale = [p for p, text in ((INSTALL, install), (PAGE, page)) if not p.exists() or p.read_text() != text]
    if "--check" in sys.argv:
        for p in stale:
            print(f"out of date with kit/: {p.relative_to(ROOT)} (run python3 scripts/build.py)")
        sys.exit(1 if stale else 0)
    INSTALL.write_text(install)
    PAGE.write_text(page)
    for p in stale:
        print(f"wrote {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
