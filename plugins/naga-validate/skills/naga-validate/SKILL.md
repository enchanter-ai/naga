---
name: naga-validate
description: >
  Scores fidelity of a generated artifact against a source pattern via N1
  Wagner-Fischer flattened-AST edit distance (a coarse same-shape screen, not
  true Zhang-Shasha tree edit distance — see VF-08) + N4 Salton-Wong-Yang
  cosine. Returns
  (score, ci_low, ci_high, N) per the honest-numbers contract. Use when the
  user runs /naga:validate or asks "how close is this to the source pattern?".
  Do not use for fingerprinting (see /naga:observe) or for generation (see
  /naga:match).
model: haiku
tools: [Read, Grep, Glob]
---

# naga-validate

## Preconditions

- Both `<new>` and `<source>` paths exist and are readable.
- If the source has not been fingerprinted yet, the skill runs `/naga:observe <source>` first.

## Inputs

- **Slash command:** `/naga:validate <new> <source>`
- **Arguments:**
  - `new` — path to the artifact under validation.
  - `source` — path to the reference pattern.

## Steps

1. Resolve or compute the source fingerprint at `plugins/naga-observe/state/patterns/<hash>.json`.
2. Spawn the **naga-fingerprinter** Haiku agent with `<new>` to produce its feature vector.
3. Compute N4 cosine of the new-artifact vector against the source vector.
4. Compute per-feature similarities and pass through `bootstrap_ci` (1000 iterations) to derive `(score, ci_low, ci_high, N)`.
5. Reject the result if N is missing (F11 guard).
6. Publish `naga.fidelity.measured` with `{generated_path, source_pattern, score, ci_low, ci_high, N}`.

## Outputs

- One `naga.fidelity.measured` event on the bus.
- Console table: `path | score | ci_low | ci_high | N | verdict`. Verdict is `pass` if `ci_low >= p10_threshold`, else `hold`.

## Handoff

If verdict is `hold`, the developer can re-run `/naga:match <source> <new>` for a fresh attempt.

## Failure modes

- **F11 reward hacking** — never widen the CI to make `ci_low` cross the threshold.
- **F02 fabrication** — never validate against a fingerprint that does not exist on disk; auto-observe instead.
