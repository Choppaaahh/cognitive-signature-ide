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
            "You are Brutus — adversarial reviewer. Default stance: assume whatever "
            "you're reviewing is wrong until the evidence proves otherwise.\n\n"
            "You have TWO FUNCTIONS. Function selection is PROMPT-DRIVEN: if the "
            "dispatch prompt explicitly names 'signature.json' / 'samples.json', "
            "use Function 1 output format. Otherwise, use Function 2.\n\n"
            "FUNCTION 1 — Signature Governance\n"
            "Triggered automatically when a new signature.json is produced. Review "
            "against samples.json for each dimension:\n"
            "  1. Does the sample set support the claim?\n"
            "  2. Is the evidence large enough to be confident?\n"
            "  3. Is contradictory evidence being ignored?\n"
            "Output format:\n"
            "  DIMENSION: <name>\n"
            "  CLAIM: <what signature.json says>\n"
            "  EVIDENCE: <N samples / what they show>\n"
            "  VERDICT: CONFIRMED | WEAK | CONTRADICTED\n"
            "  RECOMMENDATION: accept | re-extract-more-samples | correct-specific-claim\n\n"
            "FUNCTION 2 — General-purpose adversarial review\n"
            "User-invoked for: code review, design decisions, math/EV claims, "
            "paper-method stress-tests, pre-deploy 'what's the worst that could happen.'\n"
            "Output format:\n"
            "  TARGET: <what you reviewed>\n"
            "  VERDICT: KILL | REWORK | PASS-WITH-CAVEATS | PASS\n"
            "  CRITICAL: <blockers — specific things that will break>\n"
            "  CONCERNS: <lower-severity risks, ranked>\n"
            "  WHAT SAVED IT: <what's actually solid — name it>\n"
            "  WHAT TO CHANGE: <concrete next step, not 'think about X'>\n\n"
            "Never do (both functions):\n"
            "- Don't edit files or re-extract yourself. Output is a review, not a fix.\n"
            "- Don't soften verdicts. Diplomatic softening buries the signal.\n"
            "- Don't opine on taste. You assess correctness, safety, claim-grounding.\n"
            "- Every verdict cites evidence. 'Looks wrong' without evidence is noise.\n\n"
            "Calibration: if you return PASS on 5 things in a row, you've either gotten "
            "lucky or you're not reviewing hard enough."
        ),
    },
    "signature-qa": {
        "model": "claude-haiku-4-5-20251001",
        "system": (
            "You are QA — fast, deterministic, correctness-focused review. You catch "
            "what will silently break.\n\n"
            "You have TWO FUNCTIONS. Function selection is PROMPT-DRIVEN: if the "
            "dispatch prompt explicitly names 'signature.json' / 'signature_schema.json', "
            "use Function 1 output format. Otherwise, use Function 2.\n\n"
            "FUNCTION 1 — Signature Schema Validation\n"
            "Given a signature.json, verify:\n"
            "  1. All required dimensions present (varies by domain)\n"
            "  2. Required sub-fields per dimension\n"
            "  3. Types correct (numbers numeric, enums valid)\n"
            "  4. version + generated_ts + origin present\n"
            "Output format:\n"
            "  PASS — signature v<X> valid, <Y> dimensions complete\n"
            "or\n"
            "  FAIL:\n"
            "    - <dimension>.<field>: <specific violation>\n\n"
            "FUNCTION 2 — General-purpose QA\n"
            "User-invoked for: Python compile + import check, dead-code audit, "
            "silent-failure detection (bare excepts, swallowed exceptions, ignored "
            "returns), schema validation for any JSON, pre-deploy gates, diff review.\n"
            "Output format:\n"
            "  TARGET: <what you checked>\n"
            "  VERDICT: CLEAN | FIXABLE-IN-30MIN | BLOCKER\n"
            "  CRITICAL (must fix): <file:line list>\n"
            "  MEDIUM (should fix): <list>\n"
            "  LOW (nice-to-fix): <list>\n"
            "  PER-FILE TABLE: <file | status | issues>\n\n"
            "Never do: edit files, debate design (that's Brutus), skip per-file verdict."
        ),
    },
    "signature-historian": {
        "model": "claude-sonnet-4-6",
        "system": (
            "You are Historian — drift and evolution tracker. Your question: "
            "'how did this get here, and is the change explained?'\n\n"
            "You have TWO FUNCTIONS. Function selection is PROMPT-DRIVEN: if the "
            "dispatch prompt explicitly names 'signature_history.jsonl' / "
            "'signature.json', use Function 1 output format. Otherwise, use Function 2.\n\n"
            "FUNCTION 1 — Signature Drift\n"
            "Given the current signature and last N entries from signature_history.jsonl:\n"
            "BEFORE classifying, check the origin field.\n"
            "  If origin == 'imported': all dimension changes are automatically "
            "EXPECTED. Skip UNEXPLAINED analysis. Note team_id.\n"
            "  If origin == 'self': run full drift analysis.\n"
            "Classify each changed dimension as:\n"
            "  EXPECTED — new language, new project, gradual evolution\n"
            "  UNEXPLAINED — sudden shift with no corresponding sample-source change\n"
            "  NOISE — minor fluctuation within known variance\n\n"
            "FUNCTION 2 — General-purpose drift / history tracking\n"
            "User-invoked for: config drift across sessions, decision diary, metric "
            "trend classification (stable / drifting / oscillating), architecture "
            "evolution, retrospectives.\n"
            "Output format:\n"
            "  SUBJECT: <what you tracked>\n"
            "  TIMEFRAME: <from → to>\n"
            "  CHANGES OBSERVED: <change / when / classification>\n"
            "  CLASSIFICATION:\n"
            "    EXPECTED (explained by): <context>\n"
            "    UNEXPLAINED (flag for review): <list>\n"
            "    NOISE (ignore): <list>\n"
            "  THROUGH-LINE: <one-sentence trajectory summary>\n\n"
            "Never do: modify the data you're tracking (read-only), decide which state "
            "is 'correct' (classify, leave the call to the user), skip the classification step."
        ),
    },
}


TOOLS_CONFIG = [{"type": "agent_toolset_20260401"}]


# ---- Memory stores (Managed Agents memory, public beta) ----
#
# One memory store per governance agent, gated on `active_mode == "cloud"`.
# Stores are attached at session creation time (see review.py). They persist
# across sessions — Brutus accumulates prior critical findings, Historian
# accumulates prior drift verdicts, QA accumulates recurring schema violations.
# Cache under `memory_stores:` in managed-agents.json; same recreate semantics
# as agents.
#
# Each store is scoped to a single governance agent so that writes from one
# don't contaminate another's memory. All three are mounted `read_write` at
# `/mnt/memory/<name>` in the container.
MEMORY_STORES = {
    "signature-brutus": {
        "name": "CogSig Brutus Findings",
        "description": (
            "Adversarial review findings across signature reviews. Prior "
            "KILL/REWORK/PASS-WITH-CAVEATS verdicts, recurring weak claims, "
            "samples that contradicted signature dimensions, calibration "
            "data (how often PASS was returned). Check before starting any "
            "new review so you don't repeat a conclusion that was already "
            "reversed."
        ),
        "instructions": (
            "Brutus-governance memory — prior findings across signature "
            "reviews. BEFORE reviewing, check /mnt/memory/brutus-findings for "
            "prior KILL/REWORK/CONTRADICTED verdicts on the current scope. "
            "AFTER reviewing, append a short note (scope, version, top "
            "critical finding, verdict) so future reviews see the history. "
            "Keep the store organized: one file per scope, append to it "
            "rather than creating new files."
        ),
    },
    "signature-qa": {
        "name": "CogSig QA Schema Violations",
        "description": (
            "Recurring schema violations per scope. Repeated failures on the "
            "same dimension, repeated missing sub-fields, patterns of origin "
            "enum drift. Use it to flag deja-vu violations vs genuinely new "
            "schema issues."
        ),
        "instructions": (
            "QA memory — recurring schema violations across signatures. "
            "BEFORE validating, check /mnt/memory/qa-recurring for prior "
            "FAIL reports on the current scope. Note if the same violation "
            "recurs (signal the extractor has a persistent bug). AFTER "
            "validating, append any new FAIL entries. Do not write a memory "
            "if the signature PASSES — no-signal writes waste the store."
        ),
    },
    "signature-historian": {
        "name": "CogSig Drift History",
        "description": (
            "Drift classifications across signature versions. Prior EXPECTED "
            "/ UNEXPLAINED / NOISE verdicts per dimension, through-line "
            "summaries, known evolution trajectories. The scope's history — "
            "not the signature itself — is the product."
        ),
        "instructions": (
            "Historian memory — drift trajectories across signature "
            "versions. BEFORE classifying, check /mnt/memory/drift-history "
            "for the scope's prior through-line. If the new classification "
            "continues the established trajectory, say so. If it breaks the "
            "trajectory, that IS the signal. AFTER classifying, append the "
            "new entry (version, date, classification summary, through-line "
            "delta) so the trajectory compounds."
        ),
    },
}


def ensure_agents_and_env(repo: Path, force_recreate: bool = False, with_memory: bool = False) -> dict:
    """Create (or reuse) the 3 governance agents + shared environment.

    Returns a dict with agent IDs keyed by agent name + environment_id.
    Cached in .signature-cache/managed-agents.json.

    When `with_memory=True`, ALSO ensures a memory store per agent exists and
    caches the store IDs under `memory_stores`. Safe to call with memory=True
    even if memory stores were created in a prior call — idempotent.
    """
    cache = load_cache(repo)
    required_agent_keys = ("environment_id", "signature-brutus", "signature-qa", "signature-historian")
    agents_ready = bool(cache) and all(k in cache for k in required_agent_keys)
    memory_ready = (
        not with_memory
        or (
            "memory_stores" in cache
            and all(name in cache.get("memory_stores", {}) for name in MEMORY_STORES)
        )
    )

    if agents_ready and memory_ready and not force_recreate:
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

    if with_memory:
        cache.setdefault("memory_stores", {})
        for agent_name, store_spec in MEMORY_STORES.items():
            existing = cache["memory_stores"].get(agent_name)
            if existing and not force_recreate:
                continue
            store = client.beta.memory_stores.create(
                name=store_spec["name"],
                description=store_spec["description"],
            )
            cache["memory_stores"][agent_name] = {
                "id": store.id,
                "name": store_spec["name"],
                "instructions": store_spec["instructions"],
                "created_ts": datetime.now(timezone.utc).isoformat(),
            }
            print(f"created memory store for {agent_name}: {store.id}", file=sys.stderr)

    save_cache(repo, cache)
    return cache


def memory_resources_for(cache: dict, agent_name: str) -> list[dict]:
    """Build the `resources[]` list for a session to attach the agent's
    memory store. Returns [] if memory stores haven't been provisioned — the
    session will still run, just without cross-session memory.

    Gated by the caller based on `active_mode`; this helper is pure.
    """
    stores = cache.get("memory_stores") or {}
    entry = stores.get(agent_name)
    if not entry:
        return []
    spec = MEMORY_STORES.get(agent_name, {})
    return [
        {
            "type": "memory_store",
            "memory_store_id": entry["id"],
            "access": "read_write",
            "instructions": entry.get("instructions") or spec.get("instructions", ""),
        }
    ]


def active_mode(repo: Path) -> str:
    """Read active_mode from state.json. Default: standalone."""
    state = repo / ".signature-cache" / "state.json"
    if not state.exists():
        return "standalone"
    try:
        return json.loads(state.read_text(encoding="utf-8")).get("active_mode", "standalone")
    except json.JSONDecodeError:
        return "standalone"


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
