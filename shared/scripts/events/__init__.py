"""
Naga event-bus helpers — typed wrappers over shared.scripts.publish.publish.

Exposes one function per published topic listed in `CLAUDE.md § Events`.
Every helper is fail-open per shared/vis/conduct/hooks.md — advisory, never raises.

Phase-1 file-tail fallback: publishes go through Pech's `publish.py` (copied
verbatim into `shared/scripts/publish.py`) which JSONL-appends events to the
enchanted-mcp bus file.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the sibling publish.py is importable regardless of invocation cwd.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from publish import publish  # noqa: E402


def publish_pattern_fingerprinted(
    source_path: str,
    fingerprint_hash: str,
    n1_signature: str,
    n2_terms: list,
    captured_at: str,
) -> None:
    """naga.pattern.fingerprinted — emitted by naga-observe after N1+N2 extraction."""
    publish(
        "naga.pattern.fingerprinted",
        {
            "source_path": source_path,
            "fingerprint_hash": fingerprint_hash,
            "n1_signature": n1_signature,
            "n2_terms": list(n2_terms),
            "captured_at": captured_at,
        },
    )


def publish_artifact_generated(
    source_path: str,
    target_path: str,
    fidelity_score: float,
    ci_low: float,
    ci_high: float,
    N: int,
) -> None:
    """naga.artifact.generated — honest-numbers contract: (score, ci_low, ci_high, N) required.

    Emitted by naga-shift after a generated artifact passes the per-class N5
    threshold gate.
    """
    publish(
        "naga.artifact.generated",
        {
            "source_path": source_path,
            "target_path": target_path,
            "fidelity_score": fidelity_score,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "N": N,
        },
    )


def publish_fidelity_measured(
    generated_path: str,
    source_pattern: str,
    score: float,
    ci_low: float,
    ci_high: float,
    N: int,
) -> None:
    """naga.fidelity.measured — emitted by naga-validate after N1+N4 scoring."""
    publish(
        "naga.fidelity.measured",
        {
            "generated_path": generated_path,
            "source_pattern": source_pattern,
            "score": score,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "N": N,
        },
    )


def publish_pattern_refreshed(
    pattern_class: str,
    n_observations: int,
    posterior: dict,
) -> None:
    """naga.pattern.refreshed — emitted by naga-learning after PreCompact N5 update.

    pattern_class in {claude-md, python-module, plugin-json, hook-script,
    agent-md, test-module, docs-md, generic}.
    """
    publish(
        "naga.pattern.refreshed",
        {
            "pattern_class": pattern_class,
            "n_observations": n_observations,
            "posterior": dict(posterior),
        },
    )


__all__ = [
    "publish_pattern_fingerprinted",
    "publish_artifact_generated",
    "publish_fidelity_measured",
    "publish_pattern_refreshed",
]
