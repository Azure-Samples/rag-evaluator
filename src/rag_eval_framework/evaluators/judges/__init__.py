"""LLM-as-a-judge evaluators.

This package provides a reusable base class (:class:`BaseLLMJudge`) and
four concrete judge evaluators:

* :class:`AccuracyJudge` — answer accuracy
* :class:`HallucinationJudge` — unsupported-claim detection
* :class:`CitationJudge` — citation / evidence adherence
* :class:`PolicyComplianceJudge` — custom policy compliance

Judges require an Azure OpenAI deployment.  Configure via the ``judge``
and ``azure`` sections of the project YAML config.
"""

from rag_eval_framework.evaluators.judges.accuracy import AccuracyJudge
from rag_eval_framework.evaluators.judges.citation import CitationJudge
from rag_eval_framework.evaluators.judges.hallucination import HallucinationJudge
from rag_eval_framework.evaluators.judges.policy_compliance import (
    PolicyComplianceJudge,
)

__all__ = [
    "AccuracyJudge",
    "CitationJudge",
    "HallucinationJudge",
    "PolicyComplianceJudge",
]
