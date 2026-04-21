#!/usr/bin/env python3
"""export — write a shareable JSON from the current active signature.

Usage:
    python3 skills/export/export.py [--out PATH] [--team-id TEAM_ID] [--scope-name NAME]

The exported file is identical to signature.<scope>.json except:
  - origin is always "self" (you are the author of this export)
  - team_id is stamped if --team-id is provided
  - exported_ts is added so recipients know when the share happened

Resolves the active scope from .signature-cache/state.json unless --scope-name
overrides. Default scope maps to signature.json; named scopes to
signature.<scope>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def active_scope(repo: Path) -> str:
    state_path = repo / ".signature-cache" / "state.json"
    if not state_path.exists():
        return "default"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "default"
    return state.get("active_scope", "default")


def signature_path_for_scope(repo: Path, scope_name: str) -> Path:
    filename = "signature.json" if scope_name == "default" else f"signature.{scope_name}.json"
    return repo / filename


def main() -> int:
    ap = argparse.ArgumentParser(description="Export the active signature as a shareable file.")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--scope-name", default=None, help="Override active scope from state")
    ap.add_argument("--signature", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--team-id", default=None, help="Optional team identifier to stamp on the export")
    args = ap.parse_args()

    repo = args.repo.resolve()
    scope = args.scope_name or active_scope(repo)
    sig_path = args.signature or signature_path_for_scope(repo, scope)

    if not sig_path.exists():
        print(f"error: {sig_path} not found — run capture + extract for scope '{scope}' first", file=sys.stderr)
        return 1

    sig = json.loads(sig_path.read_text(encoding="utf-8"))

    sig["origin"] = "self"
    sig["exported_ts"] = datetime.now(timezone.utc).isoformat()
    if args.team_id:
        sig["team_id"] = args.team_id

    if args.out:
        out_path = args.out
    else:
        suffix = f"-{args.team_id}" if args.team_id else ""
        scope_tag = "" if scope == "default" else f".{scope}"
        out_path = repo / f"signature_export{scope_tag}{suffix}.json"

    out_path.write_text(json.dumps(sig, indent=2), encoding="utf-8")
    scope_hint = "" if scope == "default" else f" [scope: {scope}]"
    print(f"exported → {out_path}{scope_hint}")
    if args.team_id:
        print(f"team_id:  {args.team_id}")
    print("share this file. Recipient loads with: python3 skills/import_sig/import_sig.py <path>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
