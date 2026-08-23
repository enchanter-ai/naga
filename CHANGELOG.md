# Changelog

## 0.1.0 — 2026-04-25

Phase-1 scaffold.

- 7 plugins: naga-observe, naga-shift, naga-validate, naga-cross-repo, naga-fingerprint, naga-learning, full.
- 5 engines: N1 Wagner-Fischer (1974), N2 Spaerck Jones (1972), N3 Levenshtein (1966), N4 Salton-Wong-Yang (1975), N5 Gauss (1809).
- 3 agents: naga-fingerprinter (Haiku), naga-shaper (Sonnet), naga-orchestrator (Opus).
- 1 hook: PreCompact -> naga-learning. Naga is skill-invoked by design like Wixie.
- 4 published events: pattern.fingerprinted, artifact.generated, fidelity.measured, pattern.refreshed.
- Honest-numbers contract: (score, ci_low, ci_high, N) on every advisory.
- 13 inherited conduct modules from shared/conduct/.
