"""TEST-ONLY synthetic cross-layer evidence gate for the disposable F2 fixture.

Not shipped by the skill. It combines an already proven exact snapshot,
reviewed signed-head source, witness-ledger continuity and a local monotonic
publication journal. A matching *local* chain can never prove off-host
recovery or authorize real changes.

No host commands, backup capture, restore, SQL writes, network, credential
loading or dynamic adapter selection. The exact-snapshot callback and
reviewed objects are supplied exclusively by synthetic harness code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from current_anchor_source_contract import ReviewedHeadReader
from monotonic_head_contract import SyntheticMonotonicJournal
from witness_attestation_contract import WitnessTrustStore


@dataclass(frozen=True)
class SyntheticChainDecision:
    status: str
    blockers: tuple[str, ...]
    restore_authorized: bool = False
    off_host_proven: bool = False
    eligible_for_prune: bool = False


def _block(code: str) -> SyntheticChainDecision:
    return SyntheticChainDecision("BLOCKED", (code,))


def evaluate_test_chain(
    *, snapshot_check: Callable[[], None],
    signed_reader: ReviewedHeadReader,
    ledger_connection: Any,
    signed_anchor: Any,
    anchor_trust: WitnessTrustStore,
    publication: SyntheticMonotonicJournal,
    ledger_id: str,
    expected_anchor_id: str,
    trusted_ledger_revision: int,
    trusted_publication_revision: int,
    now_unix: int,
) -> SyntheticChainDecision:
    """Combine independently exercised *synthetic* read-side gates.

    All failures are constant codes. A local match is not an operational
    security claim. The caller's two revision floors are NOT protected here.
    """
    if (not callable(snapshot_check)
            or not isinstance(signed_reader, ReviewedHeadReader)
            or not isinstance(anchor_trust, WitnessTrustStore)
            or not isinstance(publication, SyntheticMonotonicJournal)
            or not isinstance(ledger_id, str) or not ledger_id
            or not isinstance(expected_anchor_id, str)
            or len(expected_anchor_id) != 64
            or any(c not in "0123456789abcdef" for c in expected_anchor_id)
            or type(trusted_ledger_revision) is not int
            or type(trusted_publication_revision) is not int
            or type(now_unix) is not int
            or not 0 <= trusted_ledger_revision <= 200_000
            or not 0 <= trusted_publication_revision <= 200_000
            or now_unix < 0):
        return _block("chain:invalid_trusted_context")
    try:
        snapshot_check()
    except Exception:
        return _block("chain:snapshot_or_key_unavailable")
    try:
        verified = signed_reader.evaluate(
            ledger_connection, signed_anchor, anchor_trust,
            ledger_id=ledger_id, now_unix=now_unix,
            trusted_min_revision=trusted_ledger_revision,
        )
    except Exception:
        return _block("chain:signed_source_unavailable")
    if (verified.status != "SIGNED_SOURCE_CLAIM_MATCHED"
            or verified.anchor_id != expected_anchor_id):
        return _block("chain:signed_head_or_ledger_mismatch")
    try:
        local_head = publication.current(
            trusted_min_revision=trusted_publication_revision,
        )
    except Exception:
        return _block("chain:publication_unavailable")
    if local_head.status != "OBSERVED_LOCAL":
        return _block("chain:publication_unavailable")
    if (local_head.anchor_id != expected_anchor_id
            or local_head.revision < trusted_publication_revision):
        return _block("chain:publication_head_mismatch")
    return SyntheticChainDecision(
        "LOCAL_EVIDENCE_CONSISTENT_ONLY",
        ("chain:independent_off_host_not_proven",),
    )
