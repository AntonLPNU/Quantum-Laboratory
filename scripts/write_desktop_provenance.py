"""Capture the exact scientific source state included in a desktop package."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quantum_lab.provenance import code_provenance


if __name__ == "__main__":
    destination = Path(sys.argv[1])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(code_provenance(), ensure_ascii=False, indent=2), encoding="utf-8")
