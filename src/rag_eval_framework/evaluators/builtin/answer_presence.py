"""Answer presence evaluator — checks whether the response is non-trivial.

This is a **Phase 1 scaffold evaluator**.  It performs a simple deterministic
check and will be supplemented (or replaced) by Azure AI Evaluation SDK
evaluators in Phase 2.
"""

from __future__ import annotations

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import BaseEvaluator, EvaluatorResult

# Minimum token count to consider a response substantive
_MIN_WORD_COUNT = 2


class AnswerPresenceEvaluator(BaseEvaluator):
    """Deterministic check: does the response contain a substantive answer?

    Scoring
    -------
    * **1.0** — response has at least ``_MIN_WORD_COUNT`` words.
    * **0.0** — response is missing or too short.

    This evaluator is intentionally simple.  In Phase 2 it can be extended
    to use an LLM judge for deeper answer-quality assessment.
    """

    @property
    def name(self) -> str:
        return "answer_presence"

    @property
    def description(self) -> str:
        return "Checks whether the response contains a substantive answer."

    def evaluate(self, record: EvaluationRecord) -> EvaluatorResult:
        words = record.response.strip().split()
        if len(words) >= _MIN_WORD_COUNT:
            return EvaluatorResult(
                score=1.0,
                reason=f"Response contains {len(words)} word(s), meets minimum.",
            )
        return EvaluatorResult(
            score=0.0,
            reason=(
                f"Response contains only {len(words)} word(s), below minimum of {_MIN_WORD_COUNT}."
            ),
        )
