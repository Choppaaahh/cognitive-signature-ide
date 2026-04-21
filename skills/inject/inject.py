#!/usr/bin/env python3
"""inject — render signature.json as a context prefix for Claude.

Designed to be called by hooks (SessionStart, UserPromptSubmit) or by the
toggle skill in 'diff' mode. Respects the on/off state written by toggle.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PREFIX_TEMPLATE = """[User's Cognitive Signature — v{version}, generated {generated_ts}]

The user's coding signature across {sample_count} samples ({languages}):

{dimensions_rendered}

Match this signature when generating code suggestions. Do not default to generic
conventions if they conflict with the user's established patterns."""


def render_dimensions(dimensions: dict) -> str:
    lines = []
    for name, value in dimensions.items():
        if not isinstance(value, dict):
            continue
        conf = value.get("confidence", "?")
        hint = (
            value.get("primary_style")
            or value.get("preference")
            or value.get("try_except_style")
            or value.get("nesting_depth")
            or value.get("grouping")
            or value.get("docstring_presence")
            or "?"
        )
        evidence = value.get("evidence", "")
        lines.append(f"  - {name}: {hint} (confidence {conf})")
        if evidence:
            lines.append(f"      evidence: {evidence}")
    return "\n".join(lines)


def render_signature_prefix(signature_path: Path) -> str | None:
    if not signature_path.exists():
        return None
    sig = json.loads(signature_path.read_text(encoding="utf-8"))
    dims = sig.get("dimensions", {})
    if not dims:
        return None
    return PREFIX_TEMPLATE.format(
        version=sig.get("version", "unknown"),
        generated_ts=sig.get("generated_ts", "unknown"),
        sample_count=sig.get("sample_count", "?"),
        languages=", ".join(sig.get("languages", [])) or "?",
        dimensions_rendered=render_dimensions(dims),
    )


def is_enabled(state_path: Path) -> bool:
    if not state_path.exists():
        return True
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    return bool(state.get("enabled", True))


def main() -> int:
    ap = argparse.ArgumentParser(description="Render signature.json as context prefix.")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--signature", type=Path, default=None)
    ap.add_argument("--state", type=Path, default=None)
    ap.add_argument("--force", action="store_true", help="Emit prefix even when toggle is OFF")
    args = ap.parse_args()

    repo = args.repo.resolve()
    signature_path = args.signature or (repo / "signature.json")
    state_path = args.state or (repo / ".signature-cache" / "state.json")

    if not args.force and not is_enabled(state_path):
        print("# signature injection is OFF — run /cogsig on to enable", file=sys.stderr)
        return 0

    prefix = render_signature_prefix(signature_path)
    if prefix is None:
        print(f"# no signature found at {signature_path} — run capture + extract first", file=sys.stderr)
        return 0

    print(prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
