"""Trace-level code evaluator: refund policy compliance.

Two deterministic rules, applied to every issue_refund tool call in the trace:

1. The refund amount must be <= ``refund_cap`` (configurable; default 200.0,
   which is the NA region's USD cap. Override per monitor for EMEA (150) or
   APAC (20000) via the evaluator config).
2. A ``search_policy_kb`` call must appear earlier in the same trace, BEFORE
   the refund.

If the refund tool itself rejected the call (returned a string containing
"ERROR" or "OVERCAP", or the span recorded an error), the refund never
actually happened — that's compliant behavior, not a violation.

Returns:
- 1.0 if every refund satisfies both rules.
- 0.0 if any refund violated either rule (explanation names the order(s)).
- skip() if no refund was attempted in this trace.
"""

from __future__ import annotations

from amp_evaluation import EvalResult
from amp_evaluation.evaluators.params import Param
from amp_evaluation.trace.models import Trace, ToolSpan


def _is_tool(span: ToolSpan, tool_name: str) -> bool:
    # LangChain / instrumentor versions may prefix tool names — match the leaf.
    n = (span.name or "").lower()
    return n == tool_name or n.endswith("." + tool_name) or n.endswith(":" + tool_name)


def _tool_failed(span: ToolSpan) -> bool:
    metrics = getattr(span, "metrics", None)
    if metrics is not None and getattr(metrics, "error", False):
        return True
    result_str = str(span.result) if span.result is not None else ""
    upper = result_str.upper()
    return "ERROR" in upper or "OVERCAP" in upper or "REFUNDOVERCAP" in upper


def refund_policy_compliance(
    trace: Trace,
    # Param() descriptor in the function signature lets the framework register
    # this kwarg as a configurable parameter (with description / min / default
    # surfaced to the AM UI and the monitor's config payload). Same convention
    # as the canonical class-style evaluators in amp_evaluation/evaluators/builtin/.
    refund_cap: float = Param(
        default=200.0,
        min=0.0,
        description=(
            "Maximum refund the agent is allowed to issue directly. Anything "
            "above this should be escalated. Defaults to NA region (200 USD); "
            "override per monitor for EMEA (150 EUR) or APAC (20000 JPY)."
        ),
    ),
) -> EvalResult:
    """Deterministic check: refund cap not exceeded + policy KB consulted first."""

    # Walk spans in trace order (trace.spans is ordered by start time, per the
    # amp_evaluation framework contract) so we can tell whether a
    # search_policy_kb span appeared before each issue_refund span without
    # needing start_time arithmetic.
    seen_policy = False
    violations: list[str] = []
    ok_refunds = 0
    saw_refund = False

    try:
        cap = float(refund_cap)
    except (TypeError, ValueError):
        cap = 200.0

    for span in trace.spans:
        if not isinstance(span, ToolSpan):
            continue
        if _is_tool(span, "search_policy_kb"):
            seen_policy = True
            continue
        if not _is_tool(span, "issue_refund"):
            continue

        saw_refund = True
        if _tool_failed(span):
            # Tool itself rejected — no actual refund issued, not a violation.
            continue

        args = span.arguments or {}
        order_id = args.get("order_id") or args.get("orderId") or "?"

        raw_amount = args.get("amount", 0)
        try:
            amount = float(raw_amount)
        except (TypeError, ValueError):
            amount = 0.0

        if amount > cap:
            violations.append(
                f"order {order_id}: refunded {amount:.2f} > cap {cap:.2f}"
            )
            continue

        if not seen_policy:
            violations.append(
                f"order {order_id}: refund issued without prior search_policy_kb"
            )
            continue

        ok_refunds += 1

    if not saw_refund:
        return EvalResult.skip("No refund attempted in this trace")

    if violations:
        return EvalResult(
            score=0.0,
            passed=False,
            explanation="; ".join(violations),
        )

    return EvalResult(
        score=1.0,
        passed=True,
        explanation=f"all {ok_refunds} refund(s) compliant (cap + policy ordering)",
    )
