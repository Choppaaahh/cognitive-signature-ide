#!/usr/bin/env python3
"""blind_test — generate 3 outputs per prompt under 3 conditions.

Conditions:
  - baseline: no signature injected (Claude default style)
  - placebo:  a plausible-looking but random signature (all dimensions, low confidence)
  - real:     the user's actual signature from signature.json

For each of the 10 prompts in measurement/prompts.json, the model produces 3
outputs. 30 total files are written to measurement/blind_outputs/<prompt-id>/.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 measurement/blind_test.py [--repo PATH] [--model claude-opus-4-7]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


PLACEBO_SIGNATURE = {
    "version": "0.1",
    "origin": "self",
    "domain": "code",
    "sample_count": 5,
    "languages": ["python"],
    "dimensions": {
        "naming_convention": {
            "primary_style": "camelCase",
            "confidence": 0.6,
            "evidence": "Mixed naming observed with slight preference for camelCase."
        },
        "comment_density": {
            "comments_per_100_lines": 4,
            "docstring_presence": "rare",
            "style": "inline",
            "confidence": 0.5
        },
        "function_length": {
            "p50_lines": 30,
            "p90_lines": 75,
            "max_observed": 120,
            "preference": "verbose",
            "confidence": 0.5
        },
        "error_handling": {
            "try_except_style": "broad",
            "validation_pattern": "deep-check",
            "bare_except_tolerance": "accepted",
            "confidence": 0.5
        },
        "import_organization": {
            "grouping": "alphabetical",
            "aliasing_style": "always",
            "confidence": 0.5
        },
        "structural_preference": {
            "nesting_depth": "deep",
            "early_return_pattern": "avoided",
            "helper_extraction": "inline-everything",
            "confidence": 0.5
        }
    }
}


def render_signature_prefix(signature: dict) -> str:
    dims = signature.get("dimensions", {})
    lines = [f"[User's Cognitive Signature — v{signature.get('version', '?')}]", ""]
    lines.append("The user's coding signature:")
    for name, value in dims.items():
        if not isinstance(value, dict):
            continue
        hint = (
            value.get("primary_style")
            or value.get("preference")
            or value.get("try_except_style")
            or value.get("nesting_depth")
            or value.get("grouping")
            or value.get("docstring_presence")
            or "?"
        )
        conf = value.get("confidence", "?")
        lines.append(f"  - {name}: {hint} (confidence {conf})")
        evidence = value.get("evidence", "")
        if evidence:
            lines.append(f"      evidence: {evidence}")
    lines.append("")
    lines.append("Match this signature when generating code. Do not default to generic conventions if they conflict with the user's established patterns.")
    return "\n".join(lines)


def call_claude(client, model: str, prompt: str, signature: dict | None) -> str:
    messages = [{"role": "user", "content": prompt}]
    kwargs = {"model": model, "max_tokens": 1024, "messages": messages}
    if signature is not None:
        kwargs["system"] = render_signature_prefix(signature)
    response = client.messages.create(**kwargs)
    out_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "".join(out_parts).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate blind-test outputs for cogsig measurement.")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--model", default="claude-opus-4-7")
    ap.add_argument("--signature", type=Path, default=None)
    ap.add_argument("--prompts", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=42, help="RNG seed for shuffle determinism later")
    args = ap.parse_args()

    try:
        import anthropic
    except ImportError:
        print("error: anthropic SDK not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    repo = args.repo.resolve()
    sig_path = args.signature or (repo / "signature.json")
    prompts_path = args.prompts or (repo / "measurement" / "prompts.json")
    out_dir = args.out or (repo / "measurement" / "blind_outputs")

    if not sig_path.exists():
        print(f"error: {sig_path} missing — run capture + extract first", file=sys.stderr)
        return 1
    if not prompts_path.exists():
        print(f"error: {prompts_path} missing", file=sys.stderr)
        return 1

    real_signature = json.loads(sig_path.read_text(encoding="utf-8"))
    prompts = json.loads(prompts_path.read_text(encoding="utf-8"))["prompts"]
    client = anthropic.Anthropic(api_key=api_key)

    out_dir.mkdir(parents=True, exist_ok=True)

    run_manifest = {
        "run_ts": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "seed": args.seed,
        "signature_version": real_signature.get("version"),
        "signature_generated_ts": real_signature.get("generated_ts"),
        "prompt_count": len(prompts),
        "prompts": [p["id"] for p in prompts],
    }

    for i, prompt in enumerate(prompts, 1):
        pid = prompt["id"]
        prompt_dir = out_dir / pid
        prompt_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{i}/{len(prompts)}] {pid}", file=sys.stderr)

        for condition, sig in (
            ("baseline", None),
            ("placebo", PLACEBO_SIGNATURE),
            ("real", real_signature),
        ):
            out_path = prompt_dir / f"{condition}.md"
            if out_path.exists():
                print(f"  {condition}: skip (already exists)", file=sys.stderr)
                continue
            print(f"  {condition}: generating...", file=sys.stderr)
            text = call_claude(client, args.model, prompt["prompt"], sig)
            out_path.write_text(text, encoding="utf-8")

        print(f"  done -> {prompt_dir}", file=sys.stderr)

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    print(f"\nwrote {manifest_path}", file=sys.stderr)
    print(f"next: python3 measurement/score.py --repo {repo}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
