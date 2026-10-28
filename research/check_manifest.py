"""Verify byte-level hashes of fixed research source records, without rewriting them."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--included-only", action="store_true",
                        help="check only files intended for the public source candidate")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "research/manifest.json").read_text(encoding="utf-8"))
    failed = []
    checked = 0
    for item in manifest["fixed_source_files"]:
        if args.included_only and not item["included_in_public_source_candidate"]:
            continue
        path = ROOT / item["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        checked += 1
        if actual != item["sha256"]:
            failed.append(item["path"])
    print(json.dumps({"status": "pass" if not failed else "fail", "checked": checked,
                      "failed_paths": failed}, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
