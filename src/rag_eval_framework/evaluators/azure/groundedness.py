"""Groundedness evaluator — wraps Azure AI Evaluation SDK ``GroundednessEvaluator``.

Checks whether the response is grounded in the provided context passages.

**Required dataset fields**: ``question``, ``response``, ``contexts``
"""

from __future__ import annotations

from typing import Any

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.azure.adapter import AzureEvaluatorBase
from rag_eval_framework.evaluators.base import EvaluatorResult, EvaluatorStatus
from rag_eval_framework.utils.normalisation import normalise_1_5


class GroundednessEvaluator(AzureEvaluatorBase):
    """Determines whether the response is grounded in the retrieved contexts."""

    @property
    def name(self) -> str:
        return "groundedness"

    @property
    def description(self) -> str:
        return "Checks whether the response is grounded in the retrieved contexts."

    @property
    def required_fields(self) -> list[str]:
        return ["question", "response", "contexts"]

    @property
    def _sdk_class_name(self) -> str:
        return "azure.ai.evaluation.GroundednessEvaluator"

    def _build_sdk_input(self, record: EvaluationRecord) -> dict[str, Any]:
        return {
            "query": record.question,
            "response": record.response,
            "context": "\n\n".join(record.contexts),
        }

    def _normalise_sdk_output(self, sdk_result: dict[str, Any]) -> EvaluatorResult:
        raw_score = sdk_result.get("groundedness", sdk_result.get("gpt_groundedness"))
        if raw_score is None:
            return EvaluatorResult(
                score=0.0,
                status=EvaluatorStatus.ERROR,
                reason="SDK did not return a groundedness score.",
                raw_output=sdk_result,
            )

        # Azure SDK typically returns 1-5; normalise to 0.0-1.0
        score = normalise_1_5(float(raw_score))
        reason = sdk_result.get(
            "groundedness_reason",
            sdk_result.get("gpt_groundedness_reason", ""),
        )
        return EvaluatorResult(
            score=score,
            reason=str(reason),
            metadata={"raw_score": raw_score},
            raw_output=sdk_result,
        )
