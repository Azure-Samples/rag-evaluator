"""Dataset loading and validation for RAG Evaluation Framework."""

from rag_eval_framework.datasets.loader import DatasetLoadError, load_dataset
from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.datasets.validator import validate_dataset

__all__ = ["DatasetLoadError", "EvaluationRecord", "load_dataset", "validate_dataset"]
