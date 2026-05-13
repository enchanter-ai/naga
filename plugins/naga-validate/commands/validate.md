---
description: Score the fidelity of a generated artifact against a source pattern.
---

# /naga:validate

Returns `(score, ci_low, ci_high, N, verdict)` for `<new>` measured against `<source>`.

## Usage

```
/naga:validate <new> <source>
```

## Arguments

| Argument | Type | Default | Purpose |
|----------|------|---------|---------|
| new      | path | —       | The artifact under validation. |
| source   | path | —       | The reference pattern. Auto-fingerprinted if not yet observed. |

## Example

```
/naga:validate shared/conduct/discipline-mirror.md ../vis/packages/core/conduct/discipline.md
```

## Invokes

This command invokes the `naga-validate` skill. See [../skills/naga-validate/SKILL.md](../skills/naga-validate/SKILL.md).
