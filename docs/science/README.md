# Formal Derivations — Naga

This document holds the paper-grounded derivations for Naga's five engines.
One section per engine listed in `CLAUDE.md § Algorithms`.

---

## N1 — Zhang-Shasha Tree Edit Distance (structural AST)

**Reference (implemented):** Zhang K. and Shasha D. (1989), "Simple Fast Algorithms for the Editing Distance Between Trees and Related Problems", SIAM J. Comput. 18(6):1245-1262 — the ordered-tree edit distance, applied directly to the parsed AST.

**VF-08 (resolved):** N1 previously flattened the AST to its postorder node-type sequence and ran a Wagner-Fischer *string* edit distance, which discarded structure — structurally different trees with the same node multiset (e.g. `f(a, g(b))` vs `f(g(a, b))`) collapsed to distance 0. The Zhang-Shasha implementation walks the tree structure, so those cases now yield a non-zero distance (2 for that example). The degeneracy is closed.

**Signature:** `tree_edit_distance(source_tree: ast.AST, target_tree: ast.AST) -> int`

### Derivation

For ordered labeled trees T1 and T2, the tree edit distance is the minimum
cost of transforming T1 into T2 via a sequence of insert / delete / relabel
operations on individual nodes. Zhang and Shasha showed that the problem
admits an O(|T1| * |T2| * min(depth(T1), leaves(T1)) * min(depth(T2), leaves(T2)))
solution via dynamic programming over postorder-numbered subtrees.

Naga implements exactly this: left-to-right postorder numbering, leftmost-leaf
descendants `l(i)`, LR-keyroots, and a forest-distance DP nested inside the
keyroot loop. Node label = AST node type; cost = 1 per insert / delete, and
relabel is free when types match, 1 otherwise. The metric is symmetric, zero
on identical trees, and equals the node count when compared against an empty
tree — the latter is what the fingerprinter persists as `n1_signature`.

### Implementation notes

- Stdlib only. `ast.parse()` for Python sources; each node adapted to an
  ordered `(label, children)` node via `ast.iter_child_nodes` (source order).
- The persisted `n1_signature` (distance from the empty tree = node count) is a
  size scalar; full structural discrimination happens on the pairwise call at
  `/naga:match` and `/naga:validate`, which re-parse the source.
- For very large source trees (> 50 KB), the caller should chunk the source
  into top-level definitions and score each subtree separately.

### Failure modes

- **SyntaxError on source.** `ast.parse` raises; caller falls back to text-only
  N2 + N3 fingerprint and marks `ast_available: false`.
- **Cross-language source/target.** AST-shape does not transfer between Python
  and markdown; naga-orchestrator decides the relaxation set.

---

## N2 — Spaerck Jones TF-IDF

**Reference:** Spaerck Jones K. (1972), "A statistical interpretation of term
specificity and its application in retrieval", Journal of Documentation
28(1):11-21.

**Signature:** `tfidf_vector(tokens: list, corpus_df: dict, n_docs: int) -> dict`

### Derivation

For term t in document d within a corpus C of N documents, the TF-IDF weight is:

    w(t, d) = tf(t, d) * idf(t, C)

where `tf(t, d) = count(t, d) / sum_{t'} count(t', d)` and
`idf(t, C) = log((N + 1) / (df(t) + 1)) + 1` (smoothed to handle unseen
terms). The intuition: terms common across the corpus get suppressed;
terms specific to this document get amplified.

### Implementation notes

- Stdlib only. `collections.Counter` for term frequency; `math.log` for IDF.
- Stopword stripping via a frozen set of low-information tokens.
- `corpus_df` is pre-computed per pattern-class and cached at
  `state/corpus_df.json`. Cold-start: empty `corpus_df` -> all terms get
  `idf = log(N+1) + 1`.

### Failure modes

- **Empty token list** -> empty vector (callers must handle).
- **Cold-start corpus** -> over-weights every term equally; mark
  `cold_start: true` until `n_docs >= 5`.

---

## N3 — Levenshtein Edit Distance

**Reference:** Levenshtein V.I. (1966), "Binary codes capable of correcting
deletions, insertions, and reversals", Soviet Physics Doklady 10(8):707-710.

**Signature:** `name_distance(source_name: str, candidate_name: str) -> int`

### Derivation

The Levenshtein distance between strings a and b is the minimum number of
single-character insertions, deletions, or substitutions required to
transform a into b. The Wagner-Fischer DP (1974) computes it in O(|a| * |b|)
time and O(min(|a|, |b|)) space via a rolling row.

### Implementation notes

- Stdlib only. Explicit DP via two list rows — no third-party Levenshtein
  package.
- For [0, 1] similarity, the `name_similarity` helper falls back to
  `difflib.SequenceMatcher.ratio()` — quicker and more forgiving for
  N4-vector entry.

### Failure modes

- **Empty string in either argument** -> distance = length of the other.
- **Unicode normalisation** -> caller is responsible; Naga compares strings
  as-is.

---

## N4 — Salton-Wong-Yang Cosine Similarity

**Reference:** Salton G., Wong A., Yang C.S. (1975), "A vector space model
for automatic indexing", Communications of the ACM 18(11):613-620.

**Signature:** `cosine_similarity(vec_a: dict, vec_b: dict) -> float`

### Derivation

For two vectors a and b in a shared term-space, the cosine similarity is:

    cos(a, b) = (a . b) / (||a|| * ||b||)

bounded in [-1, 1]. For non-negative weight vectors (as in TF-IDF), the
output is bounded in [0, 1]: 1.0 means identical direction, 0.0 means
orthogonal.

### Implementation notes

- Stdlib only. Pure-Python list comprehensions over the intersection of keys
  for the dot product; `math.sqrt` for norms.
- Output clamped to [0, 1] to handle floating-point drift.
- No numpy, no scipy.

### Failure modes

- **Empty vector on either side** -> 0.0 (callers must distinguish from
  legitimate zero-similarity).
- **Disjoint key sets** -> 0.0; single-axis matchers will trigger this.
  Counter: ensure N1 + N2 + N3 features all populate the vector.

---

## N5 — Gauss Accumulation: Pattern-Fidelity Drift

**Reference:** Brown R.G. (1956), "Exponential Smoothing for Predicting
Demand"; Holt C.C. (1957), "Forecasting Trends and Seasonals by
Exponentially Weighted Moving Averages" (exponential-smoothing
foundation for the EMA update, paired with a conjugate Beta-Binomial
posterior for the accept/reject signal).

**Ecosystem precedent:** Wixie F6, Emu A7 (renamed EMA), Crow H6 (renamed
EMA), Djinn D5, Gorgon G5.

**Signature:** `update_posterior(prior: dict, observation: dict, alpha: float = 0.3) -> dict`

### Derivation

For a stream of fidelity observations {x_t}, maintain the EMA mean and an
EMA-of-squared-deviation variance estimator:

    mu_t     = (1 - alpha) * mu_{t-1} + alpha * x_t
    sigma2_t = (1 - alpha) * sigma2_{t-1} + alpha * (x_t - mu_{t-1})^2
    sigma_t  = sqrt(sigma2_t)

The posterior 10th-percentile threshold under a normal approximation is:

    p10_t = max(0, mu_t - 1.2816 * sigma_t)

`p10_t` is the per-(pattern-class, target-domain) acceptable-fidelity floor
that the shaper must clear. Half-life ~ 30 observations at alpha = 0.3.

### Implementation notes

- Stdlib only. JSONL append-only learnings via `state_io.append_jsonl`;
  posterior persisted via `state_io.atomic_write_json`.
- Pattern classes (canonical): {claude-md, python-module, plugin-json,
  hook-script, agent-md, test-module, docs-md, generic}.
- Cold-start: first observation seeds the posterior with `sigma = 0`,
  `p10 = max(0, x - 0.1)`. Subsequent observations refine.

### Failure modes

- **Class drift** — same pattern_class label across two repos with divergent
  conventions. Sigma inflates; surface as `class_drift_detected: true`
  rather than averaging away the divergence.
- **Cold-start advisory** — when `n_observations < 5`, mark `cold_start: true`
  and hold the threshold at the global default p10 = 0.6.
