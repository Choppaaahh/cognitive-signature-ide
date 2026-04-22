#!/usr/bin/env python3
"""advisor — strategic reframe at executor inflection points.

Anthropic Claude Advisor pattern: executor agents run routine work; advisor
is consulted only at inflection points (low-confidence extraction, ambiguous
dimensions, conflicting governance, unexplained drift) for a short reframe
rather than parameter-tuning.

Used as a library by other skills:

    from advisor import consult
    result = consult(
        context={"signature": sig, "samples": samples_doc, ...},
        inflection_class="low-confidence",
    )
    # result = {"reframe": str, "suggested_action": str, "confidence": float, "diagnosis": str}

CLI usage (for testing + demo beats):

    python3 skills/advisor/advisor.py --context context.json --class low-confidence
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


MODEL_DEFAULT = "claude-opus-4-7"

INFLECTION_CLASSES = (
    "low-confidence",
    "schema-soft-fail",
    "conflicting-governance",
    "drift-unexplained",
    "manual",
)

PROMPT_TEMPLATE = """You are the ADVISOR — a strategic-reframe model consulted at inflection points by executor agents running a signature-extraction pipeline.

An executor has hit an inflection of class: **{inflection_class}**

Your job is NOT to tune parameters or retry the executor's current approach. Your job is to identify whether the PROBLEM FRAMING is wrong.

Three patterns of inflection-response:
  - **frame-shift**: the executor is solving the wrong problem. Tell them what problem they should actually be solving.
  - **corpus-shift**: the executor is using the wrong input. Tell them what corpus would be more appropriate.
  - **no-reframe-needed**: the executor is doing it right; the inflection reflects genuine uncertainty, not a misframe. Tell them to proceed with caveat.

Respond in strict JSON (no markdown, no preamble, raw JSON starting with {{ and ending with }}):

{{
  "reframe": "<one-sentence strategic reframe; if no-reframe-needed, state that>",
  "suggested_action": "<concrete next step for the executor, e.g. 're-extract with corpus filtered for X', 'accept signature with explicit low-confidence-on-dimension-Y flag', 'consult user before proceeding'>",
  "confidence": <0.0-1.0; your confidence in this reframe>,
  "diagnosis": "<2-3 sentences: why this inflection is happening, what underlying condition produced it>"
}}

CONTEXT:

{context_dump}

Return the advisor JSON now."""


def summarize_context(context: dict, max_chars: int = 4000) -> str:
    """Render the executor's context into a bounded text blob for the advisor prompt."""
    lines: list[str] = []
    if "signature" in context:
        sig = context["signature"]
        lines.append("SIGNATURE (executor's current extraction):")
        lines.append(json.dumps(sig, indent=2)[:max_chars // 2])
        lines.append("")
    if "samples_summary" in context:
        lines.append(f"SAMPLES SUMMARY: {context['samples_summary']}")
        lines.append("")
    elif "samples" in context:
        samples = context["samples"]
        if isinstance(samples, dict):
            lines.append(f"SAMPLES: {samples.get('sample_count', '?')} items, "
                         f"languages={samples.get('languages', [])}, "
                         f"scope={samples.get('scope', 'default')}")
            if samples.get("stats"):
                lines.append(f"  stats: {samples['stats']}")
        lines.append("")
    if "low_confidence_dimensions" in context:
        lines.append(f"LOW-CONFIDENCE DIMENSIONS: {context['low_confidence_dimensions']}")
        lines.append("")
    if "validation_errors" in context:
        lines.append(f"VALIDATION ERRORS: {context['validation_errors']}")
        lines.append("")
    reviews = context.get("governance_reviews")
    if reviews:
        lines.append("GOVERNANCE REVIEW SUMMARIES:")
        if isinstance(reviews, dict):
            for agent, text in reviews.items():
                lines.append(f"  {agent}: {str(text)[:500]}")
        elif isinstance(reviews, list):
            for entry in reviews:
                if isinstance(entry, dict):
                    agent = entry.get("agent", "?")
                    text = entry.get("response", entry.get("text", str(entry)))
                    lines.append(f"  {agent}: {str(text)[:500]}")
                else:
                    lines.append(f"  {str(entry)[:500]}")
        else:
            lines.append(f"  {str(reviews)[:500]}")
        lines.append("")
    if "historian_drift" in context:
        lines.append(f"HISTORIAN DRIFT REPORT: {context['historian_drift']}")
        lines.append("")
    if "notes" in context:
        lines.append(f"NOTES: {context['notes']}")
    return "\n".join(lines)[:max_chars]


def parse_advisor_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    return json.loads(text)


def consult(context: dict, inflection_class: str, model: str = MODEL_DEFAULT) -> dict:
    """Consult the advisor at an inflection. Returns {reframe, suggested_action, confidence, diagnosis}."""
    if inflection_class not in INFLECTION_CLASSES:
        raise ValueError(f"unknown inflection_class '{inflection_class}'. "
                         f"Must be one of: {INFLECTION_CLASSES}")

    try:
        import anthropic
    except ImportError:
        print("error: anthropic SDK not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        raise

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("error: ANTHROPIC_API_KEY not set")

    prompt = PROMPT_TEMPLATE.format(
        inflection_class=inflection_class,
        context_dump=summarize_context(context),
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    result = parse_advisor_response(text)
    result["consulted_ts"] = datetime.now(timezone.utc).isoformat()
    result["inflection_class"] = inflection_class
    result["model"] = model
    return result


def detect_low_confidence(signature: dict, threshold: float = 0.5) -> list[str]:
    """Return list of dimension names whose confidence is below threshold."""
    low: list[str] = []
    for name, value in signature.get("dimensions", {}).items():
        if isinstance(value, dict):
            conf = value.get("confidence")
            if isinstance(conf, (int, float)) and conf < threshold:
                low.append(name)
    return low


def should_consult(signature: dict | None, validation_errors: list | None = None, threshold: float = 0.5) -> tuple[bool, str]:
    """Default inflection-detection logic used by extract.py post-extraction.

    Returns (should_consult, inflection_class).
    """
    if validation_errors:
        return True, "schema-soft-fail"
    if signature:
        low = detect_low_confidence(signature, threshold=threshold)
        if low:
            return True, "low-confidence"
    return False, ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Advisor CLI — consult at inflection.")
    ap.add_argument("--context", type=Path, required=True, help="Path to JSON context dump")
    ap.add_argument("--class", dest="inflection_class", required=True,
                    choices=list(INFLECTION_CLASSES))
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if not args.context.exists():
        print(f"error: {args.context} missing", file=sys.stderr)
        return 1

    context = json.loads(args.context.read_text(encoding="utf-8"))
    result = consult(context, args.inflection_class, model=args.model)

    if args.out:
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
