"""Base evaluator interface and result model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from rag_eval_framework.datasets.models import EvaluationRecord

# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class EvaluatorStatus(str, Enum):
    """Status of an individual evaluator result."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


class EvaluatorResult(BaseModel):
    """Result produced by a single evaluator for a single record.

    Aligns with the judge output schema in SPEC.md FR-5.
    """

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numeric score between 0.0 (worst) and 1.0 (best).",
    )
    reason: str = Field(
        default="",
        description="Human-readable explanation of the score.",
    )
    status: EvaluatorStatus = Field(
        default=EvaluatorStatus.SUCCESS,
        description="Whether the evaluator ran successfully, was skipped, or errored.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Evaluator-specific metadata (e.g. model used, latency).",
    )
    raw_output: dict[str, Any] | None = Field(
        default=None,
        description="Raw structured output from the underlying SDK or LLM call.",
    )


# ---------------------------------------------------------------------------
# Base evaluator ABC
# ---------------------------------------------------------------------------


class BaseEvaluator(ABC):
    """Abstract base class for all evaluators.

    Every evaluator — built-in, Azure-backed, or custom — must implement
    this interface.  The evaluator registry resolves evaluator names to
    concrete subclasses at run-time.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Machine-readable evaluator name (used in configs and reports)."""
        ...

    @property
    def description(self) -> str:
        """Optional human-readable description."""
        return ""

    @property
    def required_fields(self) -> list[str]:
        """Dataset fields this evaluator requires.

        The runner checks these before calling ``evaluate()``.  If a field
        is missing or empty the record is scored ``0.0`` with status
        ``SKIPPED`` and a clear reason.

        Override in subclasses to declare additional dependencies.  The
        default only requires ``question`` and ``response``.
        """
        return ["question", "response"]

    def setup(self, config: Any) -> None:  # noqa: B027
        """Optional lifecycle hook called by the runner after instantiation.

        Override this to extract connection strings, model names, or other
        settings from a ``ProjectConfig`` (or any config object).  The
        default implementation is a no-op.
        """

    @abstractmethod
    def evaluate(self, record: EvaluationRecord) -> EvaluatorResult:
        """Evaluate a single dataset record and return a scored result."""
        ...
