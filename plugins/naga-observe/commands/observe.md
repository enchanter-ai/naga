---
description: Extract the pattern fingerprint from a source artifact and persist it to state.
---

# /naga:observe

Extracts the structural and stylistic fingerprint of `<source>` via N1 AST + N2 TF-IDF and persists it to `plugins/naga-observe/state/patterns/<hash>.json`.

## Usage

```
/naga:observe <source>
```

## Arguments

| Argument | Type | Default | Purpose |
|----------|------|---------|---------|
| source   | path | —       | Absolute or repo-relative path to the artifact to fingerprint. |

## Example

```
/naga:observe ../enchanter-foundations/packages/core/conduct/discipline.md
```

Returns the fingerprint hash and the top-10 N2 terms; persists the full record under state.

## Invokes

This command invokes the `naga-observe` skill. See [../skills/naga-observe/SKILL.md](../skills/naga-observe/SKILL.md).
