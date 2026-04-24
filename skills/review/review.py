#!/usr/bin/env python3
"""review — pattern-review queue: diff new signature vs permanent, surface pending for approval.

Subcommands:
    pending              — list pending patterns with evidence
    approve <id[,id...]> — promote listed IDs to permanent signature
    reject <id[,id...]>  — reject + log; prevents re-propose
    edit <id> <text>     — edit pattern description before accepting
    refresh-queue        — re-diff current signature vs permanent, update pending queue

Invoked either directly or via toggle.py's cmd_route.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# Dimensions we process. Each dim has an item-list at `dimensions.<dim>.<list_key>`.
OPERATIONAL_DIMS = {
    "recurring_decision_templates": "templates",
    "recurring_failure_patterns": "patterns",
    "recurring_tooling_invocations": "invocations",
    "vocabulary_anchors": "anchors",
}


def _scope_suffix(scope: str) -> str:
    return "" if scope == "default" else f".{scope}"


def pending_path(repo: Path, scope: str = "default") -> Path:
    return repo / ".signature-cache" / f"pending_patterns{_scope_suffix(scope)}.json"


def rejected_path(repo: Path, scope: str = "default") -> Path:
    return repo / ".signature-cache" / f"rejected_patterns{_scope_suffix(scope)}.jsonl"


def state_path(repo: Path) -> Path:
    return repo / ".signature-cache" / "state.json"


def signature_path_for_scope(repo: Path, scope_name: str) -> Path:
    filename = "signature.json" if scope_name == "default" else f"signature.{scope_name}.json"
    return repo / filename


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _normalize(text: str, limit: int = 80) -> str:
    """Normalize text for stable identity keys: lowercase, collapse whitespace, strip punctuation-heavy ends."""
    if not text:
        return ""
    norm = " ".join(text.lower().split())
    return norm[:limit].strip(" ,.;:!?")


def item_key(dim: str, item: dict) -> str:
    """Stable identity key for a pattern item — used to diff against permanent signature.

    Applies whitespace/case normalization + truncation to make keys robust to minor rephrasing
    (e.g. 'Push to PC' vs 'push to pc' should hash the same; 'push-to-PC' vs 'push to PC' might not).
    """
    if dim == "recurring_decision_templates":
        return f"{dim}::{_normalize(item.get('situation', ''))}||{_normalize(item.get('response', ''))}"
    if dim == "recurring_failure_patterns":
        return f"{dim}::{_normalize(item.get('pattern', ''), 100)}"
    if dim == "recurring_tooling_invocations":
        return f"{dim}::{_normalize(item.get('tool', ''))}"
    if dim == "vocabulary_anchors":
        return f"{dim}::{_normalize(item.get('term', ''))}"
    return f"{dim}::{_normalize(json.dumps(item, sort_keys=True), 100)}"


def _dispatch_cloud_governance(repo: Path, scope: str, items: list[dict]) -> bool:
    """Dispatch managed-agents/review.py synchronously for cloud-mode approvals.

    Best-effort: if managed-agents infra is unavailable (missing SDK, missing API key,
    agent setup failure), prints a warning and returns False so approval is refused
    rather than silently bypassing the governance gate. Cloud mode MUST fail closed —
    that's the contract. Non-cloud modes never call this function.
    """
    import subprocess
    import sys as _sys

    plugin_root = Path(__file__).resolve().parent.parent.parent
    managed_script = plugin_root / "managed-agents" / "review.py"
    if not managed_script.exists():
        print(f"cogsig: cloud mode — managed-agents script missing at {managed_script}", file=_sys.stderr)
        return False
    cmd = [
        _sys.executable, str(managed_script),
        "--repo", str(repo),
    ]
    if scope != "default":
        cmd.extend(["--scope-name", scope])
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=300)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"cogsig: cloud governance dispatch failed ({type(e).__name__}): {e}", file=_sys.stderr)
        return False
    if result.returncode != 0:
        print(f"cogsig: managed-agents review returned rc={result.returncode}", file=_sys.stderr)
        if result.stderr:
            print(f"  stderr: {result.stderr[:500]}", file=_sys.stderr)
        return False
    print(f"cogsig: cloud governance review completed ({len(items)} pattern(s) reviewed)", file=_sys.stderr)
    return True


def _qa_validate_patterns(pending: list[dict]) -> list[str]:
    """Governance-gate: deterministic QA schema check on pending patterns before they
    enter the permanent signature. Returns list of human-readable error messages;
    empty list = PASS. Runs $0/fast — no LLM call. Matches the per-dim schema
    required-fields in signature_schema_operational.json.

    Fields required per dim (from schema):
      recurring_decision_templates: situation, response, instance_count, evidence_list
      recurring_failure_patterns:   pattern, context, instance_count, evidence_list
      recurring_tooling_invocations:tool, context, instance_count, evidence_list
      vocabulary_anchors:           term, domain, instance_count, evidence_list
    """
    required_fields = {
        "recurring_decision_templates": ("situation", "response", "instance_count", "evidence_list"),
        "recurring_failure_patterns": ("pattern", "context", "instance_count", "evidence_list"),
        "recurring_tooling_invocations": ("tool", "context", "instance_count", "evidence_list"),
        "vocabulary_anchors": ("term", "domain", "instance_count", "evidence_list"),
    }
    errors: list[str] = []
    for p in pending:
        dim = p.get("dim")
        item = p.get("item")
        if not isinstance(item, dict):
            errors.append(f"item missing or not dict for pending entry: {p.get('id', '?')}")
            continue
        fields = required_fields.get(dim)
        if not fields:
            errors.append(f"unknown dim '{dim}' for item {p.get('id', '?')}")
            continue
        for f in fields:
            if f not in item:
                errors.append(f"dim={dim} id={p.get('id','?')}: missing required field '{f}'")
                continue
            val = item[f]
            if f == "instance_count":
                if not isinstance(val, (int, float)) or val < 2:
                    errors.append(f"dim={dim} id={p.get('id','?')}: instance_count must be int>=2, got {val!r}")
            elif f == "evidence_list":
                if not isinstance(val, list) or len(val) == 0:
                    errors.append(f"dim={dim} id={p.get('id','?')}: evidence_list must be non-empty list, got {type(val).__name__}")
            else:
                if not isinstance(val, str) or not val.strip():
                    errors.append(f"dim={dim} id={p.get('id','?')}: field '{f}' must be non-empty string")
    return errors


def load_rejected(repo: Path, scope: str = "default") -> set[str]:
    path = rejected_path(repo, scope)
    if not path.exists():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            key = row.get("item_key")
            if key:
                keys.add(key)
        except json.JSONDecodeError:
            continue
    return keys


def diff_signature(new_sig: dict, permanent_sig: dict, rejected_keys: set[str], min_instance_count: int = 2) -> list[dict]:
    """Return list of items in new_sig that are NOT in permanent_sig and NOT previously rejected,
    with instance_count >= min_instance_count. Each pending item includes its item_key + dim + data."""
    pending: list[dict] = []
    new_dims = new_sig.get("dimensions", {})
    perm_dims = permanent_sig.get("dimensions", {}) if permanent_sig else {}

    for dim, list_key in OPERATIONAL_DIMS.items():
        new_items = new_dims.get(dim, {}).get(list_key, [])
        perm_items = perm_dims.get(dim, {}).get(list_key, [])
        perm_keys = {item_key(dim, it) for it in perm_items}

        for item in new_items:
            if not isinstance(item, dict):
                continue
            count = item.get("instance_count", 0)
            if not isinstance(count, (int, float)) or count < min_instance_count:
                continue
            k = item_key(dim, item)
            if k in perm_keys or k in rejected_keys:
                continue
            pending.append({
                "dim": dim,
                "list_key": list_key,
                "item_key": k,
                "item": item,
                "detected_ts": datetime.now(timezone.utc).isoformat(),
            })

    return pending


def cmd_refresh_queue(repo: Path, rest: list[str]) -> int:
    """Re-run diff against current signature + update pending_patterns.json.

    First-run behavior is preset-conditional:
      - normie: seed permanent = current signature (auto-approve everything, 0 pending)
      - power/team/enterprise: seed permanent = EMPTY (surface everything for review)

    Subsequent runs always diff the new signature vs the current permanent baseline.
    """
    state = load_json(state_path(repo), {})
    scope = state.get("active_scope", "default")
    preset = state.get("preset", "power")

    op_scope = "operational" if scope == "default" else f"{scope}-operational"
    op_sig_path = signature_path_for_scope(repo, op_scope)

    if not op_sig_path.exists():
        print(f"review: no operational signature at {op_sig_path.name}; run /cogsig extract first", file=sys.stderr)
        return 1

    new_sig = json.loads(op_sig_path.read_text(encoding="utf-8"))

    permanent_name = f"signature.{op_scope}.permanent.json"
    permanent_sig_path = repo / permanent_name
    permanent_sig = load_json(permanent_sig_path, {})

    rejected_keys = load_rejected(repo, scope)

    # FIRST-RUN SEED: if no permanent signature exists yet, preset determines behavior.
    if not permanent_sig:
        if preset == "normie":
            # Hands-off: seed permanent from first signature; nothing pending.
            write_json(permanent_sig_path, new_sig)
            write_json(pending_path(repo, scope), {"patterns": [], "last_refresh_ts": datetime.now(timezone.utc).isoformat()})
            print(f"review: normie-preset first-run — permanent signature seeded from extract ({permanent_name}). 0 pending patterns.")
            return 0
        else:
            # Review-before-promote: seed permanent as empty dimensions;
            # diff will then surface everything from the new signature for review.
            permanent_sig = {"version": "0.1", "domain": "operational", "dimensions": {}}
            write_json(permanent_sig_path, permanent_sig)

    pending = diff_signature(new_sig, permanent_sig, rejected_keys)

    # STEADY-STATE auto-promote — ALL 4 PRESETS get hands-off promotion with
    # preset-specific count thresholds. The user never has to manually approve.
    # Per-preset rationale (count = instance_count on the pattern item):
    #   normie:     n≥2  (trusts extractor fully, fastest path)
    #   power:      n≥5  (conservative solo user, waits for more evidence)
    #   team:       n≥3  (in-session subagent dispatch-hook surfaces reminders separately;
    #                     auto-promote still fires at count-bar regardless)
    #   enterprise: n≥3  (cloud Managed Agents review fires in parallel via extract.py hook;
    #                     auto-promote still fires at count-bar regardless)
    # Malformed items (QA schema fail) are ALWAYS refused across all presets.
    _PRESET_AUTO_PROMOTE_THRESHOLD = {
        "normie": 2,
        "power": 5,
        "team": 3,
        "enterprise": 3,
    }
    threshold = _PRESET_AUTO_PROMOTE_THRESHOLD.get(preset, 3)

    if pending:
        # Split by threshold first.
        promotable = [p for p in pending
                      if int(p.get("item", {}).get("instance_count", 0) or 0) >= threshold]
        holdback = [p for p in pending if p not in promotable]

        # QA fix (PASS-WITH-CAVEATS Finding 2): validate ONLY items being promoted.
        # Previous logic flushed the entire pending queue on any malformed item,
        # silently dropping valid holdback items. Now malformed-promotable items
        # drop back to holdback (with a skipped-count note) while holdback is
        # preserved independently.
        promotable_errs = _qa_validate_patterns(promotable)
        if promotable_errs:
            # Refuse to promote malformed items; they stay out of permanent sig.
            # They're effectively skipped this cycle — will re-appear on next
            # refresh with corrected data OR stay as a diagnostic in stderr.
            malformed_indices = set()
            for err in promotable_errs:
                # err format is typically "pattern-N: <detail>" — extract index if present
                import re as _re
                m = _re.match(r"pattern-(\d+)", err)
                if m:
                    malformed_indices.add(int(m.group(1)) - 1)
            # Filter promotable: drop malformed, keep valid.
            promotable_filtered = [p for i, p in enumerate(promotable) if i not in malformed_indices]
            # Drop malformed items entirely (don't re-queue to holdback — they failed schema,
            # shouldn't sit in pending masquerading as valid).
            print(
                f"review: {preset} — {len(promotable_errs)} malformed promotable item(s) DROPPED; "
                f"holdback preserved. First errors: {promotable_errs[:2]}",
                file=sys.stderr,
            )
            promotable = promotable_filtered

        # Promote only items that meet the preset's count threshold AND passed validation.
        for p in promotable:
            dim = p["dim"]
            list_key = p["list_key"]
            item = p["item"]
            if dim not in permanent_sig.setdefault("dimensions", {}):
                permanent_sig["dimensions"][dim] = {list_key: [], "confidence": 0.8}
            permanent_sig["dimensions"][dim][list_key].append(item)
        if promotable:
            write_json(permanent_sig_path, permanent_sig)

        # Holdback items stay in pending — they'll auto-promote when
        # their instance_count grows on a future extract.
        write_json(pending_path(repo, scope), {
            "last_refresh_ts": datetime.now(timezone.utc).isoformat(),
            "scope": scope,
            "preset": preset,
            "patterns": holdback,
            "threshold": threshold,
            "last_auto_promote_count": len(promotable),
            "last_auto_promote_ts": datetime.now(timezone.utc).isoformat() if promotable else None,
        })
        print(
            f"review: {preset} steady-state (threshold n≥{threshold}) — "
            f"auto-promoted {len(promotable)}, holding {len(holdback)} pending until threshold",
            file=sys.stderr,
        )
        return 0

    # Empty-pending path: write empty queue for downstream consumers (inject.py etc).
    write_json(pending_path(repo, scope), {
        "last_refresh_ts": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "preset": preset,
        "patterns": [],
    })
    return 0


def cmd_pending(repo: Path, rest: list[str]) -> int:
    state = load_json(state_path(repo), {})
    scope = state.get("active_scope", "default")
    queue = load_json(pending_path(repo, scope), {"patterns": []})
    patterns = queue.get("patterns", [])
    if not patterns:
        print("cogsig: no pending patterns. Run /cogsig refresh-queue after an extract to check.")
        return 0
    print(f"cogsig: {len(patterns)} pending patterns")
    skipped_bad = 0
    for p in patterns:
        item = p.get("item")
        if not isinstance(item, dict) or "dim" not in p or "id" not in p:
            skipped_bad += 1
            continue
        label = item.get("situation") or item.get("pattern") or item.get("tool") or item.get("term") or "?"
        count = item.get("instance_count", "?")
        evidence = item.get("evidence_list", [])
        print(f"\n  [{p['id']}] {p['dim']} — {count}x instances")
        print(f"      {str(label)[:120]}")
        for ev in evidence[:3]:
            print(f"        ▸ {str(ev)[:100]}")
        if len(evidence) > 3:
            print(f"        ...and {len(evidence) - 3} more")
    if skipped_bad:
        print(f"\n  warning: skipped {skipped_bad} malformed pending entr{'y' if skipped_bad == 1 else 'ies'} — run /cogsig refresh-queue to rebuild", file=sys.stderr)
    print("\ncommands: /cogsig approve <id[,id...]> | /cogsig reject <id[,id...]> | /cogsig edit <id> <text>")
    return 0


def parse_ids(raw: str) -> list[int]:
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out


def cmd_approve(repo: Path, rest: list[str]) -> int:
    if not rest:
        print("usage: /cogsig approve <id[,id...]>", file=sys.stderr)
        return 1
    ids = parse_ids(rest[0])
    if not ids:
        print(f"no valid IDs in '{rest[0]}'", file=sys.stderr)
        return 1

    state = load_json(state_path(repo), {})
    scope = state.get("active_scope", "default")
    queue = load_json(pending_path(repo, scope), {"patterns": []})
    patterns = queue.get("patterns", [])
    approved = [p for p in patterns if p["id"] in ids]
    remaining = [p for p in patterns if p["id"] not in ids]

    if not approved:
        print(f"no pending patterns match IDs {ids}", file=sys.stderr)
        return 1

    # Governance gate: run deterministic QA schema validation before writing to permanent.
    # In cloud mode, ALSO dispatch Brutus + Historian via managed-agents/review.py (slower,
    # costs API). In standalone/team modes, QA-only is the gate (behavioral agent discipline
    # still applies at the prompt layer for team mode).
    qa_errors = _qa_validate_patterns(approved)
    if qa_errors:
        print("cogsig: approval refused — QA schema validation failed", file=sys.stderr)
        for err in qa_errors[:10]:
            print(f"  - {err}", file=sys.stderr)
        if len(qa_errors) > 10:
            print(f"  ... and {len(qa_errors) - 10} more", file=sys.stderr)
        print("fix upstream extract or use /cogsig edit <id> <text> before re-approving", file=sys.stderr)
        return 1

    active_mode = state.get("active_mode", "standalone")
    if active_mode == "cloud":
        cloud_ok = _dispatch_cloud_governance(repo, scope, approved)
        if not cloud_ok:
            print("cogsig: approval refused — cloud governance check failed (see stderr above)", file=sys.stderr)
            return 1

    # Apply approved to permanent signature
    op_scope = "operational" if scope == "default" else f"{scope}-operational"
    permanent_sig_path = repo / f"signature.{op_scope}.permanent.json"
    permanent_sig = load_json(permanent_sig_path, {})
    if "dimensions" not in permanent_sig:
        print(f"error: permanent signature at {permanent_sig_path.name} missing — run refresh-queue first", file=sys.stderr)
        return 1

    skipped_bad = 0
    for p in approved:
        dim = p.get("dim")
        list_key = p.get("list_key")
        item = p.get("item")
        if not dim or not list_key or not isinstance(item, dict):
            skipped_bad += 1
            continue
        if dim not in permanent_sig["dimensions"]:
            permanent_sig["dimensions"][dim] = {list_key: [], "confidence": 0.8}
        permanent_sig["dimensions"][dim][list_key].append(item)
    if skipped_bad:
        print(f"  warning: skipped {skipped_bad} malformed approved entr{'y' if skipped_bad == 1 else 'ies'} — refresh-queue first", file=sys.stderr)

    write_json(permanent_sig_path, permanent_sig)
    queue["patterns"] = remaining
    queue["last_approve_ts"] = datetime.now(timezone.utc).isoformat()
    write_json(pending_path(repo, scope), queue)

    print(f"cogsig: approved {len(approved)} pattern(s) into permanent signature")
    for p in approved:
        label = p["item"].get("situation") or p["item"].get("pattern") or p["item"].get("tool") or p["item"].get("term")
        print(f"  ✓ [{p['id']}] {p['dim']} — {str(label)[:80]}")
    return 0


def cmd_reject(repo: Path, rest: list[str]) -> int:
    if not rest:
        print("usage: /cogsig reject <id[,id...]>", file=sys.stderr)
        return 1
    ids = parse_ids(rest[0])
    reason = " ".join(rest[1:]).strip() if len(rest) > 1 else ""

    state = load_json(state_path(repo), {})
    scope = state.get("active_scope", "default")
    queue = load_json(pending_path(repo, scope), {"patterns": []})
    patterns = queue.get("patterns", [])
    rejected = [p for p in patterns if p["id"] in ids]
    remaining = [p for p in patterns if p["id"] not in ids]

    if not rejected:
        print(f"no pending patterns match IDs {ids}", file=sys.stderr)
        return 1

    rej_path = rejected_path(repo, scope)
    rej_path.parent.mkdir(parents=True, exist_ok=True)
    with rej_path.open("a", encoding="utf-8") as f:
        for p in rejected:
            row = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "item_key": p["item_key"],
                "dim": p["dim"],
                "item": p["item"],
                "reason": reason,
            }
            f.write(json.dumps(row) + "\n")

    queue["patterns"] = remaining
    queue["last_reject_ts"] = datetime.now(timezone.utc).isoformat()
    write_json(pending_path(repo, scope), queue)

    print(f"cogsig: rejected {len(rejected)} pattern(s); logged to {rej_path.name}")
    for p in rejected:
        label = p["item"].get("situation") or p["item"].get("pattern") or p["item"].get("tool") or p["item"].get("term")
        print(f"  ✗ [{p['id']}] {p['dim']} — {str(label)[:80]}")
    return 0


def cmd_edit(repo: Path, rest: list[str]) -> int:
    if len(rest) < 2:
        print("usage: /cogsig edit <id> <new description>", file=sys.stderr)
        return 1
    try:
        target_id = int(rest[0])
    except ValueError:
        print(f"invalid id '{rest[0]}'", file=sys.stderr)
        return 1
    new_text = " ".join(rest[1:]).strip()
    if not new_text:
        print("no new text provided", file=sys.stderr)
        return 1

    state = load_json(state_path(repo), {})
    scope = state.get("active_scope", "default")
    queue = load_json(pending_path(repo, scope), {"patterns": []})
    patterns = queue.get("patterns", [])
    target = next((p for p in patterns if p["id"] == target_id), None)
    if not target:
        print(f"no pending pattern with id {target_id}", file=sys.stderr)
        return 1

    item = target["item"]
    dim = target["dim"]
    if dim == "recurring_decision_templates":
        item["response"] = new_text
    elif dim == "recurring_failure_patterns":
        item["pattern"] = new_text
    elif dim == "recurring_tooling_invocations":
        item["tool"] = new_text
    elif dim == "vocabulary_anchors":
        item["term"] = new_text
    else:
        item["description"] = new_text

    target["item_key"] = item_key(dim, item)
    queue["last_edit_ts"] = datetime.now(timezone.utc).isoformat()
    write_json(pending_path(repo, scope), queue)

    print(f"cogsig: edited pending pattern [{target_id}]. Now: {new_text[:100]}")
    print("run /cogsig approve %d to promote, or edit again." % target_id)
    return 0


HANDLERS = {
    "pending": cmd_pending,
    "approve": cmd_approve,
    "reject": cmd_reject,
    "edit": cmd_edit,
    "refresh-queue": cmd_refresh_queue,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Pattern review: approve/reject/edit pending patterns.")
    ap.add_argument("command", choices=list(HANDLERS))
    ap.add_argument("args", nargs="*")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    parsed = ap.parse_args()
    repo = parsed.repo.resolve()
    return HANDLERS[parsed.command](repo, parsed.args)


if __name__ == "__main__":
    raise SystemExit(main())
