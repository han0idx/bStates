#!/usr/bin/env python3
"""Generate stateinfo.json: a map of tracked files to their SHA-256 hash.

The hash is uppercase hexadecimal. Keys are sorted for deterministic output.
Run from the repository root. See .github/workflows/update-stateinfo.yml.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import sys

# Output file (relative to repo root).
STATE_FILE = "stateinfo.json"

# Directories never walked into.
EXCLUDE_DIRS = {".git", ".github", "scripts", ".vscode", ".idea", "node_modules"}

# Files never hashed (the state file itself, VCS/CI metadata, etc.).
EXCLUDE_FILES = {STATE_FILE, ".gitignore", ".gitattributes"}

# Only files matching one of these glob patterns are tracked.
# Override by setting STATEINFO_PATTERNS (space- or comma-separated globs).
# Default "*" tracks every file not otherwise excluded.
DEFAULT_PATTERNS = ["*"]


def get_patterns():
    raw = os.environ.get("STATEINFO_PATTERNS", "").strip()
    if not raw:
        return DEFAULT_PATTERNS
    parts = [p.strip() for p in raw.replace(",", " ").split()]
    return [p for p in parts if p] or DEFAULT_PATTERNS


def matches(name, patterns):
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def sha256_upper(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def build_state(root, patterns):
    state = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for filename in filenames:
            if filename in EXCLUDE_FILES:
                continue
            if not matches(filename, patterns):
                continue
            abspath = os.path.join(dirpath, filename)
            relpath = os.path.relpath(abspath, root).replace(os.sep, "/")
            state[relpath] = sha256_upper(abspath)
    return state


def load_existing(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def serialize(state):
    # Sorted keys => deterministic ordering; trailing newline for clean diffs.
    return json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main():
    root = os.getcwd()
    patterns = get_patterns()
    new_state = build_state(root, patterns)
    new_text = serialize(new_state)

    out_path = os.path.join(root, STATE_FILE)
    existing = load_existing(out_path)
    if existing == new_state and os.path.exists(out_path):
        # Compare serialized form too, so formatting drift is corrected.
        with open(out_path, "r", encoding="utf-8") as fh:
            if fh.read() == new_text:
                print("stateinfo.json already up to date; no changes.")
                return 0

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(new_text)
    print("stateinfo.json updated with %d entr%s." % (len(new_state), "y" if len(new_state) == 1 else "ies"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
