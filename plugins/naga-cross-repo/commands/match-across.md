---
description: Cross-repo pattern replication between sibling repositories.
---

# /naga:match-across

Reads a source artifact in one repository tree and generates a matched-form artifact in another.

## Usage

```
/naga:match-across <source-repo>/<source-path> <target-repo>/<target-path>
```

## Arguments

| Argument | Type | Default | Purpose |
|----------|------|---------|---------|
| source   | path | —       | Source path including repo root. |
| target   | path | —       | Target path including repo root. |

## Example

```
/naga:match-across <repo-root>/wixie/../foundations/packages/core/conduct/discipline.md <repo-root>/naga/../foundations/packages/core/conduct/discipline.md
```

## Invokes

This command invokes the `naga-match-across` skill. See [../skills/naga-match-across/SKILL.md](../skills/naga-match-across/SKILL.md).
