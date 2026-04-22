#!/usr/bin/env python3
"""init — one-command auto-seed from Claude Code session history.

Scans ~/.claude/projects/**/*.jsonl, aggregates user-typed directives into
a dialogue corpus, runs extract --domain directing. Default onboarding.

Usage:
    python3 skills/init/init.py [--repo PATH] [--claude-projects PATH]
                                [--yes] [--max-samples N] [--min-chars N]
                                [--no-seed] [--advisor auto|always|off]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"


@dataclass
class ProjectStats:
    name: str
    session_count: int
    size_bytes: int


def scan_claude_projects(projects_dir: Path) -> tuple[list[Path], list[ProjectStats]]:
    if not projects_dir.exists():
        return [], []
    sessions: list[Path] = []
    stats: list[ProjectStats] = []
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        project_sessions = sorted(project_dir.glob("*.jsonl"))
        sessions.extend(project_sessions)
        total_size = sum(p.stat().st_size for p in project_sessions if p.exists())
        stats.append(ProjectStats(
            name=project_dir.name,
            session_count=len(project_sessions),
            size_bytes=total_size,
        ))
    return sessions, stats


def estimate_directive_count(sessions: list[Path], sample_files: int = 10) -> int:
    """Rough estimate of total user-typed directives across sessions (samples a subset)."""
    if not sessions:
        return 0
    sample = sessions[:sample_files]
    total_directives = 0
    total_sessions_sampled = len(sample)
    for session in sample:
        try:
            for line in session.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("type") == "user":
                    total_directives += 1
        except OSError:
            continue
    if total_sessions_sampled == 0:
        return 0
    avg_per_session = total_directives / total_sessions_sampled
    return int(avg_per_session * len(sessions))


def aggregate_corpus(sessions: list[Path], out_path: Path) -> Path:
    """Concatenate user-typed rows from all sessions into a single JSONL corpus."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as out:
        for session in sessions:
            try:
                for line in session.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("type") == "user":
                        out.write(line + "\n")
                        written += 1
            except OSError:
                continue
    return out_path


def confirm(prompt: str) -> bool:
    try:
        response = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return response in ("", "y", "yes")


def run_cmd(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, check=False)
    return result.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="One-command onboarding: seed signature from Claude Code session history.")
    ap.add_argument("--repo", type=Path, default=Path.cwd(), help="Plugin repo root")
    ap.add_argument("--claude-projects", type=Path, default=DEFAULT_CLAUDE_PROJECTS,
                    help=f"Claude Code projects dir (default: {DEFAULT_CLAUDE_PROJECTS})")
    ap.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    ap.add_argument("--max-samples", type=int, default=100)
    ap.add_argument("--min-chars", type=int, default=30)
    ap.add_argument("--scope-name", default="default")
    ap.add_argument("--no-seed", action="store_true",
                    help="Skip auto-seed — create empty state for cold-start")
    ap.add_argument("--advisor", choices=["auto", "always", "off"], default="auto")
    ap.add_argument("--voice-only", action="store_true",
                    help="Extract only the voice (directing) signature. Skip operational-signature pass.")
    ap.add_argument("--operational-only", action="store_true",
                    help="Extract only the operational-patterns signature. Skip voice-signature pass.")
    ap.add_argument("--preset", choices=["normie", "power", "team", "enterprise"], default=None,
                    help="Skip setup-wizard by preselecting preset (normie|power|team|enterprise).")
    args = ap.parse_args()

    repo = args.repo.resolve()
    projects_dir = args.claude_projects

    # Setup wizard — ask user to pick preset unless --preset flag or --yes
    preset = args.preset
    if not preset and not args.yes:
        print("\ncogsig init: how do you want CogSig to work?\n")
        print("  [1] normie — hands-off, auto-promote patterns silently at n=2")
        print("  [2] power  — review-before-promote, you approve/reject new patterns (default)")
        print("  [3] team   — option 2 + team-lead audit trail + Signature-Brutus/QA/Historian governance")
        print("  [4] enterprise — option 3 + Claude Managed Agents (cloud-governed, audit log)")
        print()
        try:
            choice = input("pick [1/2/3/4] (default 2): ").strip() or "2"
        except (EOFError, KeyboardInterrupt):
            choice = "2"
        preset_map = {"1": "normie", "2": "power", "3": "team", "4": "enterprise"}
        preset = preset_map.get(choice, "power")
        print(f"  → preset set to: {preset}\n")
    elif not preset:
        preset = "power"

    # Persist preset to state.json for review + inject to read
    state_file = repo / ".signature-cache" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    state["preset"] = preset
    state["preset_set_ts"] = datetime.now(timezone.utc).isoformat()
    state.setdefault("enabled", True)
    state.setdefault("active_scope", "default")
    state.setdefault("active_mode", "standalone" if preset == "normie" else ("cloud" if preset == "enterprise" else "standalone"))
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    if args.no_seed:
        print("cogsig init: --no-seed mode. No signature will be extracted.")
        print("Signature will build from live usage once PostToolUse wiring ships.")
        return 0

    print(f"cogsig init: scanning {projects_dir} ...")
    sessions, stats = scan_claude_projects(projects_dir)

    if not sessions:
        print(f"  no sessions found at {projects_dir}")
        print("  options:")
        print(f"    - pass --claude-projects PATH to point at a different location")
        print(f"    - use /cogsig import-corpus <path-to-dialogue-jsonl> for a custom corpus")
        print(f"    - use --no-seed for cold-start")
        return 1

    estimated_directives = estimate_directive_count(sessions)
    print(f"  found {len(sessions)} sessions across {len(stats)} projects")
    print(f"  estimated ~{estimated_directives} user-directives total")
    for s in stats[:5]:
        print(f"    {s.name[:40]:40s} {s.session_count:4d} sessions "
              f"({s.size_bytes / 1024 / 1024:.1f} MB)")
    if len(stats) > 5:
        print(f"    ... and {len(stats) - 5} more projects")

    if not args.yes:
        if not confirm("\nBuild signature from this corpus? [Y/n] "):
            print("cogsig init: cancelled")
            return 0

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tf:
        corpus_path = Path(tf.name)
    try:
        aggregate_corpus(sessions, corpus_path)
        print(f"\n[1/2] aggregated corpus -> {corpus_path}")

        repo_path = str(repo)
        ingest_script = repo / "skills" / "capture" / "dialogue_ingest.py"
        extract_script = repo / "skills" / "extract" / "extract.py"

        ingest_rc = run_cmd([
            sys.executable, str(ingest_script),
            "--repo", repo_path,
            "--input", str(corpus_path),
            "--source-filter", "user",
            "--max-samples", str(args.max_samples),
            "--min-chars", str(args.min_chars),
            "--scope-name", args.scope_name,
        ])
        if ingest_rc != 0:
            print("error: ingest failed", file=sys.stderr)
            return ingest_rc

        do_voice = not args.operational_only
        do_operational = not args.voice_only
        total_extracts = int(do_voice) + int(do_operational)
        step = 2
        voice_path = repo / ("signature.json" if args.scope_name == "default" else f"signature.{args.scope_name}.json")
        op_scope = f"{args.scope_name}-operational" if args.scope_name != "default" else "operational"
        op_path = repo / f"signature.{op_scope}.json"

        # Both extractions read from the same ingested samples file.
        samples_filename = "samples.json" if args.scope_name == "default" else f"samples.{args.scope_name}.json"
        shared_samples = repo / ".signature-cache" / samples_filename

        if do_voice:
            print(f"\n[{step}/{total_extracts + 1}] extracting VOICE signature via Opus 4.7 (directing domain)...")
            step += 1
            rc = run_cmd([
                sys.executable, str(extract_script),
                "--repo", repo_path,
                "--domain", "directing",
                "--scope-name", args.scope_name,
                "--samples", str(shared_samples),
                "--advisor", args.advisor,
            ])
            if rc not in (0, 3):
                print("error: voice extract failed", file=sys.stderr)
                return rc

        if do_operational:
            print(f"\n[{step}/{total_extracts + 1}] extracting OPERATIONAL signature via Opus 4.7 (operational domain)...")
            step += 1
            rc = run_cmd([
                sys.executable, str(extract_script),
                "--repo", repo_path,
                "--domain", "operational",
                "--scope-name", op_scope,
                "--samples", str(shared_samples),
                "--advisor", args.advisor,
            ])
            if rc not in (0, 3):
                print("error: operational extract failed", file=sys.stderr)
                return rc

        print(f"\ncogsig init: complete.")
        if do_voice:
            print(f"  voice signature:       {voice_path.name}")
        if do_operational:
            print(f"  operational signature: {op_path.name}")
        print(f"  toggle on/off:         python3 skills/toggle/toggle.py on|off --repo {repo}")
        print(f"  check status:          python3 skills/toggle/toggle.py status --repo {repo}")
        return 0
    finally:
        try:
            corpus_path.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
