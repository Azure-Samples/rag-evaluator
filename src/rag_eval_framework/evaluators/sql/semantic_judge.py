"""SQL semantic judge — LLM-based evaluation of SQL correctness.

Uses an Azure OpenAI deployment to assess whether the generated SQL
semantically answers the user's question given the schema context.

Reuses the :class:`BaseLLMJudge` lifecycle from the existing judge
infrastructure.

**Required dataset fields**: ``question``, ``response``
"""

from __future__ import annotations

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import EvaluatorResult
from rag_eval_framework.evaluators.judges.base import BaseLLMJudge

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SQL_SEMANTIC_SYSTEM = """\
You are an expert SQL evaluation judge.  Your task is to assess whether a
generated SQL query correctly and completely answers the user's natural-
language question, given the database schema context.

Evaluate on these dimensions:
1. Does the SQL answer the user's question?
2. Are the correct tables used?
3. Are filters correct (date ranges, WHERE conditions)?
4. Is aggregation logic correct (SUM, COUNT, AVG, etc.)?
5. Is grouping correct (GROUP BY)?
6. Are joins appropriate?
7. Are output columns appropriate?
8. Is the business meaning preserved?
9. Are there any obvious SQL safety issues?

Return a JSON object with EXACTLY these keys:
  "score"  : float between 0.0 and 1.0
             1.0  = fully correct
             0.75 = mostly correct, minor issue
             0.5  = partially correct
             0.25 = weakly related
             0.0  = incorrect or unsafe
  "reason" : one-paragraph explanation of your evaluation
"""

SQL_SEMANTIC_USER = """\
User question: {question}

Database schema:
{schema_context}

Generated SQL:
{response}

Expected behavior:
{expected_behavior}

Reference SQL (if available):
{expected_sql}

Evaluate whether the generated SQL correctly answers the user question.
Return your evaluation as JSON with "score" and "reason" keys.
"""


class SqlSemanticJudge(BaseLLMJudge):
    """LLM judge that evaluates whether generated SQL answers the question."""

    @property
    def name(self) -> str:
        return "sql_semantic_judge"

    @property
    def description(self) -> str:
        return "LLM judge — assesses whether the SQL semantically answers the question."

    @property
    def required_fields(self) -> list[str]:
        return ["question", "response"]

    @property
    def system_prompt(self) -> str:
        return SQL_SEMANTIC_SYSTEM

    @property
    def user_prompt_template(self) -> str:
        return SQL_SEMANTIC_USER

    # -- override prompt formatting to use SQL-specific fields -------------

    def _format_user_prompt(self, record: EvaluationRecord) -> str:
        """Fill the user prompt template from the SQL-specific record fields."""
        return self.user_prompt_template.format(
            question=record.question,
            response=record.response,
            schema_context=record.schema_context or "(not provided)",
            expected_behavior=record.expected_behavior or "(not provided)",
            expected_sql=record.expected_sql or "(not provided)",
        )

    def evaluate(self, record: EvaluationRecord) -> EvaluatorResult:  # type: ignore[override]
        """Evaluate using direct 0.0–1.0 scoring (no 1-5 normalisation)."""
        from rag_eval_framework.evaluators.base import EvaluatorStatus

        if not self._configured:
            return EvaluatorResult(
                score=0.0,
                status=EvaluatorStatus.ERROR,
                reason=(
                    f"Judge '{self.name}' is not configured. "
                    "Provide azure + judge settings in the project config."
                ),
            )

        user_prompt = self._format_user_prompt(record)

        try:
            raw = self._call_llm(user_prompt)
            parsed = self._parse_response(raw)
        except Exception as exc:
            return EvaluatorResult(
                score=0.0,
                status=EvaluatorStatus.ERROR,
                reason=f"LLM call failed: {exc}",
            )

        raw_score = parsed.get("score", 0)
        reason = parsed.get("reason", "")

        # Clamp to 0.0–1.0 (judge returns float directly, not 1-5)
        score = max(0.0, min(1.0, float(raw_score)))
        score = round(score, 4)

        return EvaluatorResult(
            score=score,
            reason=str(reason),
            metadata={"raw_score": raw_score, "judge_model": self._deployment},
            raw_output=parsed,
        )
