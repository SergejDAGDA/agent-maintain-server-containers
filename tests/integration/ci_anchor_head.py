"""Disposable, in-process synthetic signed current-anchor head responder.

A fake source in the same GitHub runner, never a production authority.
The key is generated during the test and is not remote or protected.
"""
from __future__ import annotations

import time

from current_anchor_source_contract import CLAIM, SCHEMA, canonical_head


class SyntheticCiHeadSource:
    def __init__(self, signing_key, *, anchor_id: str, revision: int):
        self._key = signing_key
        self.anchor_id = anchor_id
        self.revision = revision
        self.available = True
        self.old_reply = None
        self.replay = False

    def read_current_head(self, ledger_id: str, challenge: str) -> dict:
        if not self.available:
            raise OSError("synthetic CI source unavailable")
        if self.replay:
            return self.old_reply
        issued = int(time.time())
        statement = {
            "schema": SCHEMA, "claim": CLAIM,
            "source_id": "ci-registered-head", "key_id": "ci-head-key",
            "ledger_id": ledger_id, "challenge": challenge,
            "anchor_id": self.anchor_id, "revision": self.revision,
            "issued_at_unix": issued, "expires_at_unix": issued + 60,
        }
        raw = canonical_head(statement)
        self.old_reply = {
            "message": statement, "signature": self._key.sign(raw).hex(),
        }
        return self.old_reply
