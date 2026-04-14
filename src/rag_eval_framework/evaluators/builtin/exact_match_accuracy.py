"""Exact-match accuracy evaluator — compares response to ground truth.

This is a **Phase 1 scaffold evaluator**.  It performs a simple deterministic
comparison.  In Phase 2 this role will be filled by LLM-as-a-judge accuracy
evaluators that handle paraphrases, partial matches, and nuance.
"""

from __future__ import annotations

import re

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import BaseEvaluator, EvaluatorResult


def _normalize(text: str) -> str:
    """Lower-case, strip whitespace, collapse runs of whitespace, remove punctuation."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


class ExactMatchAccuracyEvaluator(BaseEvaluator):
    """Case-insensitive normalised comparison of response to ground truth.

    Scoring
    -------
    * **1.0** — normalised response *contains* the normalised ground truth answer.
    * **0.5** — ground truth answer is empty (cannot determine accuracy).
    * **0.0** — normalised ground truth answer is not found in the response.

    This evaluator deliberately uses substring containment (rather than
    strict equality) so that longer responses that include the expected
    answer still score well.  More sophisticated semantic matching should
    be added via LLM-as-a-judge evaluators in Phase 2.
    """

    @property
    def name(self) -> str:
        return "exact_match_accuracy"

    @property
    def description(self) -> str:
        return (
            "Checks whether the normalised ground-truth answer appears in the normalised response."
        )

    def evaluate(self, record: EvaluationRecord) -> EvaluatorResult:
        if not record.ground_truth_answer.strip():
            return EvaluatorResult(
                score=0.5,
                reason="No ground truth answer provided; accuracy indeterminate.",
            )

        norm_response = _normalize(record.response)
        norm_truth = _normalize(record.ground_truth_answer)

        if norm_truth in norm_response:
            return EvaluatorResult(
                score=1.0,
                reason="Ground truth answer found in response.",
            )

        return EvaluatorResult(
            score=0.0,
            reason="Ground truth answer NOT found in response.",
        )
