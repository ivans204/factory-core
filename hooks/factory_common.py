# Shared helpers for the receipt recorder and the stop gate.
import hashlib, hmac, json, os, pathlib, re

SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


class Job(str):
    """Job slug. .tampered is True when the binding index and the .factory-job file disagree."""
    tampered = False


def index_path():
    return pathlib.Path.home() / ".config/factory/bindings.json"


def load_index():
    """{abs worktree root: slug}. {} if there is no index; None if it exists but is unreadable."""
    p = index_path()
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text())
        if isinstance(d, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in d.items()):
            return d
    except (OSError, ValueError):
        pass
    return None


def _marked(slug, tampered):
    j = Job(slug)
    j.tampered = tampered
    return j


def job_of(cwd):
    """Bound job for cwd. The index (~/.config/factory/bindings.json) is authoritative; the
    .factory-job file must agree. Without an index entry, fall back to the nearest .factory-job."""
    if not isinstance(cwd, str):
        return None
    p = pathlib.Path(cwd).resolve()
    idx = load_index()
    if idx is None:
        return _marked("tampered-index", True)
    for d in [p, *p.parents]:
        slug = idx.get(str(d))
        if slug is not None:
            if not SLUG.fullmatch(slug):
                return _marked("tampered-index", True)
            try:
                f = d / ".factory-job"
                ok = f.is_file() and f.read_text().strip() == slug
            except Exception:
                ok = False                       # unreadable or undecodable: treat as tampered
            return _marked(slug, not ok)
    try:
        for d in [p, *p.parents]:
            f = d / ".factory-job"
            if f.is_file():
                slug = f.read_text().strip()
                return _marked(slug, False) if SLUG.fullmatch(slug) else None
    except (OSError, ValueError):
        return None
    return None


def safe_name(v, default):
    s = re.sub(r"[^A-Za-z0-9_.:-]", "_", str(v)) if v else default
    return s[:100] or default


def agent_run(e):
    return safe_name(e.get("agent_type"), "relay"), safe_name(e.get("agent_id"), "main")


def receipts_dir(job):
    return pathlib.Path.home() / ".brain/job" / job / "relay/receipts"


def log_path(job, agent, run):
    d = receipts_dir(job)
    p = d / f"{agent}-{run}.jsonl"
    if p.resolve().parent != d.resolve():
        raise ValueError("receipt path escapes receipts dir")
    return p


def key_path():
    return pathlib.Path.home() / ".config/factory/receipt.key"


def load_key(create=False):
    p = key_path()
    if p.is_file():
        return p.read_bytes()
    if not create:
        return None
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(os.urandom(32))
    except FileExistsError:
        pass
    return p.read_bytes()


def mac_of(key, rec):
    body = {k: v for k, v in rec.items() if k != "mac"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hmac.new(key, canon.encode(), hashlib.sha256).hexdigest()
