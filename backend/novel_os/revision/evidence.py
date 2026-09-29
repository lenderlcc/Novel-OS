"""Revision citation failures remain distinct from JSON/schema failures."""

from novel_os.quality.policy import check_evidence


class RevisionEvidenceError(ValueError):
    code = "REVISION_EVIDENCE_MISMATCH"


def check_revision_evidence(evidence, content):
    try:
        check_evidence(evidence, content)
    except ValueError:
        raise RevisionEvidenceError(
            "Revision evidence must quote exactly within its identified paragraph"
        ) from None
