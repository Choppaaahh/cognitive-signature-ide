#!/usr/bin/env python3
"""import_sig — load an imported signature JSON and make it active.

Usage:
    python3 skills/import_sig/import_sig.py <path-to-signature.json>

Sets origin to "imported" and writes to signature.json so inject will
use the imported style. The Historian will flag this in drift reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_and_validate(path: Path, schema_path: Path) -> dict:
    sig = json.loads(path.read_text(encoding="utf-8"))
    try:
        import jsonschema
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        # Remove origin from required for import validation (we override it)
        schema_copy = dict(schema)
        schema_copy["required"] = [r for r in schema["required"] if r != "origin"]
        validator = jsonschema.Draft7Validator(schema_copy)
        errors = [f"{'.'.join(str(p) for p in e.path)}: {e.message}" for e in validator.iter_errors(sig)]
        if errors:
            for e in errors:
                print(f"  warning: {e}", file=sys.stderr)
    except ImportError:
        pass
    return sig


def main() -> int:
    ap = argparse.ArgumentParser(description="Load an imported signature JSON as the active signature.")
    ap.add_argument("source", type=Path, help="Path to the signature file to import")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--schema", type=Path, default=None)
    args = ap.parse_args()

    repo = args.repo.resolve()
    schema_path = args.schema or (repo / "skills" / "extract" / "signature_schema.json")
    out_path = repo / "signature.json"
    history_path = repo / ".signature-cache" / "signature_history.jsonl"

    if not args.source.exists():
        print(f"error: {args.source} not found", file=sys.stderr)
        return 1

    sig = load_and_validate(args.source, schema_path)

    # Override origin and stamp import time
    sig["origin"] = "imported"
    sig["imported_ts"] = datetime.now(timezone.utc).isoformat()

    out_path.write_text(json.dumps(sig, indent=2), encoding="utf-8")
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(sig) + "\n")

    print(f"imported  → {out_path}")
    print(f"origin:     imported")
    team_id = sig.get("team_id", "")
    if team_id:
        print(f"team_id:    {team_id}")
    print("appended  → signature_history.jsonl")
    print("note: Historian will classify this as an EXPECTED change (origin=imported)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
