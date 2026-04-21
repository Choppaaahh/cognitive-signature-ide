#!/usr/bin/env python3
"""capture — sample recent code the user has authored.

Outputs `.signature-cache/samples.json` in the repo root. Consumed by `extract`.

Usage:
    python3 skills/capture/capture.py [--repo PATH] [--max-samples N] [--max-chars N]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

CODE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".php": "php",
    ".sh": "bash",
    ".lua": "lua",
}

SKIP_PATHS = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "dist",
    "build",
    ".next",
    ".signature-cache",
    "vendor",
    "target",
}


@dataclass
class Sample:
    path: str
    language: str
    content: str
    line_count: int


def run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def git_user_email(repo: Path) -> str | None:
    email = run(["git", "config", "user.email"], repo)
    return email or None


def git_authored_files(repo: Path, email: str, n_commits: int = 50) -> list[str]:
    raw = run(
        ["git", "log", f"--author={email}", f"-n{n_commits}", "--name-only", "--pretty=format:"],
        repo,
    )
    seen: set[str] = set()
    ordered: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        ordered.append(line)
    return ordered


def recent_working_files(repo: Path) -> list[str]:
    tracked = run(["git", "ls-files"], repo).splitlines()
    scored: list[tuple[float, str]] = []
    for rel in tracked:
        path = repo / rel
        if not path.is_file():
            continue
        try:
            scored.append((path.stat().st_mtime, rel))
        except OSError:
            continue
    scored.sort(reverse=True)
    return [rel for _, rel in scored[:100]]


def is_code_file(rel_path: str) -> tuple[bool, str]:
    parts = Path(rel_path).parts
    if any(skip in parts for skip in SKIP_PATHS):
        return False, ""
    ext = Path(rel_path).suffix.lower()
    lang = CODE_EXTENSIONS.get(ext)
    return (lang is not None), (lang or "")


def load_sample(repo: Path, rel_path: str, max_chars: int) -> Sample | None:
    ok, lang = is_code_file(rel_path)
    if not ok:
        return None
    full = repo / rel_path
    if not full.is_file():
        return None
    try:
        text = full.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.strip():
        return None
    truncated = text[:max_chars]
    line_count = text.count("\n") + 1
    return Sample(path=rel_path, language=lang, content=truncated, line_count=line_count)


def capture(repo: Path, max_samples: int = 20, max_chars: int = 4000) -> dict:
    email = git_user_email(repo)
    if not email:
        print("warn: no git user.email set, falling back to recent working files only", file=sys.stderr)
        candidates = recent_working_files(repo)
    else:
        authored = git_authored_files(repo, email)
        working = recent_working_files(repo)
        candidates = authored + [p for p in working if p not in authored]

    samples: list[Sample] = []
    for rel_path in candidates:
        if len(samples) >= max_samples:
            break
        sample = load_sample(repo, rel_path, max_chars)
        if sample:
            samples.append(sample)

    languages = sorted({s.language for s in samples})
    output = {
        "captured_ts": datetime.now(timezone.utc).isoformat(),
        "repo_path": str(repo),
        "git_email": email,
        "sample_count": len(samples),
        "languages": languages,
        "samples": [asdict(s) for s in samples],
    }
    return output


def main() -> int:
    ap = argparse.ArgumentParser(description="Sample recent code the user has authored.")
    ap.add_argument("--repo", type=Path, default=Path.cwd(), help="Repo root (default: cwd)")
    ap.add_argument("--max-samples", type=int, default=20)
    ap.add_argument("--max-chars", type=int, default=4000)
    ap.add_argument("--out", type=Path, default=None, help="Output path (default: <repo>/.signature-cache/samples.json)")
    args = ap.parse_args()

    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        print(f"error: {repo} is not a git repo", file=sys.stderr)
        return 1

    out_path = args.out or (repo / ".signature-cache" / "samples.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = capture(repo, max_samples=args.max_samples, max_chars=args.max_chars)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"captured {result['sample_count']} samples across {len(result['languages'])} languages: {', '.join(result['languages'])}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
