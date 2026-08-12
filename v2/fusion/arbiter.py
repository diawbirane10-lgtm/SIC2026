from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class SourceOpinion:
    name: str
    probabilities: Mapping[str, float]
    quality: float = 1.0
    integrity: float = 1.0


@dataclass(frozen=True)
class FusionDecision:
    label: str
    confidence: float
    margin: float
    coverage_ok: bool
    abstained: bool
    reason: str
    active_sources: Sequence[str]
    source_votes: Mapping[str, str]
    consensus_weight_ratio: float
    disagreement_index: float
    fused_probabilities: Mapping[str, float]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _clip01(value: float) -> float:
    return float(np.clip(float(value), 0.0, 1.0))


def _normalize(probabilities: Mapping[str, float], classes: Sequence[str]) -> np.ndarray:
    arr = np.asarray([max(float(probabilities.get(c, 0.0)), 0.0) for c in classes], dtype=float)
    total = float(arr.sum())
    if total <= 0:
        return np.full(len(classes), 1.0 / len(classes), dtype=float)
    return arr / total


def _opinion_weight(opinion: SourceOpinion, probs: np.ndarray) -> float:
    # Confidence enters sub-linearly so that one over-confident source cannot dominate
    # two independent sources of reasonable quality.
    if len(probs) <= 1:
        margin = 1.0
    else:
        ordered = np.sort(probs)
        margin = float(ordered[-1] - ordered[-2])
    certainty = 0.35 + 0.65 * np.sqrt(max(margin, 0.0))
    return _clip01(opinion.quality) * _clip01(opinion.integrity) * certainty


def fuse_opinions(
    opinions: Iterable[SourceOpinion],
    classes: Sequence[str],
    *,
    min_active_sources: int = 2,
    min_source_quality: float = 0.35,
    min_source_integrity: float = 0.35,
    min_total_weight: float = 0.85,
    min_fused_confidence: float = 0.56,
    min_fused_margin: float = 0.12,
    min_consensus_weight_ratio: float = 0.60,
    hard_conflict_confidence: float = 0.82,
) -> FusionDecision:
    classes = tuple(classes)
    if len(classes) < 2:
        raise ValueError("At least two classes are required")

    prepared: List[tuple[SourceOpinion, np.ndarray, float]] = []
    source_votes: Dict[str, str] = {}

    for opinion in opinions:
        probs = _normalize(opinion.probabilities, classes)
        vote = classes[int(np.argmax(probs))]
        source_votes[opinion.name] = vote
        if opinion.quality < min_source_quality or opinion.integrity < min_source_integrity:
            continue
        weight = _opinion_weight(opinion, probs)
        if weight <= 0:
            continue
        prepared.append((opinion, probs, weight))

    def abstain(reason: str, *, disagreement: float = 1.0) -> FusionDecision:
        uniform = {c: 1.0 / len(classes) for c in classes}
        return FusionDecision(
            label="unknown",
            confidence=0.0,
            margin=0.0,
            coverage_ok=False,
            abstained=True,
            reason=reason,
            active_sources=tuple(p[0].name for p in prepared),
            source_votes=source_votes,
            consensus_weight_ratio=0.0,
            disagreement_index=float(disagreement),
            fused_probabilities=uniform,
        )

    if len(prepared) < min_active_sources:
        return abstain("insufficient_independent_sources")

    total_weight = float(sum(weight for _, _, weight in prepared))
    if total_weight < min_total_weight:
        return abstain("insufficient_effective_reliability")

    weighted = np.zeros(len(classes), dtype=float)
    for _, probs, weight in prepared:
        weighted += weight * probs
    fused = weighted / max(total_weight, 1e-12)

    order = np.argsort(fused)[::-1]
    top_idx, second_idx = int(order[0]), int(order[1])
    top_label = classes[top_idx]
    confidence = float(fused[top_idx])
    margin = float(fused[top_idx] - fused[second_idx])

    vote_weight = sum(weight for opinion, probs, weight in prepared if classes[int(np.argmax(probs))] == top_label)
    consensus_ratio = float(vote_weight / max(total_weight, 1e-12))

    # Pairwise vote disagreement, weighted only by source count. This is intentionally
    # interpretable for the operator rather than a hidden learned quantity.
    votes = [classes[int(np.argmax(probs))] for _, probs, _ in prepared]
    pairs = 0
    disagreements = 0
    for i in range(len(votes)):
        for j in range(i + 1, len(votes)):
            pairs += 1
            disagreements += int(votes[i] != votes[j])
    disagreement_index = float(disagreements / max(pairs, 1))

    # Two high-confidence sources pointing to different diagnoses is an explicit veto
    # unless the remaining evidence establishes a sufficiently strong weighted consensus.
    hard_votes: Dict[str, int] = {}
    for _, probs, _ in prepared:
        local_top = int(np.argmax(probs))
        if float(probs[local_top]) >= hard_conflict_confidence:
            hard_votes[classes[local_top]] = hard_votes.get(classes[local_top], 0) + 1
    hard_conflict = len(hard_votes) >= 2

    fused_dict = {c: float(fused[i]) for i, c in enumerate(classes)}

    if hard_conflict and consensus_ratio < 0.67:
        return FusionDecision(
            label="unknown",
            confidence=confidence,
            margin=margin,
            coverage_ok=False,
            abstained=True,
            reason="high_confidence_cross_modal_conflict",
            active_sources=tuple(p[0].name for p in prepared),
            source_votes=source_votes,
            consensus_weight_ratio=consensus_ratio,
            disagreement_index=disagreement_index,
            fused_probabilities=fused_dict,
        )

    if confidence < min_fused_confidence:
        reason = "low_fused_confidence"
    elif margin < min_fused_margin:
        reason = "low_decision_margin"
    elif consensus_ratio < min_consensus_weight_ratio:
        reason = "insufficient_cross_modal_consensus"
    else:
        reason = "consensus_sufficient"

    abstained = reason != "consensus_sufficient"
    return FusionDecision(
        label="unknown" if abstained else top_label,
        confidence=confidence,
        margin=margin,
        coverage_ok=not abstained,
        abstained=abstained,
        reason=reason,
        active_sources=tuple(p[0].name for p in prepared),
        source_votes=source_votes,
        consensus_weight_ratio=consensus_ratio,
        disagreement_index=disagreement_index,
        fused_probabilities=fused_dict,
    )
