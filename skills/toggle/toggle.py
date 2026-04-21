#!/usr/bin/env python3
"""toggle — /cogsig slash command handler.

Subcommands:
    on       — enable injection (default)
    off      — disable injection
    status   — show current state + signature metadata
    diff     — render three-way comparison of next response (Step 5)
    capture  — route to capture skill (shorthand)
    extract  — route to extract skill (shorthand)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def state_path(repo: Path) -> Path:
    return repo / ".signature-cache" / "state.json"


def load_state(repo: Path) -> dict:
    path = state_path(repo)
    if not path.exists():
        return {"enabled": True}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"enabled": True}


def save_state(repo: Path, state: dict) -> None:
    path = state_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def cmd_on(repo: Path) -> int:
    state = load_state(repo)
    state["enabled"] = True
    state["toggled_at"] = datetime.now(timezone.utc).isoformat()
    save_state(repo, state)
    print("cogsig: injection ENABLED")
    return 0


def cmd_off(repo: Path) -> int:
    state = load_state(repo)
    state["enabled"] = False
    state["toggled_at"] = datetime.now(timezone.utc).isoformat()
    save_state(repo, state)
    print("cogsig: injection DISABLED")
    return 0


def cmd_status(repo: Path) -> int:
    state = load_state(repo)
    sig_path = repo / "signature.json"
    enabled = "ON" if state.get("enabled", True) else "OFF"
    if not sig_path.exists():
        print(f"cogsig: {enabled} (no signature.json yet — run /cogsig capture + /cogsig extract)")
        return 0
    try:
        sig = json.loads(sig_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"cogsig: {enabled} (signature.json exists but is unreadable)")
        return 1
    print(f"cogsig: {enabled}")
    print(f"  signature v{sig.get('version', '?')} generated {sig.get('generated_ts', '?')}")
    print(f"  domain: {sig.get('domain', '?')} | samples: {sig.get('sample_count', '?')} | languages: {', '.join(sig.get('languages', []))}")
    return 0


def cmd_diff(repo: Path) -> int:
    print("cogsig: diff mode not yet implemented (Step 5 target).")
    print("  planned: render next response under three conditions — baseline / placebo / real signature")
    return 0


def cmd_route(repo: Path, skill: str) -> int:
    script_map = {
        "capture": repo / "skills" / "capture" / "capture.py",
        "extract": repo / "skills" / "extract" / "extract.py",
    }
    script = script_map.get(skill)
    if not script or not script.exists():
        print(f"cogsig: skill '{skill}' not found at {script}", file=sys.stderr)
        return 1
    result = subprocess.run([sys.executable, str(script), "--repo", str(repo)], check=False)
    return result.returncode


HANDLERS = {
    "on": cmd_on,
    "off": cmd_off,
    "status": cmd_status,
    "diff": cmd_diff,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="/cogsig slash command handler")
    ap.add_argument("command", choices=list(HANDLERS) + ["capture", "extract"])
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    args = ap.parse_args()

    repo = args.repo.resolve()
    if args.command in HANDLERS:
        return HANDLERS[args.command](repo)
    return cmd_route(repo, args.command)


if __name__ == "__main__":
    raise SystemExit(main())
