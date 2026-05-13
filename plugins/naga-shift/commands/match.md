---
description: Generate a new artifact at <target> matching the fingerprint of <source>.
---

# /naga:match

Generates a target artifact whose N4 cosine fidelity to the source fingerprint clears the per-(class, domain) N5 threshold.

## Usage

```
/naga:match <source> <target>
```

## Arguments

| Argument | Type | Default | Purpose |
|----------|------|---------|---------|
| source   | path | —       | Path to the artifact to replicate. Auto-fingerprinted if not yet observed. |
| target   | path | —       | Destination path for the new artifact. |

## Example

```
/naga:match ../foundations/packages/core/conduct/discipline.md shared/conduct/discipline-mirror.md
```

## Invokes

This command invokes the `naga-match` skill. See [../skills/naga-match/SKILL.md](../skills/naga-match/SKILL.md).
