"""Accuracy judge — LLM-based answer accuracy evaluation.

Compares the AI response to the ground-truth answer using an Azure OpenAI
deployment and produces a 0.0–1.0 score.

**Required dataset fields**: ``question``, ``response``, ``ground_truth_answer``
"""

from __future__ import annotations

from rag_eval_framework.evaluators.judges.base import BaseLLMJudge
from rag_eval_framework.evaluators.judges.prompts import (
    ACCURACY_SYSTEM,
    ACCURACY_USER,
)


class AccuracyJudge(BaseLLMJudge):
    """LLM judge that evaluates answer accuracy against ground truth."""

    @property
    def name(self) -> str:
        return "accuracy_judge"

    @property
    def description(self) -> str:
        return "LLM-based assessment of answer accuracy against ground truth."

    @property
    def required_fields(self) -> list[str]:
        return ["question", "response", "ground_truth_answer"]

    @property
    def system_prompt(self) -> str:
        return ACCURACY_SYSTEM

    @property
    def user_prompt_template(self) -> str:
        return ACCURACY_USER
