from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RefinementIterationState:
    iteration: int
    max_iterations: int
    is_valid: bool
    has_valid_candidate: bool
    stagnation_count: int
    plateau_patience: int


@dataclass(frozen=True)
class RefinementStopDecision:
    should_stop: bool = False
    reason: str = "none"


class RefinementStopPolicy(Protocol):
    def should_stop(self, state: RefinementIterationState) -> RefinementStopDecision: ...


class ExitOnValidStopPolicy:
    def __init__(self, enabled: bool):
        self._enabled = enabled

    def should_stop(self, state: RefinementIterationState) -> RefinementStopDecision:
        if self._enabled and state.is_valid:
            return RefinementStopDecision(should_stop=True, reason="valid")
        return RefinementStopDecision()


class PlateauStopPolicy:
    def __init__(self, enabled: bool):
        self._enabled = enabled

    def should_stop(self, state: RefinementIterationState) -> RefinementStopDecision:
        if not self._enabled:
            return RefinementStopDecision()
        if state.has_valid_candidate:
            return RefinementStopDecision()
        if state.iteration >= state.max_iterations:
            return RefinementStopDecision()
        if state.stagnation_count < state.plateau_patience:
            return RefinementStopDecision()
        return RefinementStopDecision(should_stop=True, reason="plateau")


class CompositeRefinementStopPolicy:
    def __init__(self, policies: list[RefinementStopPolicy]):
        self._policies = list(policies)

    def should_stop(self, state: RefinementIterationState) -> RefinementStopDecision:
        for policy in self._policies:
            decision = policy.should_stop(state)
            if decision.should_stop:
                return decision
        return RefinementStopDecision()