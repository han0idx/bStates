#!/usr/bin/env python3
"""Maintain stateinfo.json and normalize numbered chunk files.

Rules:
- Files matching <base>.NNN where NNN is exactly 3 digits (.000-.999) are not
  kept in the repo. For each <base>, the chunk most recently changed in the
  triggering commit wins; it is renamed to <base>_ggpo.fs and the rest are
  deleted. No content transformation. An existing <base>_ggpo.fs is replaced
  only when the new content hash differs.
- *.fs files are tracked in stateinfo.json (filename -> SHA-256, uppercase).
- Everything else is ignored.

The list of files changed by the push is passed via the CHANGED_FILES env var
(newline-separated, oldest-to-newest change order). Used only to pick the
"most recently changed" chunk per base.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

STATE_FILE = "stateinfo.json"
EXCLUDE_DIRS = {".git", ".github", "scripts", ".vscode", ".idea", "node_modules"}
CHUNK_RE = re.compile(r"^(?P<base>.+)\.(?P<num>\d{3})$")


def sha256_upper(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            abspath = os.path.join(dirpath, name)
            rel = os.path.relpath(abspath, root).replace(os.sep, "/")
            yield rel, abspath


def changed_order():
    raw = os.environ.get("CHANGED_FILES", "")
    order = {}
    for i, line in enumerate(raw.splitlines()):
        p = line.strip().replace(os.sep, "/")
        if p:
            order[p] = i  # larger index == changed more recently
    return order


def normalize_chunks(root, order):
    """Pick winning chunk per base, rename to <base>_ggpo.fs, delete chunks."""
    groups = {}
    for rel, abspath in list(iter_files(root)):
        m = CHUNK_RE.match(os.path.basename(rel))
        if not m:
            continue
        d = os.path.dirname(rel)
        base = (d + "/" + m.group("base")) if d else m.group("base")
        groups.setdefault(base, []).append((rel, abspath))

    for base, members in groups.items():
        # Winner: most recently changed in the push; fall back to highest suffix.
        def rank(item):
            rel = item[0]
            return (order.get(rel, -1), rel)
        winner_rel, winner_abs = max(members, key=rank)
        target_rel = base + "_ggpo.fs"
        target_abs = os.path.join(root, target_rel.replace("/", os.sep))

        new_hash = sha256_upper(winner_abs)
        old_hash = sha256_upper(target_abs) if os.path.exists(target_abs) else None
        if old_hash != new_hash:
            with open(winner_abs, "rb") as src, open(target_abs, "wb") as dst:
                dst.write(src.read())
        # Remove all chunk files (the raw .NNN must not be hosted).
        for rel, abspath in members:
            if os.path.exists(abspath):
                os.remove(abspath)


def build_state(root):
    state = {}
    for rel, abspath in iter_files(root):
        if rel == STATE_FILE:
            continue
        if rel.endswith(".fs"):
            state[rel] = sha256_upper(abspath)
    return state


def serialize(state):
    return json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main():
    root = os.getcwd()
    normalize_chunks(root, changed_order())
    new_text = serialize(build_state(root))
    out_path = os.path.join(root, STATE_FILE)
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as fh:
            if fh.read() == new_text:
                print("stateinfo.json already up to date.")
                return 0
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(new_text)
    print("stateinfo.json written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
