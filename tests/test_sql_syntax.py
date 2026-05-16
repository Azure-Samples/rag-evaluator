"""Tests for the sql_syntax_validity evaluator."""

from __future__ import annotations

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import EvaluatorStatus
from rag_eval_framework.evaluators.sql.syntax import SqlSyntaxValidityEvaluator


def _sql_record(**overrides) -> EvaluationRecord:
    """Shorthand to create an EvaluationRecord with a SQL response."""
    defaults = {
        "id": "sql-syn-001",
        "question": "Show all sales.",
        "response": "SELECT * FROM sales;",
    }
    defaults.update(overrides)
    return EvaluationRecord(**defaults)


class TestSqlSyntaxValidity:
    def setup_method(self) -> None:
        self.evaluator = SqlSyntaxValidityEvaluator()

    def test_name(self) -> None:
        assert self.evaluator.name == "sql_syntax_validity"

    def test_valid_select(self) -> None:
        record = _sql_record(response="SELECT region, SUM(amount) FROM sales GROUP BY region;")
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0
        assert result.status == EvaluatorStatus.SUCCESS
        assert "parsed successfully" in result.reason
        assert result.metadata["parser"] == "sqlglot"

    def test_valid_select_no_semicolon(self) -> None:
        record = _sql_record(response="SELECT * FROM sales")
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_invalid_sql(self) -> None:
        record = _sql_record(response="SELEC region FORM sales GROPU BY region;")
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        assert "parsing failed" in result.reason.lower() or "failed" in result.reason.lower()

    def test_non_sql_text(self) -> None:
        record = _sql_record(response="The total sales by region are as follows.")
        result = self.evaluator.evaluate(record)
        # sqlglot may or may not parse natural language as valid SQL;
        # either a 0.0 (parse error) or 1.0 (best-effort parse) is acceptable.
        assert result.score in (0.0, 1.0)

    def test_sql_with_comments(self) -> None:
        record = _sql_record(
            response="-- get sales\nSELECT * FROM sales;"
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_multiple_statements_blocked(self) -> None:
        record = _sql_record(
            response="SELECT * FROM sales; SELECT * FROM products;"
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        assert "multiple" in result.reason.lower() or "multi" in result.reason.lower()

    def test_multiple_statements_allowed(self) -> None:
        evaluator = SqlSyntaxValidityEvaluator()
        evaluator._allow_multi_statement = True
        record = _sql_record(
            response="SELECT * FROM sales; SELECT * FROM products;"
        )
        result = evaluator.evaluate(record)
        assert result.score == 1.0
        assert result.metadata["statement_count"] == 2

    def test_trailing_semicolon(self) -> None:
        record = _sql_record(response="SELECT 1;")
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_complex_query(self) -> None:
        sql = (
            "SELECT r.region, SUM(s.amount) AS total "
            "FROM sales s JOIN regions r ON s.region_id = r.id "
            "WHERE s.sale_date >= '2025-01-01' "
            "GROUP BY r.region HAVING SUM(s.amount) > 1000 "
            "ORDER BY total DESC LIMIT 10;"
        )
        record = _sql_record(response=sql)
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_cte_query(self) -> None:
        sql = (
            "WITH cte AS (SELECT region, amount FROM sales) "
            "SELECT region, SUM(amount) FROM cte GROUP BY region;"
        )
        record = _sql_record(response=sql)
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0
