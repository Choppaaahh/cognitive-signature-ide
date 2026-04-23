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
    active_mode,
    active_scope,
    ensure_agents_and_env,
    get_client,
    load_history,
    load_samples,
    load_signature,
    memory_resources_for,
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


def run_agent_session(
    client,
    agent_id: str,
    environment_id: str,
    title: str,
    prompt: str,
    resources: list[dict] | None = None,
) -> tuple[str, list[str], str]:
    create_kwargs: dict = {
        "agent": agent_id,
        "environment_id": environment_id,
        "title": title,
    }
    if resources:
        create_kwargs["resources"] = resources
    session = client.beta.sessions.create(**create_kwargs)
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
    ap.add_argument(
        "--with-memory",
        action="store_true",
        help="Attach per-agent memory stores (Managed Agents memory beta). "
             "Auto-enabled when active_mode == 'cloud'. Stores persist across "
             "sessions so Brutus/QA/Historian compound prior findings.",
    )
    ap.add_argument(
        "--no-memory",
        action="store_true",
        help="Skip memory-store attachment even if active_mode == 'cloud'. Useful for diagnostic runs.",
    )
    args = ap.parse_args()

    repo = args.repo.resolve()
    scope = args.scope_name or active_scope(repo)
    mode = active_mode(repo)

    # Memory is attached by default in cloud mode. CLI flags override:
    # --with-memory forces on; --no-memory forces off. --no-memory wins ties.
    # QA caught: enforce cloud-mode contract in code, not just docs. If a user
    # runs --with-memory in team/standalone mode, warn + downgrade rather than
    # silently provision memory stores that violate the README cloud-only promise.
    use_memory = (args.with_memory or mode == "cloud") and not args.no_memory
    if use_memory and mode != "cloud":
        print(
            f"warning: --with-memory requested but active_mode={mode!r} "
            f"(not 'cloud'); memory is cloud-only per README contract. "
            f"Downgrading to --no-memory. Switch via '/cogsig mode cloud' "
            f"to enable.",
            file=sys.stderr,
        )
        use_memory = False

    try:
        signature = load_signature(repo, scope)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    samples = load_samples(repo, scope)
    history = load_history(repo, scope, n=5)

    print(
        f"reviewing signature for scope '{scope}' "
        f"(origin: {signature.get('origin', '?')}, mode: {mode}, memory: {'on' if use_memory else 'off'})",
        file=sys.stderr,
    )

    cache = ensure_agents_and_env(repo, force_recreate=args.force_recreate, with_memory=use_memory)
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
        "active_mode": mode,
        "memory_enabled": use_memory,
        "signature_version": signature.get("version"),
        "signature_generated_ts": signature.get("generated_ts"),
        "origin": signature.get("origin"),
        "reviews": {},
    }

    for agent_name, prompt in prompts.items():
        agent_id = cache[agent_name]["id"]
        resources = memory_resources_for(cache, agent_name) if use_memory else []
        memtag = f" [memory:{resources[0]['memory_store_id']}]" if resources else ""
        print(f"  {agent_name}: running...{memtag}", file=sys.stderr)
        try:
            text, tool_uses, session_id = run_agent_session(
                client,
                agent_id=agent_id,
                environment_id=env_id,
                title=f"CogSig {agent_name} review ({scope} / {signature.get('generated_ts', '?')[:19]})",
                prompt=prompt,
                resources=resources or None,
            )
            review["reviews"][agent_name] = {
                "session_id": session_id,
                "tool_uses": tool_uses,
                "response": text,
                "memory_store_id": (resources[0]["memory_store_id"] if resources else None),
            }
            print(f"  {agent_name}: done ({len(text)} chars)", file=sys.stderr)
        except Exception as e:
            review["reviews"][agent_name] = {
                "session_id": None,
                "tool_uses": [],  # QA caught: must match success-path list type for downstream iteration safety
                "response": f"[error] {type(e).__name__}: {e}",
                "error": True,
            }
            print(f"  {agent_name}: FAILED ({type(e).__name__}) — continuing with remaining agents", file=sys.stderr)

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
