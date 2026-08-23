---
name: naga-observe
description: >
  Extracts the pattern fingerprint from a source artifact via N1 Wagner-Fischer
  flattened-AST edit-distance signature (a coarse same-shape screen, not true
  Zhang-Shasha tree edit distance — see VF-08) and N2 Spaerck Jones TF-IDF over
  identifier, comment, and structure tokens. Persists the fingerprint to plugins/naga-observe/state/
  patterns/<hash>.json. Use when the user runs /naga:observe or asks to capture
  the structural and stylistic shape of an existing file. Do not use for
  generation (see /naga:match) or for cross-domain replication (see
  /naga:match-across).
model: haiku
tools: [Read, Grep, Glob, Write]
---

# naga-observe

## Preconditions

- The `<source>` path passed to `/naga:observe` exists and is readable.
- If the source is too small (< 50 tokens or < 5 identifiers), the skill returns `{fingerprint_unreliable: true}` rather than emit a hallucinated pattern.

## Inputs

- **Slash command:** `/naga:observe <source>`
- **Arguments:** `source` — absolute or repo-relative path to the artifact to fingerprint.

## Steps

1. Read the source file with the Read tool. If size > 50 KB, set `chunked: true` and process top 50 KB only.
2. Spawn the **naga-fingerprinter** Haiku agent with the source content and a structured-return clause demanding the fingerprint dict shape.
3. Validate the returned dict: must contain `n1_signature`, `n2_terms`, `n3_naming`, `fingerprint_hash`. Reject if any field is missing.
4. Compute the SHA-1 of the canonical-JSON-encoded fingerprint as the cache key.
5. Persist via `state_io.atomic_write_json` to `plugins/naga-observe/state/patterns/<hash>.json`.
6. Publish `naga.pattern.fingerprinted` with `{source_path, fingerprint_hash, n1_signature, n2_terms, captured_at}` via `shared.scripts.events.publish_pattern_fingerprinted`.

## Outputs

- `plugins/naga-observe/state/patterns/<hash>.json` — the fingerprint dict.
- One `naga.pattern.fingerprinted` event on the bus.
- Console: `{fingerprint_hash, n1_signature, top_n2_terms[10]}`.

## Handoff

If the user wants to generate a matching artifact next, they run `/naga:match <source> <target>` — the shaper reads the same `state/patterns/<hash>.json`.

## Failure modes

- **F02 fabrication** — never invent a token absent from the source. The fingerprinter copies tokens verbatim from the parser output.
- **F11 reward hacking** — never weaken the small-source guard to pretend a 5-token file produced a real fingerprint. Return `fingerprint_unreliable: true` and stop.
