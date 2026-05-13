"""
N5 — Gauss Accumulation: Pattern-Fidelity Drift

Reference:
    Gauss C.F. (1809), "Theoria motus corporum coelestium in sectionibus
    conicis solem ambientium" (least-squares foundation for recursive
    EMA-with-posterior updates).

Ecosystem precedent:
    Wixie F6, Emu A7, Crow H6, Djinn D5, Gorgon G5.

Role:
    Per-(pattern-class x target-domain) acceptable-fidelity-threshold posterior.
    A "claude-md replication" earns a different fidelity band than a
    "python-module replication" — naming-convention strictness differs by
    domain.

Stdlib only. EMA mean + EMA variance with sample-count tracked alongside the
posterior. Atomic JSONL append is delegated to `state_io.append_jsonl`.

Pattern classes (canonical):
    {claude-md, python-module, plugin-json, hook-script, agent-md,
     test-module, docs-md, generic}
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path


def update_posterior(prior: dict, observation: dict, alpha: float = 0.3) -> dict:
    """Fold a single fidelity observation into the per-(class x domain) posterior.

    `prior` shape (any subset; first call may be {}):
        {
            "median_fidelity": float,
            "sigma": float,
            "n_observations": int,
            "p10_threshold": float,  # 10th-percentile acceptable-fidelity floor
            "last_seen": str,        # ISO timestamp
        }
    `observation` shape:
        {
            "fidelity_score": float,
            "captured_at": str,
        }

    Returns a new posterior dict. EMA half-life ~ 30 observations at alpha=0.3
    (tunable). Variance maintained via EMA-of-squared-deviation — tractable and
    stable enough for advisory bands.
    """
    if not isinstance(observation, dict):
        return dict(prior or {})

    score = float(observation.get("fidelity_score", 0.0))
    seen = str(observation.get("captured_at", ""))

    n_prior = int(prior.get("n_observations", 0)) if prior else 0
    if n_prior == 0:
        return {
            "median_fidelity": score,
            "sigma": 0.0,
            "n_observations": 1,
            "p10_threshold": max(0.0, score - 0.1),
            "last_seen": seen,
        }

    prev_med = float(prior.get("median_fidelity", score))
    prev_sigma = float(prior.get("sigma", 0.0))

    new_med = (1 - alpha) * prev_med + alpha * score
    delta = score - prev_med
    new_var = (1 - alpha) * (prev_sigma ** 2) + alpha * (delta * delta)
    new_sigma = math.sqrt(max(0.0, new_var))
    # 10th-percentile floor under a normal approximation: mu - 1.2816 * sigma.
    new_p10 = max(0.0, new_med - 1.2816 * new_sigma)

    return {
        "median_fidelity": new_med,
        "sigma": new_sigma,
        "n_observations": n_prior + 1,
        "p10_threshold": new_p10,
        "last_seen": seen,
    }


def _main() -> int:
    """CLI entry point for the PreCompact hook (`python -m engines.n5_gauss`).

    Folds a no-op observation into the per-(repo, pattern_class) posterior. The
    actual generation/observation pipeline writes richer payloads via the
    naga-shaper; this entry point exists so the hook can stamp a heartbeat
    when no fresh observation is queued. Fail-open.
    """
    try:
        plugin_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
        scripts_dir = plugin_root.parent.parent / "shared" / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from state_io import read_json, atomic_write_json, append_jsonl  # noqa: E402

        posterior_path = plugin_root / "state" / "posterior.json"
        posteriors = read_json(posterior_path, default={})
        now = datetime.now(timezone.utc).isoformat()

        # Heartbeat-only update: re-stamp last_seen on any existing posteriors.
        for cls, by_domain in (posteriors or {}).items():
            if not isinstance(by_domain, dict):
                continue
            for dom, post in by_domain.items():
                if isinstance(post, dict):
                    post["last_seen"] = now

        atomic_write_json(posterior_path, posteriors or {})
        append_jsonl(
            plugin_root / "state" / "learnings.jsonl",
            {"updated_at": now, "kind": "heartbeat"},
        )
        return 0
    except Exception:
        # Fail-open per shared/vis/conduct/hooks.md.
        return 0


if __name__ == "__main__":
    sys.exit(_main())
