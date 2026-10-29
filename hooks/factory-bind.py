#!/usr/bin/env python3
# Bind a worktree to a job: factory-bind.py <worktree> <slug> | --unbind <worktree>
# Writes the index (~/.config/factory/bindings.json) and <worktree>/.factory-job, and
# lists .factory-job in the repo's info/exclude. Run by the human or the orchestrator.
import json, os, pathlib, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_common as fc


def save(idx):
    p = fc.index_path()
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".bindings.")
    with os.fdopen(fd, "w") as fh:
        json.dump(idx, fh, indent=1, sort_keys=True)
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)


def exclude(wt):
    r = subprocess.run(["git", "-C", str(wt), "rev-parse", "--git-path", "info/exclude"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"warning: {wt} is not a git repo; .factory-job not added to info/exclude", file=sys.stderr)
        return
    ex = pathlib.Path(r.stdout.strip())
    ex = ex if ex.is_absolute() else wt / ex
    ex.parent.mkdir(parents=True, exist_ok=True)
    cur = ex.read_text().splitlines() if ex.exists() else []
    if ".factory-job" not in cur:
        with open(ex, "a") as fh:
            fh.write(("\n" if cur and not ex.read_text().endswith("\n") else "") + ".factory-job\n")


def main(argv):
    if len(argv) == 3 and argv[1] == "--unbind":
        wt = pathlib.Path(argv[2]).resolve()
        idx = fc.load_index() or {}
        idx.pop(str(wt), None)
        save(idx)
        (wt / ".factory-job").unlink(missing_ok=True)
        print(f"unbound {wt}")
        return 0
    if len(argv) == 3 and not argv[1].startswith("-"):
        wt, slug = pathlib.Path(argv[1]).resolve(), argv[2]
        if not wt.is_dir():
            print(f"not a directory: {wt}", file=sys.stderr)
            return 1
        if not fc.SLUG.fullmatch(slug):
            print("slug must match ^[a-z0-9][a-z0-9-]{0,63}$", file=sys.stderr)
            return 1
        idx = fc.load_index()
        if idx is None:
            print("binding index is unreadable; fix or remove it first", file=sys.stderr)
            return 1
        idx[str(wt)] = slug
        save(idx)
        (wt / ".factory-job").write_text(slug + "\n")
        exclude(wt)
        print(f"bound {wt} -> {slug}")
        return 0
    print("usage: factory-bind.py <worktree> <slug> | --unbind <worktree>", file=sys.stderr)
    return 2


sys.exit(main(sys.argv))
