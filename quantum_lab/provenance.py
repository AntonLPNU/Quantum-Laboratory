"""Deterministic source provenance for reproducible experiment records."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def code_provenance(root: str | Path = ".") -> dict:
    """Identify HEAD and hash the complete working copies of runtime/reference Python.

    The content hash includes modified and untracked source files and therefore
    remains informative when an experiment is recorded before a commit exists.
    Generated ``results/`` and local virtual environments are excluded.
    """
    if getattr(sys, "frozen", False):
        manifest = Path(sys._MEIPASS) / "desktop_provenance.json"
        if not manifest.is_file():
            raise RuntimeError("packaged scientific source provenance is missing")
        return json.loads(manifest.read_text(encoding="utf-8"))
    base = Path(root).resolve()
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=base, check=True,
                              capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=base, check=True,
                            capture_output=True, text=True).stdout
    paths = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                           cwd=base, check=True, capture_output=True, text=True).stdout.splitlines()
    selected = sorted(path for path in set(paths)
                      if path.startswith(("quantum_lab/", "scripts/")) and path.endswith(".py"))
    digest = hashlib.sha256()
    for relative in selected:
        path = base / relative
        if not path.is_file():
            continue
        content = path.read_bytes()
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return {"git_revision": revision, "working_tree_dirty": bool(status.strip()),
            "python_source_sha256": digest.hexdigest(), "hashed_python_files": selected}
