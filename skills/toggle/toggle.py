#!/usr/bin/env python3
"""toggle — /cogsig slash command handler.

Subcommands:
    on                              — enable injection (default)
    off                             — disable injection
    status                          — show state + active-scope signature metadata + active governance mode
    diff                            — three-way comparison of next response (Step 5)
    scope <name>                    — switch active scope (default / work / personal / ...)
    scope list                      — list all locally-available signature scopes
    mode <standalone|team|cloud>    — select governance deployment mode
    mode status                     — show active governance mode
    init [-- init-args...]          — auto-seed signature from Claude Code session history
    capture [-- scope-args...]      — route to capture skill
    extract [-- scope-args...]      — route to extract skill
    export [-- export-args...]      — route to export skill (team-sharing)
    import <path> [-- args...]      — route to import_sig skill (load teammate signature)
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def state_path(repo: Path) -> Path:
    return repo / ".signature-cache" / "state.json"


VALID_MODES = ("standalone", "team", "cloud")
VALID_ENFORCE_MODES = ("off", "warn", "reject")


def load_state(repo: Path) -> dict:
    path = state_path(repo)
    if not path.exists():
        return {"enabled": True, "active_scope": "default", "active_mode": "standalone"}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"enabled": True, "active_scope": "default", "active_mode": "standalone"}
    state.setdefault("enabled", True)
    state.setdefault("active_scope", "default")
    state.setdefault("active_mode", "standalone")
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
    mode = state.get("active_mode", "standalone")
    preset = state.get("preset")
    sig_path = signature_path_for_scope(repo, scope)
    preset_tag = f" | preset: {preset}" if preset else ""
    print(f"cogsig: {enabled} | scope: {scope}{preset_tag} | governance mode: {mode}")

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


def cmd_mode(repo: Path, rest: list[str]) -> int:
    """/cogsig mode <name> | mode status | mode list — select governance deployment mode."""
    if not rest or rest[0] == "status":
        state = load_state(repo)
        mode = state.get("active_mode", "standalone")
        print(f"cogsig: governance mode = {mode}")
        _print_mode_description(mode)
        return 0
    if rest[0] == "list":
        state = load_state(repo)
        active = state.get("active_mode", "standalone")
        print("cogsig governance modes:")
        for m in VALID_MODES:
            marker = " *" if m == active else ""
            print(f"  {m}{marker}")
            _print_mode_description(m, indent="      ")
        return 0
    target = rest[0]
    if target not in VALID_MODES:
        print(f"cogsig: unknown mode '{target}'. Valid: {', '.join(VALID_MODES)}", file=sys.stderr)
        return 1
    state = load_state(repo)
    state["active_mode"] = target
    state["mode_switched_at"] = datetime.now(timezone.utc).isoformat()
    save_state(repo, state)
    print(f"cogsig: governance mode -> {target}")
    _print_mode_description(target)
    return 0


def _print_mode_description(mode: str, indent: str = "  ") -> None:
    descriptions = {
        "standalone": "direct API call, no governance agents — fastest, cheapest, normies/casual users",
        "team": "in-session Claude Code subagents (brutus / qa / historian, dual-function) — power users, small teams",
        "cloud": "Claude Managed Agents beta (managed-agents-2026-04-01) — enterprise, audit trail, cross-device sync",
    }
    desc = descriptions.get(mode)
    if desc:
        print(f"{indent}{desc}")


def cmd_toggle_enforce(repo: Path, rest: list[str]) -> int:
    """/cogsig toggle-enforce <off|warn|reject> | status — control v2 enforcement mode."""
    if not rest or rest[0] == "status":
        state = load_state(repo)
        mode = state.get("enforcement_mode", "warn")
        print(f"cogsig: enforcement mode = {mode}")
        _print_enforce_description(mode)
        return 0
    target = rest[0]
    if target not in VALID_ENFORCE_MODES:
        print(f"cogsig: unknown enforcement mode '{target}'. Valid: {', '.join(VALID_ENFORCE_MODES)}", file=sys.stderr)
        return 1
    state = load_state(repo)
    state["enforcement_mode"] = target
    state["enforcement_mode_switched_at"] = datetime.now(timezone.utc).isoformat()
    save_state(repo, state)
    print(f"cogsig: enforcement mode -> {target}")
    _print_enforce_description(target)
    return 0


def _print_enforce_description(mode: str, indent: str = "  ") -> None:
    descriptions = {
        "off": "no enforcement; PreToolUse hook passes through silently",
        "warn": "advisory only — violations surfaced as text but tool calls always proceed (default; safe)",
        "reject": "high-severity violations exit 1 and block the tool call; medium/low still pass with advisory",
    }
    desc = descriptions.get(mode)
    if desc:
        print(f"{indent}{desc}")


def cmd_pause_enforce(repo: Path, _rest: list[str]) -> int:
    """/cogsig pause-enforce — bypass enforcement for the next single tool call."""
    cache_dir = repo / ".signature-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    flag = cache_dir / "enforcement_pause"
    flag.touch()
    print("cogsig: enforcement paused for next tool call (auto-clears on use)")
    return 0


def cmd_diff(repo: Path, _rest: list[str]) -> int:
    print("cogsig: diff mode not yet implemented (Step 5 target).")
    print("  planned: render next response under three conditions — baseline / placebo / real signature")
    return 0


def cmd_route(repo: Path, skill: str, rest: list[str]) -> int:
    script_map = {
        "init": repo / "skills" / "init" / "init.py",
        "capture": repo / "skills" / "capture" / "capture.py",
        "extract": repo / "skills" / "extract" / "extract.py",
        "export": repo / "skills" / "export" / "export.py",
        "import": repo / "skills" / "import_sig" / "import_sig.py",
        "pending": repo / "skills" / "review" / "review.py",
        "approve": repo / "skills" / "review" / "review.py",
        "reject": repo / "skills" / "review" / "review.py",
        "edit-pattern": repo / "skills" / "review" / "review.py",
        "refresh-queue": repo / "skills" / "review" / "review.py",
    }
    # Review skill takes a positional command; map toggle-side name to review-side command.
    review_cmd_map = {
        "pending": "pending",
        "approve": "approve",
        "reject": "reject",
        "edit-pattern": "edit",
        "refresh-queue": "refresh-queue",
    }
    if skill in review_cmd_map:
        script = script_map[skill]
        cmd = [sys.executable, str(script), review_cmd_map[skill], *rest, "--repo", str(repo)]
        result = subprocess.run(cmd, check=False)
        return result.returncode
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
    "mode": cmd_mode,
    "diff": cmd_diff,
    "toggle-enforce": cmd_toggle_enforce,
    "pause-enforce": cmd_pause_enforce,
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
    if command in ("init", "capture", "extract", "export", "import",
                   "pending", "approve", "reject", "edit-pattern", "refresh-queue"):
        return cmd_route(repo, command, rest)

    print(f"cogsig: unknown command '{command}'", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
