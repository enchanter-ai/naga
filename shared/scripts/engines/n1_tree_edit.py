"""
N1 — Zhang-Shasha tree edit distance (structural AST shape)

Implementation: the Zhang-Shasha (1989) ordered-tree-edit-distance algorithm
over the real parsed AST (see tree_edit_distance below). Unlike a flattened
string edit distance, this respects parent/child structure — two programs with
the same node multiset but different nesting produce a non-zero distance.

Role:
    Structural distance between source and generated artifact. Cost = 1 per
    insert, delete, relabel; relabel is free when node types match. Node label
    is the AST node *type* (e.g. `Call`, `Name`, `FunctionDef`).

Stdlib only: `ast` for Python sources. Classic Zhang-Shasha dynamic program:
LR-keyroots + a forest-distance DP over left-to-right postorder indices.

Reference: Zhang K. and Shasha D. (1989), "Simple Fast Algorithms for the
Editing Distance Between Trees and Related Problems", SIAM J. Comput.
18(6):1245-1262. Complexity O(|T1|*|T2|*min(depth,leaves)^2), stdlib-only.
"""
from __future__ import annotations

import ast


class _Node:
    """Adapter wrapping an ast node as an ordered labeled tree node."""

    __slots__ = ("label", "children")

    def __init__(self, label: str, children: list) -> None:
        self.label = label
        self.children = children


def _adapt(node: ast.AST) -> _Node:
    """Convert an ast subtree into a `_Node` tree, preserving child order.

    Label = node type name. Child order follows `ast.iter_child_nodes`, which
    is the source-code left-to-right order, so the tree stays *ordered* — a
    prerequisite for Zhang-Shasha.
    """
    children = [_adapt(c) for c in ast.iter_child_nodes(node)]
    return _Node(type(node).__name__, children)


def _postorder(root: _Node) -> tuple[list, list]:
    """Left-to-right postorder linearisation.

    Returns (labels, lmld) where, for each postorder index i:
      - labels[i] is the node label at i;
      - lmld[i] is the postorder index of the leftmost-leaf descendant of i.
    Both are the inputs the Zhang-Shasha DP indexes into.
    """
    labels: list = []
    lmld: list = []

    def visit(n: _Node) -> int:
        # index of this node's leftmost-leaf descendant, computed from the
        # first child (or from itself if it is a leaf).
        left = None
        for i, child in enumerate(n.children):
            child_left = visit(child)
            if i == 0:
                left = child_left
        labels.append(n.label)
        idx = len(labels) - 1
        lmld.append(left if left is not None else idx)
        return left if left is not None else idx

    visit(root)
    return labels, lmld


def _keyroots(lmld: list) -> list:
    """LR-keyroots: nodes with no ancestor sharing their leftmost-leaf.

    A node i is a keyroot iff no j > i has lmld[j] == lmld[i]. Returned sorted
    ascending, as the outer Zhang-Shasha loop requires.
    """
    seen: dict = {}
    for i, l in enumerate(lmld):
        seen[l] = i  # keep the largest index for each leftmost-leaf
    return sorted(seen.values())


def _edit_distance(a_labels, a_lmld, b_labels, b_lmld) -> int:
    """Zhang-Shasha treedist over two postorder-linearised forests."""
    a_keyroots = _keyroots(a_lmld)
    b_keyroots = _keyroots(b_lmld)
    na, nb = len(a_labels), len(b_labels)

    # treedist[i][j] = distance between subtree rooted at a-node i and b-node j.
    treedist = [[0] * nb for _ in range(na)]

    for ki in a_keyroots:
        for kj in b_keyroots:
            ai, aj = a_lmld[ki], b_lmld[kj]
            # forestdist over the subforests; offset by (ai-1, aj-1).
            rows = ki - ai + 2
            cols = kj - aj + 2
            fd = [[0] * cols for _ in range(rows)]
            for i in range(1, rows):
                fd[i][0] = fd[i - 1][0] + 1  # delete
            for j in range(1, cols):
                fd[0][j] = fd[0][j - 1] + 1  # insert
            for i in range(1, rows):
                for j in range(1, cols):
                    ni = ai + i - 1  # actual a-index
                    nj = aj + j - 1  # actual b-index
                    if a_lmld[ni] == ai and b_lmld[nj] == aj:
                        # both are subtrees rooted here → relabel path
                        cost = 0 if a_labels[ni] == b_labels[nj] else 1
                        fd[i][j] = min(
                            fd[i - 1][j] + 1,
                            fd[i][j - 1] + 1,
                            fd[i - 1][j - 1] + cost,
                        )
                        treedist[ni][nj] = fd[i][j]
                    else:
                        pi = a_lmld[ni] - ai
                        pj = b_lmld[nj] - aj
                        fd[i][j] = min(
                            fd[i - 1][j] + 1,
                            fd[i][j - 1] + 1,
                            fd[pi][pj] + treedist[ni][nj],
                        )
    return treedist[na - 1][nb - 1]


def tree_edit_distance(source_tree: ast.AST, target_tree: ast.AST) -> int:
    """Returns int >= 0. 0 = structurally identical. Cost = 1 per node op.

    Zhang-Shasha ordered-tree edit distance over the real AST. Insert, delete,
    and relabel each cost 1 (relabel free when node types match). Because the
    algorithm walks the tree structure rather than a flattened sequence,
    differently nested programs with the same node multiset — e.g.
    `f(a, g(b))` vs `f(g(a, b))` — produce a non-zero distance.

    For very large trees, callers should chunk via top-level definitions — see
    docs/science/README.md § N1 Implementation notes.
    """
    a_labels, a_lmld = _postorder(_adapt(source_tree))
    b_labels, b_lmld = _postorder(_adapt(target_tree))
    if not a_labels and not b_labels:
        return 0
    if not a_labels:
        return len(b_labels)
    if not b_labels:
        return len(a_labels)
    return _edit_distance(a_labels, a_lmld, b_labels, b_lmld)
