#!/usr/bin/env python3
"""score — blind test scorer.

Two-phase workflow (terminal-agnostic):

    Phase 1 — VIEW all 10 prompts with their shuffled A/B/C outputs:
        python3 measurement/score.py --view

    Phase 2 — RECORD your picks as a comma-separated string:
        python3 measurement/score.py --picks A,C,B,A,B,C,A,C,B,A
        (use '-' for skip on any prompt, e.g. A,-,C,B,A,C,A,B,C,A)

    Interactive (TTY only — will EOFError if stdin is piped):
        python3 measurement/score.py --interactive

Shuffle is deterministic-seeded so --view order matches --picks order.
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


def shuffle_deterministic(seed: int, prompt_id: str) -> list[str]:
    rng = random.Random(f"{seed}:{prompt_id}")
    shuffled = ["baseline", "placebo", "real"]
    rng.shuffle(shuffled)
    return shuffled


def render_view(prompts: list[dict], out_dir: Path, seed: int) -> str:
    lines = [
        "# Cogsig Blind View",
        "",
        f"seed: {seed} — outputs shuffled deterministically per prompt",
        "",
        "Read each prompt's three outputs, then record your picks as:",
        "",
        "```",
        f"python3 measurement/score.py --picks A,C,B,A,B,C,A,C,B,A --seed {seed}",
        "```",
        "",
        "Use `-` for skip on any prompt.",
        "",
    ]
    for i, prompt in enumerate(prompts, 1):
        pid = prompt["id"]
        prompt_dir = out_dir / pid
        outputs = load_outputs(prompt_dir)
        if not outputs:
            lines.append(f"## {i}. {pid}\n\n_(outputs incomplete — skip)_\n")
            continue
        shuffled = shuffle_deterministic(seed, pid)
        lines.append(f"## {i}. {pid}")
        lines.append("")
        lines.append(f"> {prompt['prompt']}")
        lines.append("")
        for label, condition in zip(LABELS, shuffled):
            lines.append(f"### {label}")
            lines.append("")
            lines.append(outputs[condition])
            lines.append("")
    return "\n".join(lines)


def parse_picks_arg(picks_str: str, n_prompts: int) -> list[str | None]:
    raw = [p.strip().upper() for p in picks_str.split(",")]
    if len(raw) != n_prompts:
        raise ValueError(f"expected {n_prompts} picks, got {len(raw)}")
    parsed: list[str | None] = []
    for p in raw:
        if p in LABELS:
            parsed.append(p)
        elif p in ("-", "", "S", "SKIP"):
            parsed.append(None)
        else:
            raise ValueError(f"invalid pick '{p}' — use A / B / C / -")
    return parsed


def interactive_prompt(pid: str, shuffled: list[str], outputs: dict[str, str]) -> str | None:
    print("=" * 72)
    print(f"PROMPT: {pid}")
    print("=" * 72)
    for label, condition in zip(LABELS, shuffled):
        print(f"\n--- {label} ---")
        print(outputs[condition])
    print()
    while True:
        pick = input(f"Which is YOURS? [{'/'.join(LABELS)}] or 's' to skip: ").strip().upper()
        if pick in ("S", "SKIP", "-"):
            return None
        if pick in LABELS:
            return pick
        print(f"  invalid — enter one of {LABELS} or 's'")


def score_picks(prompts: list[dict], out_dir: Path, seed: int, picks: list[str | None]) -> dict:
    scored_picks: list[dict] = []
    correct = 0
    scored = 0

    for prompt, pick in zip(prompts, picks):
        pid = prompt["id"]
        prompt_dir = out_dir / pid
        outputs = load_outputs(prompt_dir)
        if not outputs:
            scored_picks.append({"prompt_id": pid, "pick": None, "real_label": None, "correct": None, "note": "outputs incomplete"})
            continue

        shuffled = shuffle_deterministic(seed, pid)
        real_label = LABELS[shuffled.index("real")]

        if pick is None:
            scored_picks.append({"prompt_id": pid, "pick": None, "real_label": real_label, "correct": None})
            continue

        is_correct = pick == real_label
        scored += 1
        correct += int(is_correct)
        scored_picks.append({
            "prompt_id": pid,
            "pick": pick,
            "real_label": real_label,
            "correct": is_correct,
            "shuffled_order": {label: cond for label, cond in zip(LABELS, shuffled)},
        })

    accuracy = correct / scored if scored else 0.0
    chance = 1 / 3
    return {
        "run_ts": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "scored": scored,
        "correct": correct,
        "accuracy": accuracy,
        "chance": chance,
        "delta_pp": (accuracy - chance) * 100 if scored else 0.0,
        "picks": scored_picks,
    }


def write_results_md(results: dict, path: Path) -> None:
    picks = results["picks"]
    acc = results["accuracy"]
    chance = results["chance"]
    lines = [
        "# Cogsig Blind Measurement Results",
        "",
        f"Run: {results['run_ts']}",
        f"Seed: {results['seed']}",
        "",
        "## Headline",
        "",
        f"- Prompts scored: **{results['scored']}**",
        f"- Correct picks: **{results['correct']}/{results['scored']} ({acc:.1%})**",
        f"- Chance baseline: 33.3%",
        f"- Delta over chance: **{(acc - chance) * 100:+.1f}pp**",
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
        if p.get("correct") is None:
            note = p.get("note", "skipped")
            lines.append(f"| {p['prompt_id']} | — | {p.get('real_label') or '—'} | ({note}) |")
        else:
            lines.append(f"| {p['prompt_id']} | {p['pick']} | {p['real_label']} | {'✓' if p['correct'] else '✗'} |")
    lines.append("")
    lines.append("## Reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append("export ANTHROPIC_API_KEY=sk-ant-...")
    lines.append("python3 skills/capture/capture.py")
    lines.append("python3 skills/extract/extract.py")
    lines.append("python3 measurement/blind_test.py")
    lines.append(f"python3 measurement/score.py --view       # read outputs")
    lines.append(f"python3 measurement/score.py --picks A,C,B,A,B,C,A,C,B,A --seed {results['seed']}")
    lines.append("```")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Blind-test scorer (view + record picks).")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--outputs", type=Path, default=None)
    ap.add_argument("--prompts", type=Path, default=None)
    ap.add_argument("--results", type=Path, default=None)
    ap.add_argument("--view-path", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--view", action="store_true", help="Emit blind_view.md with shuffled outputs")
    ap.add_argument("--picks", default=None, help="Comma-separated picks (A/B/C/- for skip), one per prompt")
    ap.add_argument("--interactive", action="store_true", help="Legacy interactive mode (TTY only)")
    args = ap.parse_args()

    repo = args.repo.resolve()
    prompts_path = args.prompts or (repo / "measurement" / "prompts.json")
    out_dir = args.outputs or (repo / "measurement" / "blind_outputs")
    results_path = args.results or (repo / "measurement" / "results.md")
    view_path = args.view_path or (repo / "measurement" / "blind_view.md")

    if not prompts_path.exists():
        print(f"error: {prompts_path} missing", file=sys.stderr)
        return 1
    if not out_dir.exists():
        print(f"error: {out_dir} missing — run blind_test.py first", file=sys.stderr)
        return 1

    prompts = json.loads(prompts_path.read_text(encoding="utf-8"))["prompts"]

    if args.view:
        md = render_view(prompts, out_dir, args.seed)
        view_path.write_text(md, encoding="utf-8")
        print(f"wrote {view_path}")
        print(f"read it, then record picks with:")
        print(f"  python3 measurement/score.py --picks A,C,B,A,B,C,A,C,B,A --seed {args.seed}")
        return 0

    if args.picks:
        try:
            picks = parse_picks_arg(args.picks, len(prompts))
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        results = score_picks(prompts, out_dir, args.seed, picks)
        print(f"correct: {results['correct']}/{results['scored']} ({results['accuracy']:.1%})")
        print(f"chance:  {results['chance']:.1%}")
        print(f"delta:   {results['delta_pp']:+.1f}pp over chance")
        write_results_md(results, results_path)
        (results_path.parent / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {results_path}")
        print(f"wrote {results_path.parent / 'results.json'}")
        return 0

    if args.interactive:
        picks_raw: list[str | None] = []
        for prompt in prompts:
            pid = prompt["id"]
            prompt_dir = out_dir / pid
            outputs = load_outputs(prompt_dir)
            if not outputs:
                print(f"skip {pid}: outputs incomplete", file=sys.stderr)
                picks_raw.append(None)
                continue
            shuffled = shuffle_deterministic(args.seed, pid)
            picks_raw.append(interactive_prompt(pid, shuffled, outputs))
        results = score_picks(prompts, out_dir, args.seed, picks_raw)
        write_results_md(results, results_path)
        (results_path.parent / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\ncorrect: {results['correct']}/{results['scored']} ({results['accuracy']:.1%})")
        print(f"wrote {results_path}")
        return 0

    print("usage: pick one of --view / --picks / --interactive", file=sys.stderr)
    print("  python3 measurement/score.py --view                              # emit blind_view.md", file=sys.stderr)
    print("  python3 measurement/score.py --picks A,C,B,A,B,C,A,C,B,A         # record + score", file=sys.stderr)
    print("  python3 measurement/score.py --interactive                        # TTY prompt (will EOFError if stdin piped)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
