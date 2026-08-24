# Changelog

## Unreleased

- N1 is now a real **Zhang-Shasha (1989)** ordered-tree edit distance over the
  parsed AST, replacing the flattened postorder Wagner-Fischer *string* edit
  distance. Structure is now respected — differently nested programs with the
  same node multiset (e.g. `f(a, g(b))` vs `f(g(a, b))`) no longer collapse to
  distance 0. Closes VF-08. Signature unchanged; docs/README/SKILLs reconciled.

## 0.1.0 — 2026-04-25

Phase-1 scaffold.

- 7 plugins: naga-observe, naga-shift, naga-validate, naga-cross-repo, naga-fingerprint, naga-learning, full.
- 5 engines: N1 Wagner-Fischer (1974), N2 Spaerck Jones (1972), N3 Levenshtein (1966), N4 Salton-Wong-Yang (1975), N5 Gauss (1809).
- 3 agents: naga-fingerprinter (Haiku), naga-shaper (Sonnet), naga-orchestrator (Opus).
- 1 hook: PreCompact -> naga-learning. Naga is skill-invoked by design like Wixie.
- 4 published events: pattern.fingerprinted, artifact.generated, fidelity.measured, pattern.refreshed.
- Honest-numbers contract: (score, ci_low, ci_high, N) on every advisory.
- 13 inherited conduct modules from shared/conduct/.
