"""
N1 — Node-type sequence edit distance (AST-shape proxy)

Implementation: Wagner-Fischer string edit distance over the *flattened*
postorder sequence of AST node *types* (see tree_edit_distance below). This is
NOT the Zhang-Shasha tree-edit-distance algorithm this module was previously
labelled with — flattening the tree to a sequence discards structure — so the
earlier citation to Zhang & Shasha (1989), SIAM J. Comput. 18(6):1245-1262 was
inaccurate and has been removed.

Role:
    AST-shape distance between source and generated artifact. Cost = 1 per
    insert, delete, relabel over the node-type sequence.

Stdlib only: `ast` for Python sources, `xml.etree.ElementTree` for XML/HTML.
Dict-based DP table over postorder traversal indices.

LIMITATION (VF-08): because only the postorder node-*type* sequence is compared,
structurally different programs with the same node multiset collapse to distance
0 — e.g. `f(a, g(b))` vs `f(g(a, b))` scores 0. Treat this as a coarse
same-shape screen, not a true tree-edit distance, until a real Zhang-Shasha
implementation replaces it.
"""
from __future__ import annotations

import ast


def _postorder(node: ast.AST) -> list:
    """Postorder traversal (leaves-first) producing the node-type sequence."""
    out: list = []
    for child in ast.iter_child_nodes(node):
        out.extend(_postorder(child))
    out.append(node)
    return out


def tree_edit_distance(source_tree: ast.AST, target_tree: ast.AST) -> int:
    """Returns int >= 0. 0 = identical shape. Cost = 1 per insert/delete/relabel.

    Wagner-Fischer DP over postorder sequences. O(n*m) time, O(n*m) space.
    For very large trees, callers should chunk via subtree hashing — see
    docs/science/README.md § N1 Implementation notes.
    """
    src = _postorder(source_tree)
    tgt = _postorder(target_tree)
    n, m = len(src), len(tgt)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if type(src[i - 1]) is type(tgt[j - 1]) else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    return dp[n][m]
