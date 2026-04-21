#!/usr/bin/env python3
"""export — write a shareable JSON from the current signature.json.

Usage:
    python3 skills/export/export.py [--out PATH] [--team-id TEAM_ID]

The exported file is identical to signature.json except:
  - origin is always "self" (you are the author of this export)
  - team_id is stamped if --team-id is provided
  - exported_ts is added so recipients know when the share happened
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Export signature.json as a shareable file.")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--signature", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--team-id", default=None, help="Optional team identifier to stamp on the export")
    args = ap.parse_args()

    repo = args.repo.resolve()
    sig_path = args.signature or (repo / "signature.json")

    if not sig_path.exists():
        print(f"error: {sig_path} not found — run capture + extract first", file=sys.stderr)
        return 1

    sig = json.loads(sig_path.read_text(encoding="utf-8"))

    # Stamp export metadata
    sig["origin"] = "self"
    sig["exported_ts"] = datetime.now(timezone.utc).isoformat()
    if args.team_id:
        sig["team_id"] = args.team_id

    out_path = args.out or (repo / "signature_export.json")
    out_path.write_text(json.dumps(sig, indent=2), encoding="utf-8")
    print(f"exported → {out_path}")
    if args.team_id:
        print(f"team_id:  {args.team_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
