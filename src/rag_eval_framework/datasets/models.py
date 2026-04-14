"""Pydantic models for evaluation dataset records."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class EvaluationRecord(BaseModel):
    """A single evaluation dataset record.

    Core fields (``id``, ``question``, ``response``) are always required.
    Other fields are optional and consumed only by evaluators that declare
    them in their ``required_fields`` property.

    Schema aligns with the format described in SPEC.md FR-2.
    """

    id: str = Field(..., description="Unique identifier for this test case.")
    question: str = Field(..., description="The user question / query.")
    response: str = Field(..., description="The RAG system's generated response.")
    contexts: list[str] = Field(
        default_factory=list,
        description="Retrieved context passages used to generate the response.",
    )
    ground_truth_answer: str = Field(
        default="",
        description="Expected correct answer for comparison evaluators.",
    )

    # --- Phase 2 additions ------------------------------------------------

    retrieved_documents: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Structured retrieved document objects, each with at least a "
            "'content' key.  Used by document-level evaluators."
        ),
    )
    ground_truth_documents: list[str] = Field(
        default_factory=list,
        description=("Expected document identifiers or passages for retrieval quality evaluation."),
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata for filtering or grouping.",
    )

    # --- Validators -------------------------------------------------------

    @field_validator("response")
    @classmethod
    def response_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Response must not be empty.")
        return v

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Question must not be empty.")
        return v

    # --- Convenience helpers ----------------------------------------------

    def has_contexts(self) -> bool:
        """Return *True* if at least one non-empty context is present."""
        return any(c.strip() for c in self.contexts)

    def has_ground_truth(self) -> bool:
        """Return *True* if a ground-truth answer is present."""
        return bool(self.ground_truth_answer.strip())
