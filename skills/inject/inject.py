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


_META_KEYS = {"confidence", "evidence", "evidence_list", "instance_count"}


def _summarize_value(value: dict) -> str:
    """Domain-agnostic hint summary — join non-meta scalar/list fields as 'key=val'."""
    parts = []
    for k, v in value.items():
        if k in _META_KEYS:
            continue
        if isinstance(v, str) and v:
            parts.append(f"{k}={v}")
        elif isinstance(v, (int, float, bool)):
            parts.append(f"{k}={v}")
        elif isinstance(v, list) and v:
            sample = ", ".join(str(x) for x in v[:3])
            more = f" +{len(v) - 3} more" if len(v) > 3 else ""
            parts.append(f"{k}=[{sample}{more}]")
    return "; ".join(parts) if parts else "?"


def render_dimensions(dimensions: dict) -> str:
    lines = []
    for name, value in dimensions.items():
        if not isinstance(value, dict):
            # Operational dims have list-valued entries (e.g. recurring_failure_patterns: [...])
            if isinstance(value, list) and value:
                lines.append(f"  - {name}: [{len(value)} entries]")
                for i, item in enumerate(value[:3]):
                    if isinstance(item, dict):
                        label = item.get("situation") or item.get("pattern") or item.get("tool") or item.get("term") or str(item)[:60]
                        count = item.get("instance_count")
                        suffix = f" ({count}x)" if count else ""
                        lines.append(f"      · {str(label)[:80]}{suffix}")
                if len(value) > 3:
                    lines.append(f"      ...and {len(value) - 3} more")
            continue
        conf = value.get("confidence", "?")
        hint = _summarize_value(value)
        evidence = value.get("evidence", "")
        lines.append(f"  - {name}: {hint} (confidence {conf})")
        if evidence:
            lines.append(f"      evidence: {evidence}")
    return "\n".join(lines)


def render_signature_prefix(signature_path: Path) -> str | None:
    if not signature_path.exists():
        return None
    try:
        sig = json.loads(signature_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"cogsig inject: skipping malformed signature at {signature_path.name}: {e}", file=sys.stderr)
        return None
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


def render_pending_surface(pending_path: Path, preset: str) -> str | None:
    """Render pending-pattern review section for injection into Claude's context prefix.

    In `normie` preset, returns None (silent auto-promotion — not yet wired; user still runs
    `/cogsig approve` manually for now). In `power/team/enterprise` preset, returns a section
    instructing Claude to surface the pending patterns naturally in its next response.
    """
    if preset == "normie":
        return None
    if not pending_path.exists():
        return None
    try:
        queue = json.loads(pending_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    patterns = queue.get("patterns", [])
    if not patterns:
        return None

    lines = [
        "",
        "---",
        f"[PENDING PATTERN REVIEWS — {len(patterns)} pattern(s) hit n=2 threshold since last approved snapshot]",
        "",
    ]
    for p in patterns:
        item = p.get("item", {})
        dim = p.get("dim", "?")
        pid = p.get("id", "?")
        count = item.get("instance_count", "?")
        label = (
            item.get("situation")
            or item.get("pattern")
            or item.get("tool")
            or item.get("term")
            or "?"
        )
        evidence = item.get("evidence_list", [])
        lines.append(f"[{pid}] {dim} — \"{str(label)[:120]}\" ({count}x instances)")
        for ev in evidence[:2]:
            lines.append(f"    ▸ {str(ev)[:120]}")
        if len(evidence) > 2:
            lines.append(f"    ▸ (+{len(evidence) - 2} more)")
        lines.append("")

    lines.append(
        "Instructions: when your response naturally completes, surface these pending patterns to the "
        "user in YOUR VOICE (match their compression ratio + idiom tells from signature above). "
        "Short natural ask: 'btw I noticed [pattern] [N]x this session — promote? (id [N])'. "
        "The user will reply with /cogsig approve <id[,id...]> or /cogsig reject <id> or /cogsig edit <id> <text>. "
        "Don't repeat items from previous turns — check if you've already mentioned them."
    )
    return "\n".join(lines)


def load_preset(state: dict) -> str:
    return state.get("preset", "power")


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"enabled": True, "active_scope": "default"}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"enabled": True, "active_scope": "default"}
    state.setdefault("enabled", True)
    state.setdefault("active_scope", "default")
    return state


def signature_path_for_scope(repo: Path, scope_name: str) -> Path:
    filename = "signature.json" if scope_name == "default" else f"signature.{scope_name}.json"
    return repo / filename


def main() -> int:
    ap = argparse.ArgumentParser(description="Render signature.json as context prefix.")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--signature", type=Path, default=None)
    ap.add_argument("--state", type=Path, default=None)
    ap.add_argument("--scope-name", default=None, help="Override active scope from state")
    ap.add_argument("--force", action="store_true", help="Emit prefix even when toggle is OFF")
    args = ap.parse_args()

    repo = args.repo.resolve()
    state_path = args.state or (repo / ".signature-cache" / "state.json")
    state = load_state(state_path)
    scope = args.scope_name or state["active_scope"]
    signature_path = args.signature or signature_path_for_scope(repo, scope)

    if not args.force and not state["enabled"]:
        print("# signature injection is OFF — run /cogsig on to enable", file=sys.stderr)
        return 0

    pending_filename = "pending_patterns.json" if scope == "default" else f"pending_patterns.{scope}.json"
    pending_file = repo / ".signature-cache" / pending_filename
    preset = load_preset(state)

    prefix = render_signature_prefix(signature_path)
    if prefix is None:
        if pending_file.exists():
            print(f"# no signature found at {signature_path}, but pending_patterns.json has entries — "
                  f"signature extraction must run before pending patterns can surface", file=sys.stderr)
        else:
            print(f"# no signature found at {signature_path} — run capture + extract first", file=sys.stderr)
        return 0

    pending_section = render_pending_surface(pending_file, preset)
    if pending_section:
        prefix = prefix + "\n" + pending_section

    print(prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
