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

PROMPT_CODE = """You are analyzing code samples to extract the author's coding signature — a structured description of HOW they write code, not WHAT the code does.

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


PROMPT_DIRECTING = """You are analyzing raw user-typed directives — messages the user typed TO an LLM during dialogue — to extract the user's DIRECTING signature. You describe HOW the user directs / thinks-with AI systems, NOT what the AI produced in response. The samples are the user's contribution only. The model's responses are NOT included; infer nothing about them.

You will output valid JSON matching this schema:

{schema}

Analyze the samples below and return ONLY the JSON object. No markdown, no commentary, just the raw JSON starting with {{ and ending with }}.

Focus on descriptive, not prescriptive — you are describing the user's directing style, not evaluating it.

Key things to look for:
  - directive_style: are they command-heavy, question-heavy, hunch-first? Terse or verbose? Data-first or gut-first?
  - reframe_pattern: do they challenge the frame (e.g. "wait but", "hmmmm", "hold on")? Frequency and shape of reframes.
  - trust_mechanics: what phrases signal extending autonomy ("cook it," "go for it," "you decide") vs retracting it ("hold on," "show me first," "wait but what about")?
  - idiomatic_tells: casual markers ("bro", "buddy", "laddy"), openings ("yessur", "hellyea"), closings ("lmao", "noice"), specific vocabulary signature, punctuation habits, capitalization pattern.
  - iteration_cadence: how do they layer thinking across turns? What's the typical arc ("hunch → data → reframe → converge")? How many turns to converge? Do they hold parallel structures (multiple ideas simultaneously)?
  - compression_ratio: typical length of their directives (avg chars). What do they expect back — short answer, matched-length, full analysis?
  - texture_energy: baseline mood markers. "lmaoo", "hellyea" = high; "hmmmm", "hang on" = thoughtful; capitalization for emphasis; humor signature.

For confidence scores:
  - 0.8-1.0: strong, consistent evidence across many directives
  - 0.5-0.8: visible pattern but with variance
  - below 0.5: weak or too-small sample
For idiomatic_tells specifically, list ACTUAL phrases observed in the samples — not generic descriptions.

SAMPLES ({sample_count} total user-directives, from dialogue corpus):

{samples}

Return the signature JSON now."""


PROMPT_OPERATIONAL = """You are analyzing raw user-typed directives to extract the user's OPERATIONAL signature — WHAT THEY'VE LEARNED through usage. NOT how they direct (voice signature handles that). Operational signature captures recurring CONTENT patterns: recurring decision templates, failure modes they've encountered and flag, specific tools they invoke repeatedly, and project-specific vocabulary anchors.

You will output valid JSON matching this schema:

{schema}

Analyze the samples below and return ONLY the JSON object. No markdown, no commentary, just the raw JSON starting with {{ and ending with }}.

Key extraction principles:
  - RECURRING, not one-off. If a pattern appears only once, it's not a signature pattern — skip.
  - CONTENT, not style. Voice signature captures idiomatic tells / compression ratio / capitalization. Operational captures "what they said, repeatedly."
  - EVIDENCE-LINKED. Every item must include `instance_count` (int, count of distinct instances in samples) + `evidence_list` (array of short direct quotes from the samples supporting this pattern). No item may have instance_count=0 or evidence_list=[].
  - CONSERVATIVE. Prefer missing a pattern to hallucinating one. Do not infer patterns from absence.
  - OBJECTIVE COUNTING. instance_count is a count you can defend — each instance in evidence_list is one count.
  - SEPARATE FROM VOICE. If a pattern is stylistic (how they talk), not operational (what they return to), skip it.

Per-dimension guidance:
  - recurring_decision_templates: situation → response mappings. "When facing X, user does Y." The situation + the response are both content, not style.
  - recurring_failure_patterns: known failure modes mentioned in context of encountering / flagging them. "The X thing tends to break when..." Must be grounded in explicit mentions, not inferred.
  - recurring_tooling_invocations: named tool/command/flag invocations. "Always runs git log before Y", "uses vault_search with --top 5 for Z." The tool must be NAMED (not "some CLI command").
  - vocabulary_anchors: project-specific terminology, domain vocabulary, recurring named entities. Examples of valid anchors: "scaffold", "breadcrumb", "n=2 threshold", "Managed Agents", proper nouns from user's domain. NOT idiomatic tells (voice captures those — e.g. "lmao", "hellyea").

For confidence scores per dimension:
  - 0.8-1.0: multiple clear patterns, each with 3+ evidence instances
  - 0.5-0.8: some patterns with 2+ instances
  - below 0.5: thin evidence — include dimension with low confidence + explain in notes

If a dimension has zero qualifying patterns, return an empty array for that dimension's list field with confidence 0.3 and a note.

SAMPLES ({sample_count} total user-directives, from dialogue corpus):

{samples}

Return the operational signature JSON now."""


def format_samples_code(samples: list[dict], max_per_sample: int = 1500) -> str:
    blocks: list[str] = []
    for i, s in enumerate(samples, 1):
        content = s["content"][:max_per_sample]
        blocks.append(
            f"--- Sample {i}: {s['path']} ({s['language']}, {s['line_count']} lines) ---\n{content}"
        )
    return "\n\n".join(blocks)


def format_samples_directing(samples: list[dict], max_per_sample: int = 800) -> str:
    blocks: list[str] = []
    for i, s in enumerate(samples, 1):
        content = s["content"][:max_per_sample].strip()
        meta = s.get("meta", "")
        blocks.append(f"--- Directive {i} {f'({meta})' if meta else ''} ---\n{content}")
    return "\n\n".join(blocks)


def format_samples(samples: list[dict], domain: str = "code") -> str:
    # Both directing and operational domains ingest dialogue corpora
    # with identical row shape (content + meta fields). Code domain
    # uses path/language/line_count.
    if domain in ("directing", "operational"):
        return format_samples_directing(samples)
    return format_samples_code(samples)


def extract(samples_path: Path, schema_path: Path, model: str, domain: str = "code") -> dict:
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

    if domain == "directing":
        template = PROMPT_DIRECTING
    elif domain == "operational":
        template = PROMPT_OPERATIONAL
    else:
        template = PROMPT_CODE
    prompt = template.format(
        schema=json.dumps(schema, indent=2),
        sample_count=samples_doc["sample_count"],
        languages=", ".join(samples_doc.get("languages", [])) or "dialogue",
        samples=format_samples(samples_doc["samples"], domain=domain),
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()
    if not text:
        print("error: Opus returned no text content — check API key / model availability", file=sys.stderr)
        raise SystemExit(2)
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()

    try:
        signature = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"error: Opus returned non-JSON response (likely truncated at max_tokens or refused): {e}", file=sys.stderr)
        print(f"       first 300 chars: {text[:300]}", file=sys.stderr)
        print(f"       retry with a smaller --max-samples or re-run", file=sys.stderr)
        raise SystemExit(2)
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


def _load_advisor():
    """Lazy-import advisor module; returns (consult, should_consult) or (None, None) if unavailable."""
    try:
        advisor_dir = Path(__file__).resolve().parent.parent / "advisor"
        sys.path.insert(0, str(advisor_dir))
        from advisor import consult, should_consult  # type: ignore
        return consult, should_consult
    except ImportError:
        return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Call Opus 4.7 on samples → signature.json")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--domain", choices=["code", "directing", "operational"], default="code",
                    help="Signature domain. 'code' = coding (Functionality 1 legacy). 'directing' = voice signature (Functionality 1). 'operational' = recurring operational patterns (Functionality 2).")
    ap.add_argument("--scope-name", default="default", help="Signature scope label")
    ap.add_argument("--samples", type=Path, default=None)
    ap.add_argument("--schema", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--advisor", choices=["auto", "always", "off"], default="auto",
                    help="Advisor consultation: auto (on inflection), always (every run), off (never).")
    ap.add_argument("--advisor-threshold", type=float, default=0.5,
                    help="Confidence threshold below which advisor is consulted in auto mode.")
    args = ap.parse_args()

    repo = args.repo.resolve()
    samples_path = args.samples or samples_path_for_scope(repo, args.scope_name)
    if args.domain == "directing":
        schema_name = "signature_schema_directing.json"
    elif args.domain == "operational":
        schema_name = "signature_schema_operational.json"
    else:
        schema_name = "signature_schema.json"
    # Schema files live next to extract.py (plugin-install dir), not under --repo.
    # --repo controls WRITE location; schemas are static plugin assets.
    plugin_extract_dir = Path(__file__).resolve().parent
    schema_path = args.schema or (plugin_extract_dir / schema_name)
    out_path = args.out or signature_path_for_scope(repo, args.scope_name)
    history_path = repo / ".signature-cache" / ("signature_history.jsonl" if args.scope_name == "default" else f"signature_history.{args.scope_name}.jsonl")
    advisor_dir = repo / ".signature-cache" / "advisor_reports"

    if not samples_path.exists():
        print(f"error: {samples_path} missing — run capture first", file=sys.stderr)
        return 1
    if not schema_path.exists():
        print(f"error: {schema_path} missing", file=sys.stderr)
        return 1

    signature = extract(samples_path, schema_path, args.model, domain=args.domain)
    signature["domain"] = args.domain
    if args.scope_name != "default":
        signature["scope"] = args.scope_name
    errors = validate(signature, schema_path)
    if errors:
        print("validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("(signature still written; route to Signature-QA for review)", file=sys.stderr)

    advisor_report = None
    if args.advisor != "off":
        consult, should_consult = _load_advisor()
        if consult is None:
            print("warn: advisor module unavailable; skipping", file=sys.stderr)
        else:
            if args.advisor == "always":
                trigger, inflection_class = True, "manual"
            else:
                trigger, inflection_class = should_consult(signature, errors, threshold=args.advisor_threshold)
            if trigger:
                samples_doc = json.loads(samples_path.read_text(encoding="utf-8"))
                low_conf = [n for n, v in signature.get("dimensions", {}).items()
                            if isinstance(v, dict) and isinstance(v.get("confidence"), (int, float))
                            and v["confidence"] < args.advisor_threshold]
                context = {
                    "signature": signature,
                    "samples_summary": f"{samples_doc.get('sample_count', '?')} samples, "
                                       f"scope={samples_doc.get('scope', 'default')}, "
                                       f"domain={args.domain}, languages={samples_doc.get('languages', [])}",
                    "low_confidence_dimensions": low_conf,
                    "validation_errors": errors,
                }
                print(f"\n* advisor consulted (class: {inflection_class}) *", file=sys.stderr)
                try:
                    advisor_report = consult(context, inflection_class, model=args.model)
                    advisor_dir.mkdir(parents=True, exist_ok=True)
                    stamp = advisor_report.get("consulted_ts", datetime.now(timezone.utc).isoformat()).replace(":", "").replace("-", "")[:15]
                    advisor_out = advisor_dir / f"advisor-{args.scope_name}-{stamp}.json"
                    advisor_out.write_text(json.dumps(advisor_report, indent=2), encoding="utf-8")
                    signature["_advisor_consulted"] = {
                        "inflection_class": inflection_class,
                        "report_path": str(advisor_out.relative_to(repo)),
                        "reframe": advisor_report.get("reframe"),
                        "suggested_action": advisor_report.get("suggested_action"),
                    }
                except Exception as e:
                    print(f"warn: advisor call failed: {e}", file=sys.stderr)

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
    if advisor_report:
        print("--- advisor reframe ---")
        print(f"  reframe: {advisor_report.get('reframe')}")
        print(f"  suggested action: {advisor_report.get('suggested_action')}")
        print(f"  diagnosis: {advisor_report.get('diagnosis')}")

    return 0 if not errors else 3


if __name__ == "__main__":
    raise SystemExit(main())
