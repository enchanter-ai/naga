"""
Naga engine sanity tests — stdlib only.
Run: python -m unittest tests.test_engines -v
"""
import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "shared" / "scripts"))

from engines.n1_tree_edit import tree_edit_distance
from engines.n2_tfidf import tf, tfidf_vector
from engines.n3_levenshtein import name_distance, name_similarity
from engines.n4_cosine import cosine_similarity
from engines.n5_gauss import update_posterior
from bootstrap_ci import bootstrap_ci


class TestN1TreeEdit(unittest.TestCase):
    def test_identical_trees_have_zero_distance(self):
        a = ast.parse("def f():\n    return 1\n")
        b = ast.parse("def f():\n    return 1\n")
        self.assertEqual(tree_edit_distance(a, b), 0)

    def test_distance_is_non_negative(self):
        a = ast.parse("x = 1\n")
        b = ast.parse("def f():\n    return 1\n")
        d = tree_edit_distance(a, b)
        self.assertIsInstance(d, int)
        self.assertGreaterEqual(d, 0)

    def test_empty_modules_zero_distance(self):
        a = ast.parse("")
        b = ast.parse("")
        self.assertEqual(tree_edit_distance(a, b), 0)

    def test_structure_is_respected(self):
        # Same node-type multiset, different nesting. A flattened sequence
        # edit distance collapses these to 0; Zhang-Shasha must not.
        a = ast.parse("f(a, g(b))\n")
        b = ast.parse("f(g(a, b))\n")
        self.assertGreater(tree_edit_distance(a, b), 0)

    def test_symmetric_distance(self):
        a = ast.parse("def f(x):\n    return x + 1\n")
        b = ast.parse("y = [1, 2, 3]\n")
        self.assertEqual(tree_edit_distance(a, b), tree_edit_distance(b, a))

    def test_relabel_cheaper_than_full_rebuild(self):
        # One differing operator node type (Add vs Sub) should cost a single
        # relabel, cheaper than deleting/reinserting the whole tree.
        a = ast.parse("x + 1\n")
        b = ast.parse("x - 1\n")
        d = tree_edit_distance(a, b)
        self.assertGreater(d, 0)
        self.assertLess(d, tree_edit_distance(a, ast.parse("")))


class TestN2TFIDF(unittest.TestCase):
    def test_tf_strips_stopwords(self):
        counts = tf(["the", "quick", "brown", "the", "fox"])
        self.assertNotIn("the", counts)
        self.assertEqual(counts.get("quick"), 1)
        self.assertEqual(counts.get("fox"), 1)

    def test_empty_tokens_yield_empty_vector(self):
        self.assertEqual(tfidf_vector([], {}, 0), {})

    def test_known_tokens_produce_positive_weights(self):
        v = tfidf_vector(["alpha", "beta", "alpha"], {"alpha": 1, "beta": 5}, 10)
        self.assertIn("alpha", v)
        self.assertIn("beta", v)
        self.assertGreater(v["alpha"], 0.0)


class TestN3Levenshtein(unittest.TestCase):
    def test_identical_names_zero_distance(self):
        self.assertEqual(name_distance("foo_bar", "foo_bar"), 0)

    def test_substitution_costs_one(self):
        self.assertEqual(name_distance("foo", "fob"), 1)

    def test_empty_string_distance_equals_other_length(self):
        self.assertEqual(name_distance("", "abcd"), 4)
        self.assertEqual(name_distance("abc", ""), 3)

    def test_similarity_in_unit_interval(self):
        s = name_similarity("snake_case", "snake_case")
        self.assertEqual(s, 1.0)
        s2 = name_similarity("snake_case", "camelCase")
        self.assertGreaterEqual(s2, 0.0)
        self.assertLessEqual(s2, 1.0)


class TestN4Cosine(unittest.TestCase):
    def test_empty_vectors_zero(self):
        self.assertEqual(cosine_similarity({}, {}), 0.0)
        self.assertEqual(cosine_similarity({"a": 1}, {}), 0.0)

    def test_identical_vectors_one(self):
        v = {"a": 1.0, "b": 2.0}
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=6)

    def test_disjoint_vectors_zero(self):
        self.assertEqual(cosine_similarity({"a": 1.0}, {"b": 1.0}), 0.0)

    def test_similar_vectors_in_unit_interval(self):
        v = cosine_similarity({"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 0.5})
        self.assertGreater(v, 0.0)
        self.assertLessEqual(v, 1.0)


class TestN5Gauss(unittest.TestCase):
    def test_first_observation_seeds_posterior(self):
        p = update_posterior({}, {"fidelity_score": 0.8,
                                  "captured_at": "2026-04-25T00:00:00Z"})
        self.assertEqual(p["n_observations"], 1)
        self.assertAlmostEqual(p["median_fidelity"], 0.8, places=4)
        self.assertEqual(p["sigma"], 0.0)
        self.assertGreaterEqual(p["p10_threshold"], 0.0)

    def test_repeated_same_obs_converges(self):
        p: dict = {}
        for _ in range(20):
            p = update_posterior(p, {"fidelity_score": 0.9,
                                     "captured_at": "2026-04-25T00:00:00Z"})
        self.assertAlmostEqual(p["median_fidelity"], 0.9, places=2)
        self.assertLess(p["sigma"], 0.05)
        self.assertEqual(p["n_observations"], 20)

    def test_p10_never_negative(self):
        p = update_posterior({}, {"fidelity_score": 0.05,
                                  "captured_at": "2026-04-25T00:00:00Z"})
        self.assertGreaterEqual(p["p10_threshold"], 0.0)


class TestBootstrapCI(unittest.TestCase):
    def test_empty_returns_zeros(self):
        self.assertEqual(bootstrap_ci([]), (0.0, 0.0, 0.0, 0))

    def test_single_sample_collapses_band(self):
        v, lo, hi, n = bootstrap_ci([0.7])
        self.assertEqual((v, lo, hi, n), (0.7, 0.7, 0.7, 1))

    def test_multi_sample_band_ordering(self):
        v, lo, hi, n = bootstrap_ci([0.5, 0.6, 0.7, 0.8, 0.9, 0.55, 0.65, 0.75])
        self.assertLessEqual(lo, v)
        self.assertLessEqual(v, hi)
        self.assertEqual(n, 8)


if __name__ == "__main__":
    unittest.main()
