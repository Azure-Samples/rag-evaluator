"""Azure AI Evaluation SDK-backed evaluators.

These evaluators wrap the ``azure-ai-evaluation`` SDK and require:

1. ``pip install 'rag-eval-framework[azure]'``
2. A valid Azure AI project connection string **or** an Azure OpenAI
   endpoint + deployment configured via the ``azure`` section of the
   project YAML config (see ``docs/configuration.md``).

When the SDK is not installed the evaluators are still registered in the
default registry but will produce a clear error at evaluation time.
"""

from rag_eval_framework.evaluators.azure.completeness import (
    ResponseCompletenessEvaluator,
)
from rag_eval_framework.evaluators.azure.groundedness import GroundednessEvaluator
from rag_eval_framework.evaluators.azure.relevance import RelevanceEvaluator
from rag_eval_framework.evaluators.azure.retrieval import RetrievalEvaluator

__all__ = [
    "GroundednessEvaluator",
    "RelevanceEvaluator",
    "ResponseCompletenessEvaluator",
    "RetrievalEvaluator",
]
