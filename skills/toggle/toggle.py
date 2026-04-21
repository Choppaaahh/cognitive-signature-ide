#!/usr/bin/env python3
"""toggle — /cogsig slash command handler.

Subcommands:
    on                              — enable injection (default)
    off                             — disable injection
    status                          — show state + active-scope signature metadata
    diff                            — three-way comparison of next response (Step 5)
    scope <name>                    — switch active scope (default / work / personal / ...)
    scope list                      — list all locally-available signature scopes
    export [--team-id ID] [--out P] — write current active signature to a shareable file
    import <path>                   — load external signature into the active scope
    capture [-- scope-args...]      — route to capture skill
    extract [-- scope-args...]      — route to extract skill
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def state_path(repo: Path) -> Path:
    return repo / ".signature-cache" / "state.json"


def load_state(repo: Path) -> dict:
    path = state_path(repo)
    if not path.exists():
        return {"enabled": True, "active_scope": "default"}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"enabled": True, "active_scope": "default"}
    state.setdefault("enabled", True)
    state.setdefault("active_scope", "default")
    return state


def save_state(repo: Path, state: dict) -> None:
    path = state_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def signature_path_for_scope(repo: Path, scope_name: str) -> Path:
    filename = "signature.json" if scope_name == "default" else f"signature.{scope_name}.json"
    return repo / filename


def list_scopes(repo: Path) -> list[str]:
    scopes: list[str] = []
    default = repo / "signature.json"
    if default.exists():
        scopes.append("default")
    for path in repo.glob("signature.*.json"):
        name = path.stem.removeprefix("signature.")
        if name:
            scopes.append(name)
    return sorted(scopes)


def cmd_on(repo: Path, _rest: list[str]) -> int:
    state = load_state(repo)
    state["enabled"] = True
    state["toggled_at"] = datetime.now(timezone.utc).isoformat()
    save_state(repo, state)
    print("cogsig: injection ENABLED")
    return 0


def cmd_off(repo: Path, _rest: list[str]) -> int:
    state = load_state(repo)
    state["enabled"] = False
    state["toggled_at"] = datetime.now(timezone.utc).isoformat()
    save_state(repo, state)
    print("cogsig: injection DISABLED")
    return 0


def cmd_status(repo: Path, _rest: list[str]) -> int:
    state = load_state(repo)
    enabled = "ON" if state["enabled"] else "OFF"
    scope = state["active_scope"]
    sig_path = signature_path_for_scope(repo, scope)
    print(f"cogsig: {enabled} | active scope: {scope}")

    if not sig_path.exists():
        print(f"  no signature at {sig_path.name} — run /cogsig capture + /cogsig extract")
        available = list_scopes(repo)
        if available:
            print(f"  available scopes: {', '.join(available)}")
        return 0

    try:
        sig = json.loads(sig_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"  signature at {sig_path.name} is unreadable")
        return 1

    origin = sig.get("origin", "?")
    team_id = sig.get("team_id")
    origin_tag = f"{origin}" + (f" (team_id: {team_id})" if team_id else "")
    print(f"  signature v{sig.get('version', '?')} generated {sig.get('generated_ts', '?')}")
    print(f"  domain: {sig.get('domain', '?')} | samples: {sig.get('sample_count', '?')} | languages: {', '.join(sig.get('languages', []))}")
    print(f"  origin: {origin_tag}")
    return 0


def cmd_scope(repo: Path, rest: list[str]) -> int:
    if not rest or rest[0] == "list":
        scopes = list_scopes(repo)
        state = load_state(repo)
        if not scopes:
            print("cogsig: no signatures exist yet")
            return 0
        print(f"cogsig: active scope = {state['active_scope']}")
        for name in scopes:
            marker = " *" if name == state["active_scope"] else ""
            print(f"  {name}{marker}")
        return 0

    target = rest[0]
    sig_path = signature_path_for_scope(repo, target)
    if not sig_path.exists():
        print(f"cogsig: no signature found for scope '{target}' — capture+extract with --scope-name {target} first")
        return 1

    state = load_state(repo)
    state["active_scope"] = target
    state["scope_switched_at"] = datetime.now(timezone.utc).isoformat()
    save_state(repo, state)
    print(f"cogsig: active scope -> {target}")
    return 0


def cmd_diff(repo: Path, _rest: list[str]) -> int:
    print("cogsig: diff mode not yet implemented (Step 5 target).")
    print("  planned: render next response under three conditions — baseline / placebo / real signature")
    return 0


def cmd_export(repo: Path, rest: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="/cogsig export", add_help=False)
    ap.add_argument("--team-id", default=None)
    ap.add_argument("--out", type=Path, default=None)
    args, _ = ap.parse_known_args(rest)

    state = load_state(repo)
    scope = state["active_scope"]
    src = signature_path_for_scope(repo, scope)
    if not src.exists():
        print(f"cogsig: no signature at active scope '{scope}' — nothing to export", file=sys.stderr)
        return 1

    try:
        sig = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"cogsig: {src.name} is unreadable", file=sys.stderr)
        return 1

    if args.team_id:
        sig["team_id"] = args.team_id
    sig.setdefault("export_ts", datetime.now(timezone.utc).isoformat())

    out = args.out or (repo / f"signature.export{'-' + args.team_id if args.team_id else ''}.json")
    out.write_text(json.dumps(sig, indent=2), encoding="utf-8")
    tid = f" [team_id: {args.team_id}]" if args.team_id else ""
    print(f"cogsig: exported scope '{scope}' -> {out}{tid}")
    print("  share this file. Recipient loads with: /cogsig import <path>")
    return 0


def cmd_import(repo: Path, rest: list[str]) -> int:
    if not rest:
        print("cogsig: /cogsig import <path> — path required", file=sys.stderr)
        return 1

    src = Path(rest[0]).expanduser().resolve()
    if not src.exists():
        print(f"cogsig: file not found: {src}", file=sys.stderr)
        return 1

    try:
        sig = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"cogsig: {src} is not valid JSON", file=sys.stderr)
        return 1

    sig["origin"] = "imported"
    sig["imported_ts"] = datetime.now(timezone.utc).isoformat()
    sig["imported_from"] = str(src)

    state = load_state(repo)
    scope = state["active_scope"]
    dst = signature_path_for_scope(repo, scope)
    dst.write_text(json.dumps(sig, indent=2), encoding="utf-8")
    team_id = sig.get("team_id")
    tid = f" [team_id: {team_id}]" if team_id else ""
    print(f"cogsig: imported -> scope '{scope}' ({dst.name}){tid}")
    print("  origin set to 'imported'. Historian will skip drift analysis.")
    return 0


def cmd_route(repo: Path, skill: str, rest: list[str]) -> int:
    script_map = {
        "capture": repo / "skills" / "capture" / "capture.py",
        "extract": repo / "skills" / "extract" / "extract.py",
    }
    script = script_map.get(skill)
    if not script or not script.exists():
        print(f"cogsig: skill '{skill}' not found at {script}", file=sys.stderr)
        return 1
    cmd = [sys.executable, str(script), "--repo", str(repo), *rest]
    result = subprocess.run(cmd, check=False)
    return result.returncode


HANDLERS = {
    "on": cmd_on,
    "off": cmd_off,
    "status": cmd_status,
    "scope": cmd_scope,
    "diff": cmd_diff,
    "export": cmd_export,
    "import": cmd_import,
}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: toggle.py <command> [args...]  (on|off|status|scope|diff|export|import|capture|extract)", file=sys.stderr)
        return 1

    # Accept --repo anywhere
    repo = Path.cwd()
    cleaned: list[str] = []
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--repo" and i + 1 < len(argv):
            repo = Path(argv[i + 1])
            i += 2
            continue
        cleaned.append(argv[i])
        i += 1
    repo = repo.resolve()

    command, rest = cleaned[0], cleaned[1:]

    if command in HANDLERS:
        return HANDLERS[command](repo, rest)
    if command in ("capture", "extract"):
        return cmd_route(repo, command, rest)

    print(f"cogsig: unknown command '{command}'", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
