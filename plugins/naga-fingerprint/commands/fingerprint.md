---
description: Read-only stylistic and naming-convention report for an artifact.
---

# /naga:fingerprint

Returns the top-15 N2 TF-IDF terms and the N3 naming-convention distribution for `<source>`. No state writes, no events.

## Usage

```
/naga:fingerprint <source>
```

## Arguments

| Argument | Type | Default | Purpose |
|----------|------|---------|---------|
| source   | path | —       | Path to the artifact to inspect. |

## Example

```
/naga:fingerprint shared/foundations/conduct/discipline.md
```

## Invokes

This command invokes the `naga-fingerprint` skill. See [../skills/naga-fingerprint/SKILL.md](../skills/naga-fingerprint/SKILL.md).
