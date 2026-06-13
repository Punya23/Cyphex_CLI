"""Grounded reflexion loop: draft -> verify -> evidence feedback -> retry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

PASS = "PASS"

_TIER_ROUNDS = {
    "minimal": 1,
    "low": 1,
    "mid": 2,
    "high": 3,
    "ultra": 3,
    "cloud": 3,
}


@dataclass
class ReflexionAttempt:
    round_no: int
    candidate: dict[str, Any]
    verdict: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflexionResult:
    status: str  # verified | unverified
    attempts: list[ReflexionAttempt]
    best_candidate: Optional[dict[str, Any]] = None


GenerateFn = Callable[[str, int], Awaitable[dict[str, Any]]]
VerifyFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def rounds_for_tier(tier: str) -> int:
    return _TIER_ROUNDS.get((tier or "mid").lower(), 2)


def build_objective_feedback(evidence: dict[str, Any]) -> str:
    if not evidence:
        return "Verification failed without detailed evidence. Preserve behavior and reduce risk using a different strategy."

    lines = ["Previous candidate failed objective verification. Address these concrete findings:"]
    if evidence.get("exploit_still_works"):
        lines.append("- Exploit still works after patch; close the vulnerable sink completely.")
    if evidence.get("endpoint_dead"):
        lines.append("- Endpoint became unavailable; preserve endpoint behavior and response contract.")
    if evidence.get("suppression_added"):
        lines.append("- Patch added suppression markers; remove suppression and fix root cause directly.")
    if evidence.get("finding_still_present"):
        lines.append("- Static finding still present near same location; strengthen the fix in the sink.")
    if evidence.get("changed_lines", 0) > 40:
        lines.append("- Diff is too large; produce a smaller, targeted fix.")
    return "\n".join(lines)


async def patch_with_reflexion(
    generate_candidate: GenerateFn,
    verify_candidate: VerifyFn,
    tier: str = "mid",
    max_rounds: Optional[int] = None,
) -> ReflexionResult:
    rounds = max_rounds if max_rounds is not None else rounds_for_tier(tier)
    attempts: list[ReflexionAttempt] = []
    feedback = ""
    best = None

    for i in range(1, max(1, rounds) + 1):
        candidate = await generate_candidate(feedback, i)
        verdict_obj = await verify_candidate(candidate)
        verdict = str(verdict_obj.get("verdict", "UNVERIFIABLE"))
        evidence = verdict_obj.get("evidence", {}) or {}
        attempts.append(ReflexionAttempt(i, candidate, verdict, evidence))
        best = candidate

        if verdict == PASS:
            return ReflexionResult(status="verified", attempts=attempts, best_candidate=candidate)

        feedback = build_objective_feedback(evidence)

    return ReflexionResult(status="unverified", attempts=attempts, best_candidate=best)
