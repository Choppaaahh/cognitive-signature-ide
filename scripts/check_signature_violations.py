#!/usr/bin/env python3
"""check_signature_violations — CogSig v2 enforcement layer detector.

Compares proposed file-edit content against an active signature.json and
classifies violations by severity (high / medium / low / none). Designed to be
called by the PreToolUse hook; also runnable standalone via --self-test.

Design philosophy:
  - Graceful degrade. A signature without explicit code-style markers (e.g. a
    "directing/dialogue" signature) returns severity=none — there's nothing to
    check, so we don't fabricate violations.
  - Confidence-weighted. Each signature dimension has its own confidence score;
    we only enforce dimensions with confidence >= MIN_DIM_CONFIDENCE.
  - Conservative. When in doubt, return WARN (not REJECT). FP cost on a Reject
    is high (blocks the user); FP cost on a Warn is low (visible advisory).

Output (stdout): JSON with keys:
  - violations:        list[dict] (rule, severity, evidence, confidence)
  - severity:          'high' | 'medium' | 'low' | 'none'
  - recommended_action 'REJECT' | 'WARN' | 'PASS'
  - signature_loaded:  bool
  - reason:            optional human string (when no enforcement applies)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Only enforce dimensions whose confidence meets this floor.
MIN_DIM_CONFIDENCE = 0.7

# Severity for each rule class. Tunable here without touching the rule code.
RULE_SEVERITY = {
    "naming_convention": "medium",      # warn-worthy by default
    "import_wildcard": "high",          # bad practice + signature-conflict = reject-eligible
    "bare_except": "high",              # widely-cited code smell
    "indent_style": "medium",
    "structural_nesting_depth": "low",  # heuristic; never reject
}


# ---------------------------------------------------------------------------
# Rule helpers
# ---------------------------------------------------------------------------

_FUNC_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
_CLASS_DEF_RE = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]", re.MULTILINE)
_WILDCARD_IMPORT_RE = re.compile(r"^\s*from\s+\S+\s+import\s+\*", re.MULTILINE)
_BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
_BROAD_EXCEPT_RE = re.compile(r"^\s*except\s+Exception\s*:", re.MULTILINE)


def _is_snake_case(name: str) -> bool:
    # Allow leading underscores (private), but otherwise lowercase + underscores only.
    stripped = name.lstrip("_")
    if not stripped:
        return True
    return stripped.islower() and "_" in stripped or (
        stripped.islower() and stripped.isalnum()
    )


def _is_camel_case(name: str) -> bool:
    stripped = name.lstrip("_")
    if not stripped or not stripped[0].islower():
        return False
    return any(c.isupper() for c in stripped[1:])


def _is_python_file(filename: str) -> bool:
    return filename.endswith(".py") or filename.endswith(".pyi")


# ---------------------------------------------------------------------------
# Rule checks
# ---------------------------------------------------------------------------

def _check_naming(content: str, dim: dict) -> list[dict]:
    style = dim.get("primary_style")
    conf = dim.get("confidence", 0.0)
    if conf < MIN_DIM_CONFIDENCE or style not in ("snake_case", "camelCase"):
        return []
    violations = []
    funcs = _FUNC_DEF_RE.findall(content)
    for fn in funcs:
        if fn.startswith("__") and fn.endswith("__"):
            continue  # dunder methods are conventional regardless
        if style == "snake_case" and not _is_snake_case(fn):
            violations.append({
                "rule": "naming_convention",
                "severity": RULE_SEVERITY["naming_convention"],
                "evidence": f"function '{fn}' is not snake_case (signature: snake_case)",
                "confidence": conf,
            })
        elif style == "camelCase" and not _is_camel_case(fn):
            violations.append({
                "rule": "naming_convention",
                "severity": RULE_SEVERITY["naming_convention"],
                "evidence": f"function '{fn}' is not camelCase (signature: camelCase)",
                "confidence": conf,
            })
    return violations


def _check_imports(content: str, dim: dict) -> list[dict]:
    """Wildcard imports nearly always violate any explicit import_organization."""
    conf = dim.get("confidence", 0.0)
    if conf < MIN_DIM_CONFIDENCE:
        return []
    grouping = dim.get("grouping")
    if grouping not in ("stdlib-third-party-local", "alphabetical"):
        return []
    matches = _WILDCARD_IMPORT_RE.findall(content)
    if not matches:
        return []
    return [{
        "rule": "import_wildcard",
        "severity": RULE_SEVERITY["import_wildcard"],
        "evidence": f"wildcard import detected ({len(matches)}x); signature prefers explicit imports ({grouping})",
        "confidence": conf,
    }]


def _check_error_handling(content: str, dim: dict) -> list[dict]:
    """`bare_except_tolerance: never` + bare `except:` in proposed content = high-severity hit."""
    conf = dim.get("confidence", 0.0)
    if conf < MIN_DIM_CONFIDENCE:
        return []
    tolerance = dim.get("bare_except_tolerance")
    if tolerance not in ("never", "rare"):
        return []
    bare_count = len(_BARE_EXCEPT_RE.findall(content))
    if bare_count == 0:
        return []
    severity = "high" if tolerance == "never" else "medium"
    return [{
        "rule": "bare_except",
        "severity": severity,
        "evidence": f"bare 'except:' found ({bare_count}x); signature tolerance: {tolerance}",
        "confidence": conf,
    }]


def _check_indent(content: str, filename: str) -> list[dict]:
    """Heuristic: if file looks Python AND mixes tabs+spaces in leading indent, flag."""
    if not _is_python_file(filename):
        return []
    has_tab_indent = False
    has_space_indent = False
    for line in content.splitlines():
        if not line or not line[0].isspace():
            continue
        if line.startswith("\t"):
            has_tab_indent = True
        elif line.startswith("  "):
            has_space_indent = True
        if has_tab_indent and has_space_indent:
            return [{
                "rule": "indent_style",
                "severity": RULE_SEVERITY["indent_style"],
                "evidence": "file mixes tab and space indentation",
                "confidence": 0.9,  # this is a strong signal regardless of signature
            }]
    return []


# ---------------------------------------------------------------------------
# Top-level check
# ---------------------------------------------------------------------------

def check_violations(signature: dict, content: str, filename: str) -> dict:
    """Return JSON-serializable verdict dict."""
    if not signature:
        return {
            "violations": [],
            "severity": "none",
            "recommended_action": "PASS",
            "signature_loaded": False,
            "reason": "no signature provided",
        }
    domain = signature.get("domain", "")
    dims = signature.get("dimensions", {})

    # Dialogue/directing-domain signatures don't tell us anything about code structure.
    if domain in ("directing", "writing", "dialogue") and not _has_code_dimensions(dims):
        return {
            "violations": [],
            "severity": "none",
            "recommended_action": "PASS",
            "signature_loaded": True,
            "reason": f"signature domain '{domain}' has no code-style markers — enforcement skipped",
        }

    # Python-only filename gate for code rules. Other languages get a no-op for now
    # (signature schema is python-leaning; non-python is out-of-scope until v3).
    is_py = _is_python_file(filename)
    violations: list[dict] = []

    if is_py:
        if "naming_convention" in dims:
            violations.extend(_check_naming(content, dims["naming_convention"]))
        if "import_organization" in dims:
            violations.extend(_check_imports(content, dims["import_organization"]))
        if "error_handling" in dims:
            violations.extend(_check_error_handling(content, dims["error_handling"]))
        violations.extend(_check_indent(content, filename))

    # Compute aggregate severity = max per-rule severity.
    if not violations:
        overall = "none"
        action = "PASS"
    else:
        sev_rank = {"low": 0, "medium": 1, "high": 2}
        max_rank = max(sev_rank[v["severity"]] for v in violations)
        overall = ["low", "medium", "high"][max_rank]
        # Action is determined by enforcement_mode at the hook layer; this is a recommendation.
        action = "REJECT" if overall == "high" else "WARN" if overall == "medium" else "PASS"

    return {
        "violations": violations,
        "severity": overall,
        "recommended_action": action,
        "signature_loaded": True,
        "filename": filename,
        "domain": domain,
    }


def _has_code_dimensions(dims: dict) -> bool:
    """True if signature carries any of the code-domain dimensions."""
    code_dims = {"naming_convention", "import_organization", "error_handling",
                 "structural_preference", "function_length", "comment_density"}
    return bool(set(dims.keys()) & code_dims)


# ---------------------------------------------------------------------------
# CLI / self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    """Run 3 sample payloads through the detector — one violating, one passing, one borderline."""
    code_sig = {
        "version": "0.1",
        "domain": "code",
        "dimensions": {
            "naming_convention": {"primary_style": "snake_case", "confidence": 0.95, "evidence": "x"},
            "import_organization": {"grouping": "stdlib-third-party-local", "aliasing_style": "rare", "confidence": 0.9},
            "error_handling": {
                "try_except_style": "specific",
                "validation_pattern": "guard-clause",
                "bare_except_tolerance": "never",
                "confidence": 0.9,
            },
        },
    }
    dialogue_sig = {
        "version": "0.1",
        "domain": "directing",
        "dimensions": {
            "directive_style": {"primary_mode": "command", "confidence": 0.9, "evidence": "x"},
        },
    }

    cases = [
        ("violating.py", code_sig,
         "from os import *\n\ndef MyBadFunc():\n    try:\n        pass\n    except:\n        pass\n",
         "high"),
        ("passing.py", code_sig,
         "import os\n\ndef good_function():\n    try:\n        pass\n    except ValueError:\n        pass\n",
         "none"),
        ("borderline.py", code_sig,
         "import os\n\ndef AnotherBadName():\n    pass\n",
         "medium"),
        ("dialogue_skip.py", dialogue_sig,
         "from os import *\n\ndef BadName():\n    pass\n",
         "none"),
    ]
    failures = 0
    for filename, sig, content, expected_sev in cases:
        verdict = check_violations(sig, content, filename)
        status = "OK" if verdict["severity"] == expected_sev else "FAIL"
        if status == "FAIL":
            failures += 1
        print(f"[{status}] {filename}: severity={verdict['severity']} expected={expected_sev} "
              f"action={verdict['recommended_action']} violations={len(verdict['violations'])}")
        for v in verdict["violations"]:
            print(f"        - {v['rule']} ({v['severity']}): {v['evidence']}")
    print(f"\nself-test: {len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect signature violations in proposed file content.")
    ap.add_argument("--signature", type=Path, help="Path to signature.json")
    ap.add_argument("--content-file", type=Path, help="Proposed file content (alternative to stdin)")
    ap.add_argument("--filename", type=str, default="", help="Target filename for context")
    ap.add_argument("--self-test", action="store_true", help="Run built-in self-test")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()

    sig: dict[str, Any] = {}
    if args.signature and args.signature.exists():
        try:
            sig = json.loads(args.signature.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(json.dumps({
                "violations": [],
                "severity": "none",
                "recommended_action": "PASS",
                "signature_loaded": False,
                "reason": f"signature unreadable: {e}",
            }))
            return 0

    if args.content_file:
        content = args.content_file.read_text(encoding="utf-8", errors="replace")
    else:
        content = sys.stdin.read()

    verdict = check_violations(sig, content, args.filename or "")
    print(json.dumps(verdict, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
