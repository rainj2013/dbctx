from __future__ import annotations

from dbctx.models import Finding, ReviewResult, ReviewTableContext


def build_result(
    tables: list[str],
    matched_indexes: list[str],
    findings: list[Finding],
    context: list[ReviewTableContext] | None = None,
) -> ReviewResult:
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
        context=context or [],
        analysis_guidance=[
            "dbctx review is a deterministic pre-check. Treat findings and context as facts for the coding agent to reason over, not as a complete SQL optimization verdict.",
            "For large or production-critical tables, reason about predicate selectivity, index prefix order, tenant/soft-delete conventions, sorting, pagination, and whether test EXPLAIN can represent production data distribution.",
            "If a warning is kept, explain the project-specific reason and the expected data volume or index behavior.",
        ],
    )
