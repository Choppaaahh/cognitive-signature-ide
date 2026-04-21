#!/usr/bin/env python3
"""Run the 3 governance agents (Brutus, QA, Historian) on a cognitive signature.

Each agent runs as a Claude Managed Agents session. Reviews are streamed back and
written to .signature-cache/reviews/<timestamp>.json.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 managed-agents/review.py [--repo PATH] [--scope-name NAME] [--force-recreate]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client import (  # type: ignore
    active_scope,
    ensure_agents_and_env,
    get_client,
    load_history,
    load_samples,
    load_signature,
    reviews_dir,
)


def build_brutus_prompt(signature: dict, samples: dict | None) -> str:
    lines = [
        "Review the following cognitive signature against the source samples.",
        "",
        "SIGNATURE:",
        json.dumps(signature, indent=2),
        "",
    ]
    if samples:
        lines.append(f"SAMPLES ({samples['sample_count']} total):")
        for i, s in enumerate(samples.get("samples", []), 1):
            lines.append(f"--- Sample {i}: {s['path']} ({s['language']}, {s['line_count']}L) ---")
            lines.append(s["content"][:1500])
            lines.append("")
    else:
        lines.append("(no samples available — review signature internal consistency only)")

    lines.append("Respond with your structured review per your system prompt.")
    return "\n".join(lines)


def build_qa_prompt(signature: dict) -> str:
    return (
        "Validate the following cognitive signature against its schema (6 required dimensions, "
        "typed sub-fields, confidence 0-1, origin enum, etc).\n\n"
        "SIGNATURE:\n"
        f"{json.dumps(signature, indent=2)}\n\n"
        "Return PASS or FAIL with violations per your system prompt."
    )


def build_historian_prompt(signature: dict, history: list[dict]) -> str:
    lines = [
        "Classify drift between the current cognitive signature and recent history.",
        "",
        "CURRENT SIGNATURE:",
        json.dumps(signature, indent=2),
        "",
    ]
    if history:
        lines.append(f"RECENT HISTORY ({len(history)} entries, oldest first):")
        for i, entry in enumerate(history, 1):
            lines.append(f"--- history entry {i} (generated {entry.get('generated_ts', '?')}, origin {entry.get('origin', '?')}) ---")
            lines.append(json.dumps(entry.get("dimensions", {}), indent=2))
            lines.append("")
    else:
        lines.append("(no prior history — this is the first signature for this scope)")
    lines.append("Produce your drift report per your system prompt.")
    return "\n".join(lines)


def run_agent_session(client, agent_id: str, environment_id: str, title: str, prompt: str) -> str:
    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=environment_id,
        title=title,
    )
    collected: list[str] = []
    tool_uses: list[str] = []

    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": prompt}],
                },
            ],
        )
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    text = getattr(block, "text", None)
                    if text:
                        collected.append(text)
            elif event.type == "agent.tool_use":
                tool_uses.append(getattr(event, "name", "unknown"))
            elif event.type == "session.status_idle":
                break

    return "".join(collected), tool_uses, session.id


def main() -> int:
    ap = argparse.ArgumentParser(description="Run governance review on a cognitive signature via Managed Agents.")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--scope-name", default=None)
    ap.add_argument("--force-recreate", action="store_true", help="Recreate Managed Agents + environment")
    args = ap.parse_args()

    repo = args.repo.resolve()
    scope = args.scope_name or active_scope(repo)

    try:
        signature = load_signature(repo, scope)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    samples = load_samples(repo, scope)
    history = load_history(repo, scope, n=5)

    print(f"reviewing signature for scope '{scope}' (origin: {signature.get('origin', '?')})", file=sys.stderr)

    cache = ensure_agents_and_env(repo, force_recreate=args.force_recreate)
    env_id = cache["environment_id"]
    client = get_client()

    prompts = {
        "signature-brutus": build_brutus_prompt(signature, samples),
        "signature-qa": build_qa_prompt(signature),
        "signature-historian": build_historian_prompt(signature, history),
    }

    review = {
        "run_ts": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "signature_version": signature.get("version"),
        "signature_generated_ts": signature.get("generated_ts"),
        "origin": signature.get("origin"),
        "reviews": {},
    }

    for agent_name, prompt in prompts.items():
        agent_id = cache[agent_name]["id"]
        print(f"  {agent_name}: running...", file=sys.stderr)
        text, tool_uses, session_id = run_agent_session(
            client,
            agent_id=agent_id,
            environment_id=env_id,
            title=f"CogSig {agent_name} review ({scope} / {signature.get('generated_ts', '?')[:19]})",
            prompt=prompt,
        )
        review["reviews"][agent_name] = {
            "session_id": session_id,
            "tool_uses": tool_uses,
            "response": text,
        }
        print(f"  {agent_name}: done ({len(text)} chars)", file=sys.stderr)

    out_dir = reviews_dir(repo)
    stamp = review["run_ts"].replace(":", "").replace("-", "")[:15]
    out_path = out_dir / f"review-{scope}-{stamp}.json"
    out_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
    print(f"\nwrote review to {out_path}", file=sys.stderr)

    print("\n=== REVIEW SUMMARY ===")
    for name, data in review["reviews"].items():
        print(f"\n--- {name} ---")
        print(data["response"][:1500])
        if len(data["response"]) > 1500:
            print(f"... ({len(data['response']) - 1500} more chars in {out_path.name})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
