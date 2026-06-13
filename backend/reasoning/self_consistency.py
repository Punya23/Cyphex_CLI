"""Self-consistency candidate selection driven by verification verdicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

PASS = "PASS"

_TIER_K = {
    "minimal": 1,
    "low": 1,
    "mid": 2,
    "high": 3,
    "ultra": 3,
    "cloud": 3,
}


@dataclass
class ConsistencyCandidate:
    candidate: dict[str, Any]
    verdict: str
    evidence: dict[str, Any] = field(default_factory=dict)
    diff_size: int = 0


@dataclass
class ConsistencyResult:
    status: str  # verified | unverified
    selected: Optional[ConsistencyCandidate]
    evaluated: list[ConsistencyCandidate]


GenerateKFn = Callable[[int], Awaitable[list[dict[str, Any]]]]
VerifyFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
DiffSizeFn = Callable[[dict[str, Any]], int]


def k_for_tier(tier: str) -> int:
    return _TIER_K.get((tier or "mid").lower(), 2)


async def patch_with_consistency(
    generate_candidates: GenerateKFn,
    verify_candidate: VerifyFn,
    tier: str = "mid",
    k: Optional[int] = None,
    diff_size_fn: Optional[DiffSizeFn] = None,
) -> ConsistencyResult:
    count = k if k is not None else k_for_tier(tier)
    candidates = await generate_candidates(max(1, count))

    evaluated: list[ConsistencyCandidate] = []
    for c in candidates[:max(1, count)]:
        verdict_obj = await verify_candidate(c)
        verdict = str(verdict_obj.get("verdict", "UNVERIFIABLE"))
        evidence = verdict_obj.get("evidence", {}) or {}
        diff_size = diff_size_fn(c) if diff_size_fn else len(str(c.get("fixed_code", "")))
        evaluated.append(ConsistencyCandidate(c, verdict, evidence, diff_size))

    passing = [e for e in evaluated if e.verdict == PASS]
    if passing:
        passing.sort(key=lambda x: x.diff_size)
        return ConsistencyResult(status="verified", selected=passing[0], evaluated=evaluated)

    selected = evaluated[0] if evaluated else None
    return ConsistencyResult(status="unverified", selected=selected, evaluated=evaluated)
