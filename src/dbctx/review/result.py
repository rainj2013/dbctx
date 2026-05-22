from __future__ import annotations

from dbctx.models import Finding, ReviewResult


def build_result(tables: list[str], matched_indexes: list[str], findings: list[Finding]) -> ReviewResult:
    if any(f.severity == "error" for f in findings):
        risk = "high"
    elif any(f.severity == "warning" for f in findings):
        risk = "medium"
    else:
        risk = "low"
    return ReviewResult(
        risk=risk,
        tables=sorted(set(tables)),
        matched_indexes=sorted(set(matched_indexes)),
        findings=findings,
    )

