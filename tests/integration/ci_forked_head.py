"""Reviewed CI-only subprocess transport for signed anchor-head observations.

No configurable program or endpoint. Launches exactly ci_head_child.py,
through an isolated Python interpreter with a bounded stdio JSON exchange.
Every request uses a newly launched throwaway child; there is no daemon,
socket, Docker access, remote server or production signing-key custody.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

HERE = Path(__file__).resolve().parent
WORKER = HERE / "ci_head_child.py"


class SyntheticProcessHead:
    """Mutable fault modes are only for tests; no code loaded from responses."""

    def __init__(self, synthetic_private_key, *, anchor_id: str, revision: int,
                 worker_sha256: str):
        self._seed = synthetic_private_key.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
        self.anchor_id = anchor_id
        self.revision = revision
        self.worker_sha256 = worker_sha256
        self.mode = "normal"
        self.replay_reply = None
        self._lock = threading.Lock()
        self.pids_seen = []
        self.calls = 0

    def read_current_head(self, ledger_id: str, challenge: str) -> dict:
        # Review-time code pin. Never follow a symlink or choose a path from
        # caller-provided policy/JSON. Each subprocess executes fixed code.
        if (WORKER.is_symlink() or not WORKER.is_file()
                or "sha256:" + hashlib.sha256(WORKER.read_bytes()).hexdigest()
                   != self.worker_sha256):
            raise OSError("synthetic worker code pin invalid")
        with self._lock:
            mode = self.mode
            previous = self.replay_reply
            self.calls += 1
        request = {
            "schema": "ci-anchor-worker/v1", "ledger_id": ledger_id,
            "challenge": challenge, "anchor_id": self.anchor_id,
            "revision": self.revision, "now_unix": self.now_unix,
            "synthetic_seed_hex": self._seed, "mode": mode,
            "replay_reply": previous if mode == "replay" else None,
        }
        raw = json.dumps(request, separators=(",", ":"))
        if len(raw) > 8192:
            raise OSError("synthetic request exceeded size limit")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-B", str(WORKER)],
                input=raw, capture_output=True, text=True,
                timeout=2, check=False,
                env={"PATH": os.environ.get("PATH", ""),
                     "PYTHONHASHSEED": "0"},
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise OSError("synthetic head child unavailable") from None
        with self._lock:
            self.pids_seen.append(proc.args[3] if len(proc.args) > 3 else "child")
        if proc.returncode != 0 or len(proc.stdout) > 8192 or len(proc.stderr) > 4096:
            raise OSError("synthetic head child failed or produced oversized reply")
        try:
            reply = json.loads(proc.stdout)
        except (ValueError, TypeError):
            raise OSError("synthetic malformed child response") from None
        if not isinstance(reply, dict):
            raise OSError("synthetic wrong child response type")
        if mode == "normal":
            with self._lock:
                self.replay_reply = reply
        return reply
