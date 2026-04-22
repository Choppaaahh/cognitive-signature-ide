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

    # Write pending queue with auto-assigned IDs
    for i, p in enumerate(pending, 1):
        p["id"] = i
    queue = {
        "last_refresh_ts": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "preset": preset,
        "patterns": pending,
    }
    write_json(pending_path(repo, scope), queue)
    print(f"review: {len(pending)} pending patterns written to {pending_path(repo, scope).name}")
    for p in pending:
        item = p["item"]
        label = item.get("situation") or item.get("pattern") or item.get("tool") or item.get("term") or "?"
        count = item.get("instance_count", "?")
        print(f"  [{p['id']}] {p['dim']} — \"{str(label)[:80]}\" ({count}x)")
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
