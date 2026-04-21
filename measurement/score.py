#!/usr/bin/env python3
"""score — interactive blind test. Presents three shuffled outputs per prompt and
asks the author to pick which is theirs. Records accuracy vs chance (33%).

Usage:
    python3 measurement/score.py [--repo PATH] [--seed N]

Reads measurement/blind_outputs/<prompt-id>/{baseline,placebo,real}.md and
writes measurement/results.md with per-prompt picks + aggregate score.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path


LABELS = ["A", "B", "C"]


def load_outputs(prompt_dir: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for cond in ("baseline", "placebo", "real"):
        path = prompt_dir / f"{cond}.md"
        if not path.exists():
            return {}
        outputs[cond] = path.read_text(encoding="utf-8")
    return outputs


def shuffle_deterministic(conditions: list[str], seed: int, prompt_id: str) -> list[str]:
    rng = random.Random(f"{seed}:{prompt_id}")
    shuffled = conditions[:]
    rng.shuffle(shuffled)
    return shuffled


def prompt_user_pick(prompt_id: str, shuffled: list[str], outputs: dict[str, str]) -> str:
    print("=" * 72)
    print(f"PROMPT: {prompt_id}")
    print("=" * 72)
    for label, condition in zip(LABELS, shuffled):
        print(f"\n--- {label} ---")
        print(outputs[condition])
    print()
    while True:
        pick = input(f"Which is YOURS? [{'/'.join(LABELS)}] or 's' to skip: ").strip().upper()
        if pick == "S":
            return ""
        if pick in LABELS:
            return pick
        print(f"  invalid — enter one of {LABELS} or 's'")


def main() -> int:
    ap = argparse.ArgumentParser(description="Interactive blind-test scorer.")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--prompts", type=Path, default=None)
    ap.add_argument("--outputs", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--results", type=Path, default=None)
    args = ap.parse_args()

    repo = args.repo.resolve()
    prompts_path = args.prompts or (repo / "measurement" / "prompts.json")
    out_dir = args.outputs or (repo / "measurement" / "blind_outputs")
    results_path = args.results or (repo / "measurement" / "results.md")

    if not prompts_path.exists():
        print(f"error: {prompts_path} missing", file=sys.stderr)
        return 1
    if not out_dir.exists():
        print(f"error: {out_dir} missing — run blind_test.py first", file=sys.stderr)
        return 1

    prompts = json.loads(prompts_path.read_text(encoding="utf-8"))["prompts"]
    picks: list[dict] = []
    correct = 0
    scored = 0

    for prompt in prompts:
        pid = prompt["id"]
        prompt_dir = out_dir / pid
        outputs = load_outputs(prompt_dir)
        if not outputs:
            print(f"skip {pid}: outputs incomplete", file=sys.stderr)
            continue

        conditions = ["baseline", "placebo", "real"]
        shuffled = shuffle_deterministic(conditions, args.seed, pid)
        real_label = LABELS[shuffled.index("real")]

        pick = prompt_user_pick(pid, shuffled, outputs)
        if not pick:
            picks.append({"prompt_id": pid, "pick": None, "real_label": real_label, "correct": None})
            continue

        is_correct = pick == real_label
        scored += 1
        correct += int(is_correct)
        picks.append({
            "prompt_id": pid,
            "pick": pick,
            "real_label": real_label,
            "correct": is_correct,
            "shuffled_order": {label: cond for label, cond in zip(LABELS, shuffled)},
        })
        print(f"  -> {'CORRECT' if is_correct else 'WRONG'} (real was {real_label})\n")

    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)
    if scored == 0:
        print("no prompts scored")
        return 1
    accuracy = correct / scored
    chance = 1 / 3
    print(f"correct: {correct}/{scored} ({accuracy:.1%})")
    print(f"chance:  {chance:.1%}")
    print(f"delta:   {(accuracy - chance) * 100:+.1f}pp over chance")

    results = {
        "run_ts": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "scored": scored,
        "correct": correct,
        "accuracy": accuracy,
        "chance": chance,
        "delta_pp": (accuracy - chance) * 100,
        "picks": picks,
    }

    md_lines = [
        f"# Cogsig Blind Measurement Results",
        "",
        f"Run: {results['run_ts']}",
        f"Seed: {args.seed}",
        "",
        "## Headline",
        "",
        f"- Prompts scored: **{scored}**",
        f"- Correct picks: **{correct}/{scored} ({accuracy:.1%})**",
        f"- Chance baseline: 33.3%",
        f"- Delta over chance: **{(accuracy - chance) * 100:+.1f}pp**",
        "",
        "## What this measures",
        "",
        "Each prompt was answered by Claude under three conditions — no signature injected (baseline), a plausible-but-fake placebo signature, and the user's real extracted signature. The three outputs were shuffled and presented without labels. The author then picked which output looked most like code they would have written.",
        "",
        "An accuracy significantly above 33% is evidence that the cognitive signature actually shifts Claude's output toward the user's voice — otherwise the three outputs would be indistinguishable.",
        "",
        "## Per-prompt picks",
        "",
        "| Prompt | Pick | Real was | Correct |",
        "|--------|------|----------|---------|",
    ]
    for p in picks:
        if p["correct"] is None:
            md_lines.append(f"| {p['prompt_id']} | — | {p['real_label']} | (skipped) |")
        else:
            md_lines.append(
                f"| {p['prompt_id']} | {p['pick']} | {p['real_label']} | {'✓' if p['correct'] else '✗'} |"
            )

    md_lines.append("")
    md_lines.append("## Reproduce")
    md_lines.append("")
    md_lines.append("```bash")
    md_lines.append("export ANTHROPIC_API_KEY=sk-ant-...")
    md_lines.append("python3 skills/capture/capture.py")
    md_lines.append("python3 skills/extract/extract.py")
    md_lines.append("python3 measurement/blind_test.py")
    md_lines.append(f"python3 measurement/score.py --seed {args.seed}")
    md_lines.append("```")

    results_path.write_text("\n".join(md_lines), encoding="utf-8")
    (results_path.parent / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"\nwrote {results_path}")
    print(f"wrote {results_path.parent / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
