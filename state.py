"""Tiny persistent counter so every run shifts the content + design rotation,
meaning two runs never start on the same post/design (content stays fresh)."""

import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "state.json")


def _load():
    try:
        with open(_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def get_offset():
    return int(_load().get("offset", 0))


def bump_offset(by=1):
    d = _load()
    d["offset"] = int(d.get("offset", 0)) + int(by)
    try:
        with open(_PATH, "w") as f:
            json.dump(d, f)
    except Exception:
        pass
    return d["offset"]


# --- cross-run "used content" ledger -------------------------------------
# Remembers headlines already published so a NEW week never repeats an OLD one.
# generator.py seeds its avoid-list from here and appends fresh headlines after
# each run. Capped so the file never grows without bound.
_USED_CAP = 600


def get_used():
    d = _load()
    u = d.get("used_headlines", [])
    return u if isinstance(u, list) else []


def add_used(headlines):
    """Append headlines to the persistent ledger (delta only, de-duped, capped)."""
    if not headlines:
        return
    d = _load()
    seen = set(d.get("used_headlines", []))
    cur = list(d.get("used_headlines", []))
    for h in headlines:
        h = (h or "").strip()
        if h and h not in seen:
            seen.add(h)
            cur.append(h)
    d["used_headlines"] = cur[-_USED_CAP:]
    try:
        with open(_PATH, "w") as f:
            json.dump(d, f)
    except Exception:
        pass
    return len(d["used_headlines"])
