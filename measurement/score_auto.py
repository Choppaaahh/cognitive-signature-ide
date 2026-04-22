#!/usr/bin/env python3
"""score_auto — auto-scorer for the 3-condition blind test using Claude-as-judge.

For each prompt:
  - Read the 3 shuffled outputs (baseline / placebo / real)
  - Read the signature.json the 'real' condition was generated under
  - Ask Claude (a different conversation than the generator) to predict
    which output was produced WITH the signature injected
  - Compare prediction to ground truth
  - Report per-prompt accuracy + aggregate vs 33% chance baseline

Complementary to the user-subjective blind test (score.py). This produces
an objective-automated accuracy number that doesn't require human scoring.
Both results can coexist in results.md.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 measurement/score_auto.py [--repo PATH] [--signature PATH]
                                       [--outputs PATH] [--prompts PATH]
                                       [--seed N] [--model claude-opus-4-7]
                                       [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path


MODEL_DEFAULT = "claude-opus-4-7"
LABELS = ["A", "B", "C"]


JUDGE_PROMPT_TEMPLATE = """You are the Judge in a blind test. One of three outputs was produced by Claude with a specific cognitive-signature injected into its context; the other two are controls (no-signature baseline, and a placebo-signature with deliberately wrong traits).

Your job: read the signature below and predict which output (A, B, or C) was produced with THIS SIGNATURE actively injected.

SIGNATURE (the real signature used for the 'real' condition):

{signature}

PROMPT THAT WAS GIVEN TO ALL THREE CLAUDES:
{prompt}

OUTPUTS (shuffled — one is real, two are controls):

=== A ===
{output_a}

=== B ===
{output_b}

=== C ===
{output_c}

Respond in strict JSON (no markdown, no preamble):

{{
  "prediction": "A" | "B" | "C",
  "confidence": <0.0-1.0>,
  "reasoning": "<1-2 sentences on what signature traits you saw (or missed) in the chosen output>"
}}
"""


def load_outputs(prompt_dir: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for cond in ("baseline", "placebo", "real"):
        path = prompt_dir / f"{cond}.md"
        if not path.exists():
            return {}
        outputs[cond] = path.read_text(encoding="utf-8")
    return outputs


def shuffle_deterministic(seed: int, prompt_id: str) -> list[str]:
    rng = random.Random(f"{seed}:{prompt_id}")
    shuffled = ["baseline", "placebo", "real"]
    rng.shuffle(shuffled)
    return shuffled


def parse_judge_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    return json.loads(text)


def judge_prompt(client, model: str, signature: dict, prompt_text: str, outputs_in_order: list[str]) -> dict:
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        signature=json.dumps(signature, indent=2),
        prompt=prompt_text,
        output_a=outputs_in_order[0][:3000],
        output_b=outputs_in_order[1][:3000],
        output_c=outputs_in_order[2][:3000],
    )
    response = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    return parse_judge_response(text)


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-scorer (Claude-as-judge) for the 3-condition blind test.")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--signature", type=Path, default=None)
    ap.add_argument("--outputs", type=Path, default=None)
    ap.add_argument("--prompts", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--out", type=Path, default=None)
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
    signature_path = args.signature or (repo / "signature.json")
    outputs_dir = args.outputs or (repo / "measurement" / "blind_outputs")
    prompts_path = args.prompts or (repo / "measurement" / "prompts.json")
    out_path = args.out or (repo / "measurement" / "results_auto.json")

    if not signature_path.exists():
        print(f"error: {signature_path} missing — run capture + extract first", file=sys.stderr)
        return 1
    if not outputs_dir.exists():
        print(f"error: {outputs_dir} missing — run blind_test.py first", file=sys.stderr)
        return 1
    if not prompts_path.exists():
        print(f"error: {prompts_path} missing", file=sys.stderr)
        return 1

    signature = json.loads(signature_path.read_text(encoding="utf-8"))
    prompts = json.loads(prompts_path.read_text(encoding="utf-8"))["prompts"]
    client = anthropic.Anthropic(api_key=api_key)

    scored: list[dict] = []
    correct = 0
    total = 0

    for i, prompt in enumerate(prompts, 1):
        pid = prompt["id"]
        prompt_text = prompt["prompt"]
        prompt_dir = outputs_dir / pid
        outputs = load_outputs(prompt_dir)
        if not outputs:
            print(f"[{i}/{len(prompts)}] skip {pid}: outputs incomplete", file=sys.stderr)
            continue

        shuffled = shuffle_deterministic(args.seed, pid)
        real_label = LABELS[shuffled.index("real")]
        outputs_in_order = [outputs[shuffled[0]], outputs[shuffled[1]], outputs[shuffled[2]]]

        print(f"[{i}/{len(prompts)}] {pid}: judging...", file=sys.stderr)
        try:
            verdict = judge_prompt(client, args.model, signature, prompt_text, outputs_in_order)
        except Exception as e:
            print(f"[{i}/{len(prompts)}] {pid}: JUDGE ERROR — {e}", file=sys.stderr)
            scored.append({
                "prompt_id": pid,
                "prediction": None,
                "real_label": real_label,
                "correct": None,
                "error": str(e),
            })
            continue

        pred = verdict.get("prediction")
        is_correct = pred == real_label
        total += 1
        correct += int(is_correct)
        scored.append({
            "prompt_id": pid,
            "prediction": pred,
            "real_label": real_label,
            "correct": is_correct,
            "confidence": verdict.get("confidence"),
            "reasoning": verdict.get("reasoning"),
            "shuffled_order": {label: cond for label, cond in zip(LABELS, shuffled)},
        })
        marker = "✓" if is_correct else "✗"
        print(f"[{i}/{len(prompts)}] {pid}: predicted {pred}, real {real_label} {marker}  conf={verdict.get('confidence')}", file=sys.stderr)

    accuracy = correct / total if total else 0.0
    chance = 1 / 3
    results = {
        "run_ts": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "model": args.model,
        "scored": total,
        "correct": correct,
        "accuracy": accuracy,
        "chance": chance,
        "delta_pp": (accuracy - chance) * 100 if total else 0.0,
        "signature_version": signature.get("version"),
        "signature_generated_ts": signature.get("generated_ts"),
        "signature_domain": signature.get("domain"),
        "picks": scored,
    }

    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\ncorrect: {correct}/{total} ({accuracy:.1%})")
    print(f"chance:  {chance:.1%}")
    print(f"delta:   {results['delta_pp']:+.1f}pp over chance")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
