"""
Event-bus helper shape tests: wrappers in shared/scripts/events/__init__.py
must be importable, exposed via __all__, and fail-open (no exception escapes
the wrapper, regardless of arg quality).

Also asserts the publish.py branding contract: log prefix is `[naga:publish]`
and the storage path uses `naga/<repo_id>/events.jsonl` under XDG_STATE_HOME.

Run: python -m unittest tests.test_events_helpers -v
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "shared" / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from shared.scripts.events import (  # noqa: E402
    publish_artifact_generated,
    publish_fidelity_measured,
    publish_pattern_fingerprinted,
    publish_pattern_refreshed,
)
import shared.scripts.events as events_pkg  # noqa: E402
import publish as publish_mod  # noqa: E402


class TestEventHelpersFailOpen(unittest.TestCase):
    """Every helper swallows exceptions and never propagates to the caller."""

    def setUp(self):
        # Route any actual writes into a disposable dir.
        self._tmp = tempfile.TemporaryDirectory()
        self._prev_xdg = os.environ.get("XDG_STATE_HOME")
        os.environ["XDG_STATE_HOME"] = self._tmp.name

    def tearDown(self):
        if self._prev_xdg is None:
            os.environ.pop("XDG_STATE_HOME", None)
        else:
            os.environ["XDG_STATE_HOME"] = self._prev_xdg
        self._tmp.cleanup()

    def test_all_helpers_exported(self):
        self.assertEqual(
            set(events_pkg.__all__),
            {
                "publish_pattern_fingerprinted",
                "publish_artifact_generated",
                "publish_fidelity_measured",
                "publish_pattern_refreshed",
            },
        )

    def test_pattern_fingerprinted_happy_path_writes_event(self):
        publish_pattern_fingerprinted(
            source_path="a.py",
            fingerprint_hash="deadbeef",
            n1_signature="sig",
            n2_terms=["x", "y"],
            captured_at="2026-05-21T00:00:00Z",
        )
        # An events.jsonl should now exist somewhere under the tmp XDG dir.
        hits = list(Path(self._tmp.name).rglob("events.jsonl"))
        self.assertEqual(len(hits), 1, "expected exactly one events.jsonl")
        text = hits[0].read_text(encoding="utf-8")
        self.assertIn("naga.pattern.fingerprinted", text)

    def test_pattern_fingerprinted_swallows_bad_n2_terms(self):
        # n2_terms=None — list(None) raises TypeError inside the wrapper.
        # The contract requires this to be logged to stderr, not raised.
        buf = io.StringIO()
        with redirect_stderr(buf):
            try:
                publish_pattern_fingerprinted(
                    source_path="a.py",
                    fingerprint_hash="deadbeef",
                    n1_signature="sig",
                    n2_terms=None,  # type: ignore[arg-type]
                    captured_at="2026-05-21T00:00:00Z",
                )
            except Exception as exc:  # pragma: no cover
                self.fail(f"helper must not raise; got {exc!r}")
        self.assertIn("publish_pattern_fingerprinted swallowed", buf.getvalue())

    def test_pattern_refreshed_swallows_bad_posterior(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            try:
                publish_pattern_refreshed(
                    pattern_class="python-module",
                    n_observations=3,
                    posterior=42,  # type: ignore[arg-type] — dict(42) raises
                )
            except Exception as exc:  # pragma: no cover
                self.fail(f"helper must not raise; got {exc!r}")
        self.assertIn("publish_pattern_refreshed swallowed", buf.getvalue())

    def test_artifact_generated_and_fidelity_do_not_raise(self):
        # Smoke: well-formed calls return None silently.
        self.assertIsNone(
            publish_artifact_generated(
                source_path="a", target_path="b",
                fidelity_score=0.9, ci_low=0.8, ci_high=0.95, N=30,
            )
        )
        self.assertIsNone(
            publish_fidelity_measured(
                generated_path="g", source_pattern="s",
                score=0.9, ci_low=0.8, ci_high=0.95, N=30,
            )
        )


class TestPublishBranding(unittest.TestCase):
    """publish.py must be naga-branded, not pech."""

    def test_log_prefix_is_naga_publish(self):
        src = (SCRIPTS_DIR / "publish.py").read_text(encoding="utf-8")
        self.assertIn("[naga:publish]", src)
        self.assertNotIn("[pech:publish]", src)
        self.assertNotIn("pech", src.lower())

    def test_events_path_uses_naga_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            prev = os.environ.get("XDG_STATE_HOME")
            os.environ["XDG_STATE_HOME"] = tmp
            try:
                path = publish_mod._events_path()
            finally:
                if prev is None:
                    os.environ.pop("XDG_STATE_HOME", None)
                else:
                    os.environ["XDG_STATE_HOME"] = prev
            parts = path.parts
            self.assertIn("naga", parts)
            self.assertNotIn("pech", parts)
            self.assertEqual(path.name, "events.jsonl")


if __name__ == "__main__":
    unittest.main()
