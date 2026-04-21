#!/usr/bin/env python3
"""extract — call Opus 4.7 on captured samples → produce signature.json.

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python3 skills/extract/extract.py [--repo PATH] [--model claude-opus-4-7]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MODEL_DEFAULT = "claude-opus-4-7"

PROMPT_TEMPLATE = """You are analyzing code samples to extract the author's coding signature — a structured description of HOW they write code, not WHAT the code does.

You will output valid JSON matching this schema:

{schema}

Analyze the samples below and return ONLY the JSON object. No markdown, no commentary, just the raw JSON starting with {{ and ending with }}.

Focus on descriptive, not prescriptive — you are describing the author's style, not evaluating it.

For confidence scores:
  - 0.8-1.0: strong, consistent evidence across multiple samples
  - 0.5-0.8: visible pattern but with some variance
  - below 0.5: weak or contradictory evidence
If a dimension can't be assessed (e.g. no error handling observed), use confidence 0.3 and a generic default plus a note explaining why.

SAMPLES ({sample_count} total, languages: {languages}):

{samples}

Return the signature JSON now."""


def format_samples(samples: list[dict], max_per_sample: int = 1500) -> str:
    blocks: list[str] = []
    for i, s in enumerate(samples, 1):
        content = s["content"][:max_per_sample]
        blocks.append(
            f"--- Sample {i}: {s['path']} ({s['language']}, {s['line_count']} lines) ---\n{content}"
        )
    return "\n\n".join(blocks)


def extract(samples_path: Path, schema_path: Path, model: str) -> dict:
    try:
        import anthropic
    except ImportError:
        print("error: anthropic SDK not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        raise

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        raise SystemExit(2)

    samples_doc = json.loads(samples_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    prompt = PROMPT_TEMPLATE.format(
        schema=json.dumps(schema, indent=2),
        sample_count=samples_doc["sample_count"],
        languages=", ".join(samples_doc["languages"]),
        samples=format_samples(samples_doc["samples"]),
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()

    signature = json.loads(text)
    signature["version"] = "0.1"
    signature["generated_ts"] = datetime.now(timezone.utc).isoformat()
    signature["origin"] = "self"
    signature["domain"] = signature.get("domain", "code")
    signature["sample_count"] = samples_doc["sample_count"]
    signature["languages"] = samples_doc["languages"]
    return signature


def validate(signature: dict, schema_path: Path) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed — skipping validation"]

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = [f"{'.'.join(str(p) for p in e.path)}: {e.message}" for e in validator.iter_errors(signature)]
    return errors


def samples_path_for_scope(repo: Path, scope_name: str) -> Path:
    filename = "samples.json" if scope_name == "default" else f"samples.{scope_name}.json"
    return repo / ".signature-cache" / filename


def signature_path_for_scope(repo: Path, scope_name: str) -> Path:
    filename = "signature.json" if scope_name == "default" else f"signature.{scope_name}.json"
    return repo / filename


def main() -> int:
    ap = argparse.ArgumentParser(description="Call Opus 4.7 on samples → signature.json")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--scope-name", default="default", help="Signature scope label")
    ap.add_argument("--samples", type=Path, default=None)
    ap.add_argument("--schema", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    repo = args.repo.resolve()
    samples_path = args.samples or samples_path_for_scope(repo, args.scope_name)
    schema_path = args.schema or (repo / "skills" / "extract" / "signature_schema.json")
    out_path = args.out or signature_path_for_scope(repo, args.scope_name)
    history_path = repo / ".signature-cache" / ("signature_history.jsonl" if args.scope_name == "default" else f"signature_history.{args.scope_name}.jsonl")

    if not samples_path.exists():
        print(f"error: {samples_path} missing — run capture first", file=sys.stderr)
        return 1
    if not schema_path.exists():
        print(f"error: {schema_path} missing", file=sys.stderr)
        return 1

    signature = extract(samples_path, schema_path, args.model)
    if args.scope_name != "default":
        signature["scope"] = args.scope_name
    errors = validate(signature, schema_path)
    if errors:
        print("validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("(signature still written; route to Signature-QA for review)", file=sys.stderr)

    out_path.write_text(json.dumps(signature, indent=2), encoding="utf-8")
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(signature) + "\n")

    print(f"wrote {out_path}")
    print(f"appended {history_path}")
    print("--- summary ---")
    for dim, val in signature.get("dimensions", {}).items():
        conf = val.get("confidence", "?")
        hint = val.get("primary_style") or val.get("preference") or val.get("try_except_style") or val.get("nesting_depth") or ""
        print(f"  {dim}: {hint} (conf {conf})")

    return 0 if not errors else 3


if __name__ == "__main__":
    raise SystemExit(main())
