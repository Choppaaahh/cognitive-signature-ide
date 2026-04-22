#!/usr/bin/env python3
"""dialogue_ingest — ingest a dialogue corpus (JSONL of user-typed messages)
and format it as samples.json for the directing-signature extract.

Accepts a JSONL file with rows containing at minimum a `content` field and
preferably a `source` field ("user" vs "agent"). Filters to user-only content
(source="user" OR source missing but type suggests user origin).

Input formats accepted:
  - session_breadcrumbs.jsonl (private scaffold): ts/type/content[/source]
  - Discord export (custom): ts/author/content
  - Generic chat: any JSONL with a `content` field

Usage:
    python3 skills/capture/dialogue_ingest.py --input PATH [--source-filter user]
                                              [--max-samples N] [--min-chars N]
                                              [--scope-name NAME]

Writes .signature-cache/samples.json (or .signature-cache/samples.<scope>.json)
ready for extract.py --domain directing.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DirectiveSample:
    content: str
    meta: str
    ts: str | None = None
    char_count: int = 0


def extract_content_text(raw_content) -> str | None:
    """Extract plain text from a content field that may be a string or a list of blocks.

    Claude Code native format stores content as either a string or a list of dicts like
    [{"type": "text", "text": "..."}, {"type": "tool_use", ...}].
    """
    if isinstance(raw_content, str):
        return raw_content
    if isinstance(raw_content, list):
        text_parts = []
        for block in raw_content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str):
                    text_parts.append(t)
        return "\n".join(text_parts) if text_parts else None
    return None


def parse_row(raw: dict) -> tuple[str | None, str | None, str | None, str | None]:
    """Extract (content, source, ts, meta) from a JSONL row in one of several known formats.

    Supported formats:
      - private scaffold breadcrumbs: {ts, type, content[, source]}
      - Claude Code native session: {type:"user"|"assistant", message:{role, content:str|list[block]}}
      - Discord export: {ts, author, content}
      - Generic chat: {content:str, ...}
    """
    row_type = raw.get("type") or raw.get("kind")
    source = raw.get("source") or raw.get("author") or raw.get("role")
    ts = raw.get("ts") or raw.get("timestamp") or raw.get("created_at")

    # Claude Code native format: content lives under message.content,
    # role lives under message.role or is implied by top-level type.
    content: str | None = None
    message = raw.get("message")
    if isinstance(message, dict):
        content = extract_content_text(message.get("content"))
        if not source:
            source = message.get("role")
    if content is None:
        content = extract_content_text(raw.get("content")) or raw.get("text")

    # If row_type is "user"/"assistant" (Claude Code native), treat as source hint
    if not source and row_type in ("user", "assistant"):
        source = row_type

    meta_parts: list[str] = []
    if ts:
        meta_parts.append(str(ts)[:19])
    if row_type and row_type not in ("user", "assistant"):
        meta_parts.append(f"type:{row_type}")
    if source:
        meta_parts.append(f"src:{source}")
    meta = ", ".join(meta_parts)
    return content, source, ts, meta


def is_user_row(source: str | None, row_type: str | None, source_filter: str) -> bool:
    if source_filter == "all":
        return True
    if source_filter == "user":
        if source == "user":
            return True
        if source in ("agent", "assistant", "bot", "system"):
            return False
        # Legacy breadcrumb row types that were typed by the user before source field was added
        if row_type in ("hunch", "dialogue", "config"):
            return True
        return False
    return source == source_filter


def ingest(
    input_path: Path,
    source_filter: str = "user",
    max_samples: int | None = None,
    min_chars: int = 10,
) -> dict:
    if not input_path.exists():
        raise FileNotFoundError(f"input file not found: {input_path}")

    samples: list[DirectiveSample] = []
    seen_signatures: set[str] = set()
    skipped_short = 0
    skipped_filter = 0
    skipped_dup = 0

    for line in input_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue

        content, source, ts, meta = parse_row(raw)
        if not content or not isinstance(content, str):
            continue

        row_type = raw.get("type")
        if not is_user_row(source, row_type, source_filter):
            skipped_filter += 1
            continue

        content = content.strip()
        if len(content) < min_chars:
            skipped_short += 1
            continue

        sig = content[:200]
        if sig in seen_signatures:
            skipped_dup += 1
            continue
        seen_signatures.add(sig)

        samples.append(
            DirectiveSample(content=content, meta=meta, ts=ts, char_count=len(content))
        )

    samples.sort(key=lambda s: str(s.ts) if s.ts is not None else "", reverse=True)
    if max_samples:
        samples = samples[:max_samples]

    return {
        "captured_ts": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "source_filter": source_filter,
        "sample_count": len(samples),
        "languages": ["dialogue"],
        "domain_hint": "directing",
        "stats": {
            "skipped_below_min_chars": skipped_short,
            "skipped_by_source_filter": skipped_filter,
            "skipped_duplicates": skipped_dup,
        },
        "samples": [asdict(s) for s in samples],
    }


def samples_path_for_scope(repo: Path, scope_name: str) -> Path:
    filename = "samples.json" if scope_name == "default" else f"samples.{scope_name}.json"
    return repo / ".signature-cache" / filename


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest a dialogue corpus (JSONL) for directing-signature extract.")
    ap.add_argument("--input", type=Path, required=True, help="Path to JSONL file containing dialogue/directives")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--scope-name", default="default")
    ap.add_argument("--source-filter", default="user", help="Filter by source field (user/agent/all)")
    ap.add_argument("--max-samples", type=int, default=100)
    ap.add_argument("--min-chars", type=int, default=20, help="Skip directives shorter than this")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    repo = args.repo.resolve()
    out_path = args.out or samples_path_for_scope(repo, args.scope_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = ingest(
        args.input,
        source_filter=args.source_filter,
        max_samples=args.max_samples,
        min_chars=args.min_chars,
    )

    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    stats = result["stats"]
    print(f"ingested {result['sample_count']} user-directives from {args.input}")
    print(f"  filtered-by-source: {stats['skipped_by_source_filter']}, too-short: {stats['skipped_below_min_chars']}, duplicates: {stats['skipped_duplicates']}")
    if result["samples"]:
        avg_chars = sum(s["char_count"] for s in result["samples"]) / len(result["samples"])
        print(f"  avg directive length: {avg_chars:.0f} chars")
    print(f"wrote {out_path}")
    print(f"next: python3 skills/extract/extract.py --repo {repo} --domain directing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
