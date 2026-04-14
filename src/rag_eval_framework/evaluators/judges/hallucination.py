"""Hallucination judge — LLM-based unsupported-claim detection.

Checks whether the AI response contains claims not supported by the
retrieved context passages.

**Required dataset fields**: ``question``, ``response``, ``contexts``
"""

from __future__ import annotations

from rag_eval_framework.evaluators.judges.base import BaseLLMJudge
from rag_eval_framework.evaluators.judges.prompts import (
    HALLUCINATION_SYSTEM,
    HALLUCINATION_USER,
)


class HallucinationJudge(BaseLLMJudge):
    """LLM judge that detects hallucinated or unsupported claims."""

    @property
    def name(self) -> str:
        return "hallucination_judge"

    @property
    def description(self) -> str:
        return "LLM-based detection of hallucinated or unsupported claims."

    @property
    def required_fields(self) -> list[str]:
        return ["question", "response", "contexts"]

    @property
    def system_prompt(self) -> str:
        return HALLUCINATION_SYSTEM

    @property
    def user_prompt_template(self) -> str:
        return HALLUCINATION_USER
