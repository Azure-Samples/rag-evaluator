"""Tests for the sql_schema_validity evaluator."""

from __future__ import annotations

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import EvaluatorStatus
from rag_eval_framework.evaluators.sql.schema import SqlSchemaValidityEvaluator


def _sql_record(**overrides) -> EvaluationRecord:
    defaults = {
        "id": "sql-schema-001",
        "question": "Show total sales.",
        "response": "SELECT region, SUM(amount) FROM sales GROUP BY region;",
        "allowed_tables": ["sales"],
        "allowed_columns": {"sales": ["region", "amount", "sale_date"]},
    }
    defaults.update(overrides)
    return EvaluationRecord(**defaults)


class TestSqlSchemaValidity:
    def setup_method(self) -> None:
        self.evaluator = SqlSchemaValidityEvaluator()

    def test_name(self) -> None:
        assert self.evaluator.name == "sql_schema_validity"

    def test_valid_table_and_columns(self) -> None:
        record = _sql_record()
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0
        assert result.metadata["validation_level"] == "column"

    def test_hallucinated_table(self) -> None:
        record = _sql_record(
            response="SELECT * FROM customer_orders;",
            allowed_tables=["sales"],
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        assert "customer_orders" in result.reason

    def test_hallucinated_column(self) -> None:
        record = _sql_record(
            response="SELECT region, revenue FROM sales;",
            allowed_tables=["sales"],
            allowed_columns={"sales": ["region", "amount", "sale_date"]},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        assert "revenue" in result.reason.lower()

    def test_valid_table_no_column_metadata(self) -> None:
        """When allowed_columns is empty, table-only validation returns 0.5."""
        record = _sql_record(
            allowed_tables=["sales"],
            allowed_columns={},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.5
        assert "column validation skipped" in result.reason.lower()

    def test_no_schema_metadata(self) -> None:
        """No allowed_tables or allowed_columns → skip with 1.0."""
        record = _sql_record(
            allowed_tables=[],
            allowed_columns={},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0
        assert result.status == EvaluatorStatus.SKIPPED

    def test_table_alias_resolved(self) -> None:
        record = _sql_record(
            response="SELECT s.region, s.amount FROM sales s;",
            allowed_tables=["sales"],
            allowed_columns={"sales": ["region", "amount"]},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_multiple_tables_valid(self) -> None:
        record = _sql_record(
            response="SELECT s.region, p.name FROM sales s JOIN products p ON s.pid = p.id;",
            allowed_tables=["sales", "products"],
            allowed_columns={"sales": ["region", "pid"], "products": ["name", "id"]},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_case_insensitive(self) -> None:
        record = _sql_record(
            response="SELECT Region, Amount FROM Sales;",
            allowed_tables=["sales"],
            allowed_columns={"sales": ["region", "amount"]},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_select_star_passes(self) -> None:
        """SELECT * should pass table check (columns can't be validated)."""
        record = _sql_record(
            response="SELECT * FROM sales;",
            allowed_tables=["sales"],
            allowed_columns={"sales": ["region", "amount"]},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_parse_error(self) -> None:
        record = _sql_record(response="{{INVALID SQL}}")
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        assert "parse" in result.reason.lower()

    def test_partial_column_metadata(self) -> None:
        """allowed_columns only has some tables; unknown-table columns skip."""
        record = _sql_record(
            response="SELECT s.region, p.name FROM sales s JOIN products p ON s.pid = p.id;",
            allowed_tables=["sales", "products"],
            allowed_columns={"sales": ["region", "pid"]},  # no products columns
        )
        result = self.evaluator.evaluate(record)
        # products.name can't be validated → should still pass since table is allowed
        # and column set for products is not provided
        assert result.score == 1.0
