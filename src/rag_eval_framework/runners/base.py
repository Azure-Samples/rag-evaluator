"""Base runner interface and shared result models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from rag_eval_framework.config.models import ProjectConfig
from rag_eval_framework.evaluators.base import EvaluatorResult

# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class RecordResult(BaseModel):
    """Evaluation results for a single dataset record."""

    record_id: str
    evaluator_results: dict[str, EvaluatorResult]
    passed: bool = Field(
        default=True,
        description="True if every evaluator score meets its threshold for this record.",
    )


class ThresholdBreach(BaseModel):
    """Details about a threshold that was not met."""

    evaluator: str
    threshold: float
    actual: float
    delta: float = Field(
        description="How far below the threshold the actual score fell.",
    )


class ThresholdResult(BaseModel):
    """Per-evaluator threshold check outcome (used in reports)."""

    evaluator: str
    threshold: float
    actual: float
    passed: bool


class EvaluationRunResult(BaseModel):
    """Aggregated result of a full evaluation run."""

    project_name: str
    timestamp: str
    dataset_path: str
    total_records: int
    evaluators_used: list[str]
    record_results: list[RecordResult]
    aggregate_scores: dict[str, float]
    threshold_breaches: list[ThresholdBreach] = Field(default_factory=list)
    threshold_results: list[ThresholdResult] = Field(default_factory=list)
    passed: bool
    run_metadata: dict[str, Any] = Field(default_factory=dict)
    skipped_evaluators: dict[str, str] = Field(
        default_factory=dict,
        description="Evaluators skipped globally and the reason (e.g. SDK missing).",
    )
    config_reference: str = Field(
        default="",
        description="Path to the project configuration file that produced this run.",
    )
    runner_type: str = Field(
        default="local",
        description="Execution mode: 'local' or 'cloud'.",
    )


# ---------------------------------------------------------------------------
# Abstract runner
# ---------------------------------------------------------------------------


class BaseRunner(ABC):
    """Abstract runner interface.

    Both the local runner and the future Azure AI Foundry cloud runner
    implement this interface, allowing callers to swap execution modes
    without changing orchestration code.
    """

    @abstractmethod
    def run(self, config: ProjectConfig) -> EvaluationRunResult:
        """Execute a full evaluation run and return aggregated results."""
        ...
