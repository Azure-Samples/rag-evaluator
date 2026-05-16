"""Tests for the sql_semantic_judge evaluator."""

from __future__ import annotations

import json
from unittest.mock import patch

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import EvaluatorStatus
from rag_eval_framework.evaluators.sql.semantic_judge import SqlSemanticJudge


def _sql_record(**overrides) -> EvaluationRecord:
    defaults = {
        "id": "sql-judge-001",
        "question": "Show total sales by region for Q1 2025.",
        "response": (
            "SELECT region, SUM(amount) AS total_sales FROM sales "
            "WHERE sale_date >= '2025-01-01' AND sale_date < '2025-04-01' "
            "GROUP BY region;"
        ),
        "schema_context": "Table sales(region TEXT, amount DECIMAL, sale_date DATE)",
        "expected_behavior": "Aggregate total sales by region for Q1 2025.",
        "expected_sql": (
            "SELECT region, SUM(amount) AS total_sales FROM sales "
            "WHERE sale_date >= '2025-01-01' AND sale_date < '2025-04-01' "
            "GROUP BY region;"
        ),
    }
    defaults.update(overrides)
    return EvaluationRecord(**defaults)


class TestSqlSemanticJudge:
    def test_name(self) -> None:
        judge = SqlSemanticJudge()
        assert judge.name == "sql_semantic_judge"

    def test_required_fields(self) -> None:
        judge = SqlSemanticJudge()
        assert "question" in judge.required_fields
        assert "response" in judge.required_fields

    def test_not_configured_returns_error(self) -> None:
        judge = SqlSemanticJudge()
        record = _sql_record()
        result = judge.evaluate(record)
        assert result.score == 0.0
        assert result.status == EvaluatorStatus.ERROR
        assert "not configured" in result.reason

    def test_prompt_construction(self) -> None:
        judge = SqlSemanticJudge()
        record = _sql_record()
        prompt = judge._format_user_prompt(record)
        assert "Show total sales" in prompt
        assert "SELECT region" in prompt
        assert "sales(region TEXT" in prompt
        assert "Aggregate total sales" in prompt

    def test_prompt_handles_missing_optional_fields(self) -> None:
        judge = SqlSemanticJudge()
        record = _sql_record(
            schema_context="",
            expected_behavior="",
            expected_sql="",
        )
        prompt = judge._format_user_prompt(record)
        assert "(not provided)" in prompt

    def test_valid_judge_response(self) -> None:
        judge = SqlSemanticJudge()
        judge._configured = True
        judge._deployment = "gpt-4.1"

        mock_response = json.dumps({"score": 0.85, "reason": "SQL is mostly correct."})

        with patch.object(judge, "_call_llm", return_value=mock_response):
            record = _sql_record()
            result = judge.evaluate(record)

        assert result.score == 0.85
        assert result.reason == "SQL is mostly correct."
        assert result.metadata["judge_model"] == "gpt-4.1"
        assert result.raw_output["score"] == 0.85

    def test_perfect_score(self) -> None:
        judge = SqlSemanticJudge()
        judge._configured = True
        judge._deployment = "gpt-4.1"

        mock_response = json.dumps({"score": 1.0, "reason": "Fully correct."})

        with patch.object(judge, "_call_llm", return_value=mock_response):
            result = judge.evaluate(_sql_record())

        assert result.score == 1.0

    def test_zero_score(self) -> None:
        judge = SqlSemanticJudge()
        judge._configured = True
        judge._deployment = "gpt-4.1"

        mock_response = json.dumps({"score": 0.0, "reason": "Completely wrong."})

        with patch.object(judge, "_call_llm", return_value=mock_response):
            result = judge.evaluate(_sql_record())

        assert result.score == 0.0

    def test_malformed_json_response(self) -> None:
        judge = SqlSemanticJudge()
        judge._configured = True
        judge._deployment = "gpt-4.1"

        with patch.object(judge, "_call_llm", return_value="NOT JSON"):
            result = judge.evaluate(_sql_record())

        assert result.score == 0.0
        assert "parse" in result.reason.lower() or result.raw_output is not None

    def test_llm_call_failure(self) -> None:
        judge = SqlSemanticJudge()
        judge._configured = True
        judge._deployment = "gpt-4.1"

        with patch.object(judge, "_call_llm", side_effect=RuntimeError("API error")):
            result = judge.evaluate(_sql_record())

        assert result.score == 0.0
        assert result.status == EvaluatorStatus.ERROR
        assert "API error" in result.reason

    def test_score_clamped_above_1(self) -> None:
        judge = SqlSemanticJudge()
        judge._configured = True
        judge._deployment = "gpt-4.1"

        mock_response = json.dumps({"score": 1.5, "reason": "Over-scored."})

        with patch.object(judge, "_call_llm", return_value=mock_response):
            result = judge.evaluate(_sql_record())

        assert result.score == 1.0

    def test_score_clamped_below_0(self) -> None:
        judge = SqlSemanticJudge()
        judge._configured = True
        judge._deployment = "gpt-4.1"

        mock_response = json.dumps({"score": -0.5, "reason": "Negative."})

        with patch.object(judge, "_call_llm", return_value=mock_response):
            result = judge.evaluate(_sql_record())

        assert result.score == 0.0
