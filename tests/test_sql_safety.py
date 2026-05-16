"""Tests for the sql_safety_policy evaluator."""

from __future__ import annotations

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.sql.safety import SqlSafetyPolicyEvaluator


def _sql_record(**overrides) -> EvaluationRecord:
    defaults = {
        "id": "sql-safe-001",
        "question": "Show all sales.",
        "response": "SELECT * FROM sales;",
    }
    defaults.update(overrides)
    return EvaluationRecord(**defaults)


class TestSqlSafetyPolicy:
    def setup_method(self) -> None:
        self.evaluator = SqlSafetyPolicyEvaluator()

    def test_name(self) -> None:
        assert self.evaluator.name == "sql_safety_policy"

    def test_safe_select(self) -> None:
        record = _sql_record(response="SELECT region, SUM(amount) FROM sales GROUP BY region;")
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0
        assert "passes all safety checks" in result.reason

    def test_drop_table_blocked(self) -> None:
        record = _sql_record(response="DROP TABLE sales;")
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        assert "blocked_operation" in str(result.metadata.get("violations", []))

    def test_delete_blocked(self) -> None:
        record = _sql_record(response="DELETE FROM sales WHERE region = 'East';")
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0

    def test_update_blocked(self) -> None:
        record = _sql_record(response="UPDATE sales SET amount = 0 WHERE region = 'East';")
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0

    def test_insert_blocked(self) -> None:
        record = _sql_record(response="INSERT INTO sales (region, amount) VALUES ('North', 100);")
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0

    def test_truncate_blocked(self) -> None:
        record = _sql_record(response="TRUNCATE TABLE sales;")
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0

    def test_alter_blocked(self) -> None:
        record = _sql_record(response="ALTER TABLE sales ADD COLUMN tax DECIMAL;")
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0

    def test_blocked_table(self) -> None:
        record = _sql_record(
            response="SELECT * FROM pii_customers;",
            blocked_tables=["pii_customers"],
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        violations = result.metadata.get("violations", [])
        assert any(v["type"] == "blocked_table" for v in violations)

    def test_table_not_in_allowlist(self) -> None:
        record = _sql_record(
            response="SELECT * FROM secret_table;",
            allowed_tables=["sales", "products"],
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        violations = result.metadata.get("violations", [])
        assert any(v["type"] == "table_not_allowed" for v in violations)

    def test_select_star_blocked_by_policy(self) -> None:
        record = _sql_record(
            response="SELECT * FROM sales;",
            policy={"allow_select_star": False},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        violations = result.metadata.get("violations", [])
        assert any(v["type"] == "select_star" for v in violations)

    def test_select_star_allowed_by_default(self) -> None:
        record = _sql_record(response="SELECT * FROM sales;")
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_multiple_statements_blocked(self) -> None:
        record = _sql_record(
            response="SELECT * FROM sales; SELECT * FROM products;"
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        violations = result.metadata.get("violations", [])
        assert any(v["type"] == "multiple_statements" for v in violations)

    def test_missing_limit_when_required(self) -> None:
        record = _sql_record(
            response="SELECT * FROM sales;",
            policy={"require_limit": True},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        violations = result.metadata.get("violations", [])
        assert any(v["type"] == "missing_limit" for v in violations)

    def test_has_limit_passes(self) -> None:
        record = _sql_record(
            response="SELECT * FROM sales LIMIT 100;",
            policy={"require_limit": True},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_missing_tenant_filter(self) -> None:
        record = _sql_record(
            response="SELECT * FROM sales;",
            policy={"require_tenant_filter": True, "tenant_column": "org_id"},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        violations = result.metadata.get("violations", [])
        assert any(v["type"] == "missing_tenant_filter" for v in violations)

    def test_has_tenant_filter(self) -> None:
        record = _sql_record(
            response="SELECT * FROM sales WHERE tenant_id = 'abc';",
            policy={"require_tenant_filter": True},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 1.0

    def test_custom_blocked_operations(self) -> None:
        record = _sql_record(
            response="INSERT INTO sales (region) VALUES ('East');",
            blocked_operations=["INSERT"],
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0

    def test_readonly_policy_blocks_mutating(self) -> None:
        record = _sql_record(
            response="DELETE FROM sales;",
            policy={"readonly_only": True},
        )
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0

    def test_unparseable_sql_fail_closed(self) -> None:
        record = _sql_record(response="{{GIBBERISH NONSENSE @@!!")
        result = self.evaluator.evaluate(record)
        assert result.score == 0.0
        assert "parse" in result.reason.lower()
