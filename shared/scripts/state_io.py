"""
state_io.py — atomic write-tmp-rename persistence helpers.

Every JSON state file in Naga goes through `atomic_write_json`. No direct
open('w') on state paths, ever. See `shared/foundations/conduct/verification.md` and
Gorgon's state_io.py for the invariant this enforces.

JSONL appends go through `append_jsonl`, which acquires an exclusive file
lock per write (msvcrt on Windows, fcntl elsewhere) so concurrent emitters
across plugin boundaries cannot interleave bytes mid-line. See finding F-016
in the ecosystem audit.

Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path | str, data: Any) -> None:
    """Atomically write `data` as JSON to `path` via write-tmp-rename.

    - Creates parent dirs if missing.
    - Writes to a temp file in the same directory (so rename is atomic on POSIX and Windows).
    - fsyncs the temp file before rename.
    - Never partial-writes the destination.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=p.name + ".",
        suffix=".tmp",
        dir=str(p.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"), ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, p)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_json(path: Path | str, default: Any = None) -> Any:
    """Read JSON; return `default` if the file is missing or malformed."""
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def append_jsonl(path: Path | str, record: dict) -> None:
    """JSONL append: locked + flushed. Cross-platform.

    Fail-open: never raises to the caller. The exclusive file lock prevents
    concurrent emitters (e.g., naga-learning's pre-compact hook racing the
    n5_gauss heartbeat) from interleaving partial-line bytes that would
    corrupt downstream Bayesian posterior reads.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, separators=(",", ":")) + "\n"
    try:
        with p.open("a", encoding="utf-8") as fh:
            if sys.platform == "win32":
                import msvcrt
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
                    fh.write(line)
                    fh.flush()
                    os.fsync(fh.fileno())
                finally:
                    try:
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
            else:
                import fcntl
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                    fh.write(line)
                    fh.flush()
                    os.fsync(fh.fileno())
                finally:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
