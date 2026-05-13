# Naga — Agent Contract

Audience: Claude. Naga observes a source artifact's structural and stylistic
fingerprint and generates new artifacts that match the observed shape,
vocabulary, and naming idiom. Pattern replication of EXISTING artifacts —
orthogonal to prompt engineering from scratch (Wixie), structural intelligence
(Gorgon), per-change trust (Crow), and intent anchoring (Djinn).

## Shared behavioral modules

These apply to every skill in every plugin. Load once; do not re-derive.

- @../vis/packages/core/conduct/discipline.md — coding conduct: think-first, simplicity, surgical edits, goal-driven loops
- @../vis/packages/core/conduct/capability-fidelity.md — contracts survive capability gaps: recover, escalate, or abort; never silently substitute
- @../vis/packages/core/conduct/doubt-engine.md — adversarial self-check before agreement; counter to F01 sycophancy
- @../vis/packages/core/conduct/context.md — attention-budget hygiene, U-curve placement, checkpoint protocol
- @../vis/packages/core/conduct/verification.md — independent checks, baseline snapshots, dry-run for destructive ops
- @../vis/packages/core/conduct/verdict-calibration.md — every verdict (DEPLOY/PASS/COMPLETE/VERIFIED) carries n, sampling method, and a calibration qualifier; vis-side abstraction over the wixie DEPLOY bar
- @../vis/packages/core/conduct/delegation.md — subagent contracts, tool whitelisting, parallel vs. serial rules
- @../vis/packages/core/conduct/failure-modes.md — 14-code taxonomy for accumulated-learning logs
- @../vis/packages/core/conduct/tool-use.md — tool-choice hygiene, error payload contract, parallel-dispatch rules
- @../vis/packages/skills/conduct/formatting.md — per-target format (XML/Markdown/minimal/few-shot), prefill + stop sequences
- @../vis/packages/skills/conduct/skill-authoring.md — SKILL.md frontmatter discipline, discovery test
- @../vis/packages/core/conduct/hooks.md — advisory-only hooks, injection over denial, fail-open
- @../vis/packages/core/conduct/metacognition.md — periodic goal-restate; fires every K=8 tool-uses or on user meta-question
- @../vis/packages/core/conduct/precedent.md — log self-observed failures to `state/precedent-log.md`; consult before risky steps
- @../vis/packages/core/conduct/precedent-freshness.md — verify self-authored memory/precedent/briefings before relying on them: Class-A surfaces (path/function/flag) get a Glob/Grep existence check; Class-B snapshots get a git-log freshness check; Class-C feedback rules are trusted unless contradicted
- @../vis/packages/core/conduct/prior-art-discovery.md — F28 counter: run the 5-target discovery pass (shared/scripts, packages/*/skills, state/proposals, slug-glob, signature-grep) before authoring a new tool/script/skill/module
- @../vis/packages/core/conduct/reversibility-foresight.md — classify action reversibility (trivial/costly/impossible) before acting; confirmation scales with tier
- @../vis/packages/core/conduct/substrate-consumption.md — read-side complement to precedent.md: consume briefing, MEMORY, learnings, and precedent before acting; counter to F24 substrate-blindness
- @../vis/packages/core/conduct/sunk-cost-iteration.md — stop-and-re-ask after 2 INCONCLUSIVE/BLOCKED results on the same artifact; iteration is not an authorization to keep patching
- @../vis/packages/core/conduct/tier-sizing.md — Opus intent-level, Sonnet decomposed, Haiku senior-to-junior
- @../vis/packages/web/conduct/web-fetch.md — WebFetch is Haiku-tier-only; cache and budget
- @shared/conduct/inference-substrate.md — emit-only contract for the Wixie inference engine

When a module conflicts with a plugin-local instruction, the plugin wins — but log the override.

## Lifecycle

Naga is **skill-invoked by design**, like Wixie. Pattern replication is a
deliberate developer request ("make me a new thing like this"); it is not a
continuous background signal. Every sub-plugin except `naga-learning` is
fired by a slash command. The single hook (PreCompact -> naga-learning)
exists ONLY to persist the cross-session fidelity posterior.

| Event or Skill                               | Sub-plugin         | Role                                                                |
|----------------------------------------------|--------------------|---------------------------------------------------------------------|
| /naga:observe `<source>`                     | naga-observe       | Extract fingerprint via N1 + N2; persist `state/patterns/<hash>.json` |
| /naga:match `<source> <target>`              | naga-shift         | Generate target conforming to fingerprint via N1+N2+N3+N4 + N5 gate |
| /naga:validate `<new> <source>`              | naga-validate      | Score fidelity (N1 + N4) with bootstrap CI                          |
| /naga:match-across `<src-repo>` `<tgt-repo>` | naga-cross-repo    | Cross-repo replication; orchestrator decides relaxation set         |
| /naga:fingerprint `<source>`                 | naga-fingerprint   | Read-only N2 + N3 report; no state writes                           |
| PreCompact                                   | naga-learning      | Update N5 per-(pattern-class x target-domain) posterior             |

See `./plugins/naga-learning/hooks/hooks.json` for the single matcher.
Agents in `./shared/agents/`.

## Algorithms

N1 Zhang-Shasha Tree Edit Distance · N2 Spaerck Jones TF-IDF ·
N3 Levenshtein Edit Distance · N4 Salton-Wong-Yang Cosine Similarity ·
N5 Gauss Accumulation (fidelity drift). Derivations in
`docs/science/README.md`. **Defining engine:** N4 cosine fidelity score —
no single axis is permitted to dominate.

| ID | Name                                  | Plugin                          | Algorithm |
|----|---------------------------------------|---------------------------------|-----------|
| N1 | Zhang-Shasha Tree Edit Distance       | naga-observe, naga-shift, naga-validate, naga-cross-repo | Postorder Wagner-Fischer DP on `ast.parse` output. |
| N2 | Spaerck Jones TF-IDF                  | naga-observe, naga-shift, naga-cross-repo, naga-fingerprint | `Counter` term frequency * smoothed `log((N+1)/(df+1))+1` IDF. |
| N3 | Levenshtein Edit Distance             | naga-shift, naga-cross-repo, naga-fingerprint | Wagner-Fischer DP over identifier strings; `difflib` ratio for [0,1] similarity. |
| N4 | Salton-Wong-Yang Cosine Similarity    | naga-shift, naga-validate, naga-cross-repo | Pure-Python dot-product over feature dicts; clamp to [0,1]. |
| N5 | Gauss Accumulation: Fidelity Drift    | naga-learning                   | EMA mean + EMA variance + p10 = mu - 1.2816 * sigma per-(class, domain). |

## Behavioral contracts

Markers: **[H]** hook-enforced (deterministic) · **[A]** advisory (relies on your adherence).

1. **IMPORTANT — Honest-numbers contract on every advisory.** [A] Every
   emitted `naga.fidelity.measured` event and every `/naga:validate` row
   carries `(score, ci_low, ci_high, N)`. Missing N -> reject the row. The
   Haiku validator (naga-fingerprinter) enforces this gate.
2. **YOU MUST NOT collapse to a single axis.** [A] N1 (shape), N2
   (vocabulary), and N3 (naming) MUST jointly contribute to the N4 cosine
   score. A perfect-AST-shape, alien-naming output is rejected.
3. **YOU MUST stop at fingerprint extraction.** [A] When asked to "make
   this look like X", Naga does NOT call into Wixie's technique-selection
   surface. Naga REPLICATES the observed source; Wixie ENGINEERS from a
   technique catalog. Subscribe to `wixie.prompt.crafted` to propagate seeds;
   do not engineer.
4. **YOU MUST escalate cross-domain transfers.** [A] When source and target
   domains diverge (e.g., `.py` -> `.md`), the Sonnet shaper escalates to
   the Opus orchestrator for the relaxation set. Do not silently force a
   `.py` AST signature into a `.md` artifact.

## State paths

| State file                                                  | Owner             | Purpose                                                        |
|-------------------------------------------------------------|-------------------|----------------------------------------------------------------|
| `plugins/naga-observe/state/patterns/<hash>.json`           | naga-observe      | Persisted fingerprint dict per source-artifact hash            |
| `plugins/naga-learning/state/posterior.json`                | naga-learning     | N5 per-(pattern-class x target-domain) fidelity posterior      |
| `plugins/naga-learning/state/learnings.jsonl`               | naga-learning     | Append-only compaction-event log                               |
| `plugins/<sub>/state/precedent-log.md`                      | per sub-plugin    | Self-observed operational failures (see @../vis/packages/core/conduct/precedent.md) |

## Agent tiers

| Tier         | Model  | Used for                                                          |
|--------------|--------|-------------------------------------------------------------------|
| Orchestrator | Opus   | Cross-domain relaxation judgment (naga-orchestrator)              |
| Executor     | Sonnet | Generation under fingerprint constraint (naga-shaper)             |
| Validator    | Haiku  | Feature extraction + honest-numbers gate (naga-fingerprinter)     |

Respect the tiering. Routing a Haiku validation task to Opus burns budget and breaks the cost contract.

## Anti-patterns

- **Single-axis style matchers.** Naming-only or AST-only output looks
  almost-right and gets rejected by reviewers. Counter: N1 + N2 + N3 jointly
  feed N4; N5 thresholds reject single-axis-perfect outputs.
- **Template-based scaffolding (Cookiecutter / Jinja2 / LangChain templates).**
  Rigid templates encode one shape and cannot adapt. Counter: Naga has no
  template authoring step — the source IS the spec at invocation time.
- **Few-shot LLM style transfer with no constraint.** The model averages
  examples against its prior and washes out source-specific minority
  patterns. Counter: the fingerprint is computed deterministically and
  passed as a hard constraint to the shaper.
- **Conflating Naga with Wixie.** Wixie engineers prompts from scratch via
  named techniques. Naga replicates an existing artifact's shape. Subscribe
  to `wixie.prompt.crafted` to propagate seeds; do NOT call Wixie's
  technique-selection surface.

---

## Brand invariants (survive unchanged into every sibling)

1. **Zero external runtime deps.** Hooks: bash + jq only. Scripts: Python 3.8+ stdlib only. No npm/pip/cargo at runtime.
2. **Managed agent tiers.** Opus = orchestrator/judgment. Sonnet = executor/loops. Haiku = validator/format.
3. **Named formal algorithm per engine.** ID prefix letter + number. Academic-style citation in the docstring.
4. **Emu-style marketplace.** Each sub-plugin ships `.claude-plugin/plugin.json` + `{agents,commands,hooks,skills,state}/` + `README.md`.
5. **Dark-themed PDF report.** Produced by `docs/architecture/generate.py` (Phase 2).
6. **Gauss Accumulation learning.** Per-session learnings at `plugins/naga-learning/state/posterior.json`.
7. **enchanted-mcp event bus.** Inter-plugin coordination via published/subscribed events namespaced `naga.<event>`.
8. **Diagrams from source of truth.** `docs/architecture/generate.py` (Phase 2) reads `plugin.json` + `hooks.json` + `SKILL.md` frontmatter.

Events this plugin publishes: `naga.pattern.fingerprinted`, `naga.artifact.generated`, `naga.fidelity.measured`, `naga.pattern.refreshed`.
Events this plugin subscribes to (optional): `gorgon.snapshot.captured`, `wixie.prompt.crafted`.
