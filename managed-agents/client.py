#!/usr/bin/env python3
"""Managed Agents client helpers — shared bootstrap + IO for cogsig governance.

Uses the Claude Managed Agents public beta (header: managed-agents-2026-04-01).
The Anthropic SDK sets the beta header automatically when calling client.beta.agents
/ client.beta.environments / client.beta.sessions.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


AGENT_IDS_CACHE = ".signature-cache/managed-agents.json"
REVIEWS_DIR = ".signature-cache/reviews"


def cache_path(repo: Path) -> Path:
    return repo / AGENT_IDS_CACHE


def reviews_dir(repo: Path) -> Path:
    path = repo / REVIEWS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_cache(repo: Path) -> dict:
    path = cache_path(repo)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cache(repo: Path, data: dict) -> None:
    path = cache_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_client():
    try:
        import anthropic
    except ImportError:
        print("error: anthropic SDK not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        raise
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        raise SystemExit(2)
    return anthropic.Anthropic(api_key=api_key)


GOVERNANCE_AGENTS = {
    "signature-brutus": {
        "model": "claude-opus-4-7",
        "system": (
            "You are Signature-Brutus — adversarial reviewer for extracted cognitive signatures.\n\n"
            "Given a signature.json and the samples.json it was extracted from, review every dimension for:\n"
            "1. Does the sample set actually support the claim?\n"
            "2. Is the evidence large enough to be confident?\n"
            "3. Is contradictory evidence being ignored?\n\n"
            "For each dimension, respond:\n"
            "  DIMENSION: <name>\n"
            "  CLAIM: <what signature.json says>\n"
            "  EVIDENCE: <N samples / what they show>\n"
            "  VERDICT: CONFIRMED | WEAK | CONTRADICTED\n"
            "  RECOMMENDATION: accept | re-extract-more-samples | correct-specific-claim\n\n"
            "Do not suggest the user change their style. You describe, you don't prescribe. "
            "Do not edit any files. Your output is a review only."
        ),
    },
    "signature-qa": {
        "model": "claude-haiku-4-5-20251001",
        "system": (
            "You are Signature-QA — schema validator for cognitive signatures.\n\n"
            "Given a signature.json, verify:\n"
            "1. All 6 required dimensions present\n"
            "2. Required sub-fields per dimension\n"
            "3. Types correct (numbers numeric, enums valid)\n"
            "4. version + generated_ts + origin present\n\n"
            "Return PASS or FAIL with specific violation list. Do not attempt to repair malformed JSON — "
            "route back to extract."
        ),
    },
    "signature-historian": {
        "model": "claude-sonnet-4-6",
        "system": (
            "You are Signature-Historian — drift detector for cognitive signatures.\n\n"
            "Given a current signature and the last N entries from signature_history.jsonl, classify any "
            "changed dimension as:\n"
            "  EXPECTED — new language, new project, gradual evolution\n"
            "  UNEXPLAINED — sudden shift with no corresponding sample-source change\n"
            "  NOISE — minor fluctuation within known variance\n\n"
            "BEFORE classifying: check the origin field.\n"
            "  If origin == 'imported': all dimension changes are automatically EXPECTED (user loaded "
            "an external signature). Skip UNEXPLAINED analysis. Note team_id if present.\n"
            "  If origin == 'self': run full drift analysis.\n\n"
            "Do not modify signature.json. Read-only."
        ),
    },
}


TOOLS_CONFIG = [{"type": "agent_toolset_20260401"}]


def ensure_agents_and_env(repo: Path, force_recreate: bool = False) -> dict:
    """Create (or reuse) the 3 governance agents + shared environment.

    Returns a dict with agent IDs keyed by agent name + environment_id.
    Cached in .signature-cache/managed-agents.json.
    """
    cache = load_cache(repo)
    if cache and not force_recreate and all(
        k in cache for k in ("environment_id", "signature-brutus", "signature-qa", "signature-historian")
    ):
        return cache

    client = get_client()

    if "environment_id" not in cache or force_recreate:
        env = client.beta.environments.create(
            name="cogsig-governance-env",
            config={"type": "cloud", "networking": {"type": "unrestricted"}},
        )
        cache["environment_id"] = env.id
        cache["environment_name"] = env.name
        cache["environment_created_ts"] = datetime.now(timezone.utc).isoformat()
        print(f"created environment: {env.id}", file=sys.stderr)

    for name, spec in GOVERNANCE_AGENTS.items():
        if name in cache and not force_recreate:
            continue
        agent = client.beta.agents.create(
            name=f"CogSig {name.replace('-', ' ').title()}",
            model=spec["model"],
            system=spec["system"],
            tools=TOOLS_CONFIG,
        )
        cache[name] = {
            "id": agent.id,
            "version": agent.version,
            "model": spec["model"],
            "created_ts": datetime.now(timezone.utc).isoformat(),
        }
        print(f"created agent {name}: {agent.id}", file=sys.stderr)

    save_cache(repo, cache)
    return cache


def load_signature(repo: Path, scope: str) -> dict:
    filename = "signature.json" if scope == "default" else f"signature.{scope}.json"
    path = repo / filename
    if not path.exists():
        raise FileNotFoundError(f"signature not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_samples(repo: Path, scope: str) -> dict | None:
    filename = "samples.json" if scope == "default" else f"samples.{scope}.json"
    path = repo / ".signature-cache" / filename
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_history(repo: Path, scope: str, n: int = 5) -> list[dict]:
    filename = "signature_history.jsonl" if scope == "default" else f"signature_history.{scope}.jsonl"
    path = repo / ".signature-cache" / filename
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries[-n:]


def active_scope(repo: Path) -> str:
    state = repo / ".signature-cache" / "state.json"
    if not state.exists():
        return "default"
    try:
        return json.loads(state.read_text(encoding="utf-8")).get("active_scope", "default")
    except json.JSONDecodeError:
        return "default"
