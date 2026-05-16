"""Tests for the sql_execution_success evaluator."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import EvaluatorStatus
from rag_eval_framework.evaluators.sql.execution import SqlExecutionSuccessEvaluator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(**overrides: Any) -> EvaluationRecord:
    base: dict[str, Any] = {
        "id": "exec-test",
        "question": "test question",
        "response": "SELECT 1;",
    }
    base.update(overrides)
    return EvaluationRecord.model_validate(base)


def _make_config(
    tmp_path: Path,
    db_name: str = "test.db",
    *,
    database_type: str = "sqlite",
    readonly: bool = True,
    timeout_seconds: float = 5.0,
    max_rows: int = 1000,
    allow_multiple_statements: bool = False,
) -> Any:
    """Return a lightweight config-like object with evaluator_options."""
    from rag_eval_framework.config.models import ProjectConfig

    db_path = tmp_path / db_name
    return ProjectConfig.model_validate(
        {
            "project_name": "exec-test",
            "dataset_path": "datasets/rag-evaluation/eval.jsonl",
            "mode": "local",
            "local_mode": {
                "evaluators": ["sql_execution_success"],
                "evaluator_options": {
                    "sql_execution_success": {
                        "database_type": database_type,
                        "database_path": str(db_path),
                        "readonly": readonly,
                        "timeout_seconds": timeout_seconds,
                        "max_rows": max_rows,
                        "allow_multiple_statements": allow_multiple_statements,
                    },
                },
            },
        }
    )


def _create_test_db(tmp_path: Path, db_name: str = "test.db") -> Path:
    """Create a small SQLite DB and return its path."""
    db_path = tmp_path / db_name
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO items VALUES (1, 'alpha')")
    conn.execute("INSERT INTO items VALUES (2, 'beta')")
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSqlExecutionSuccess:
    """Unit tests for SqlExecutionSuccessEvaluator."""

    def test_valid_select(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlExecutionSuccessEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(response="SELECT * FROM items;")
        result = ev.evaluate(rec)
        assert result.score == 1.0
        assert result.status == EvaluatorStatus.SUCCESS
        assert result.metadata["rows_returned"] == 2

    def test_invalid_table(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlExecutionSuccessEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(response="SELECT * FROM nonexistent;")
        result = ev.evaluate(rec)
        assert result.score == 0.0
        assert "no such table" in result.reason.lower()

    def test_invalid_column(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlExecutionSuccessEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(response="SELECT fake_col FROM items;")
        result = ev.evaluate(rec)
        assert result.score == 0.0

    def test_unsafe_delete_blocked(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlExecutionSuccessEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(response="DELETE FROM items WHERE id = 1;")
        result = ev.evaluate(rec)
        assert result.score == 0.0
        assert "blocked" in result.reason.lower() or "safety" in result.reason.lower()

    def test_unsafe_drop_blocked(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlExecutionSuccessEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(response="DROP TABLE items;")
        result = ev.evaluate(rec)
        assert result.score == 0.0

    def test_empty_sql(self, tmp_path: Path) -> None:
        """Empty/whitespace response is rejected by EvaluationRecord validation."""
        from pydantic import ValidationError

        _create_test_db(tmp_path)
        with pytest.raises(ValidationError, match="[Rr]esponse"):
            _make_record(response="   ")

    def test_multiple_statements_blocked(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlExecutionSuccessEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(response="SELECT 1; SELECT 2;")
        result = ev.evaluate(rec)
        assert result.score == 0.0
        assert "multiple" in result.reason.lower()

    def test_not_configured(self) -> None:
        ev = SqlExecutionSuccessEvaluator()
        rec = _make_record(response="SELECT 1;")
        result = ev.evaluate(rec)
        assert result.score == 0.0
        assert result.status == EvaluatorStatus.ERROR
        assert "not configured" in result.reason.lower()

    def test_missing_db_file(self, tmp_path: Path) -> None:
        ev = SqlExecutionSuccessEvaluator()
        ev.setup(_make_config(tmp_path, db_name="missing.db"))
        rec = _make_record(response="SELECT 1;")
        result = ev.evaluate(rec)
        assert result.score == 0.0
        assert result.status == EvaluatorStatus.ERROR

    def test_unsupported_database_type(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlExecutionSuccessEvaluator()
        ev.setup(_make_config(tmp_path, database_type="postgres"))
        rec = _make_record(response="SELECT 1;")
        result = ev.evaluate(rec)
        assert result.score == 0.0
        assert result.status == EvaluatorStatus.ERROR
        assert "unsupported" in result.reason.lower()

    def test_name_and_required_fields(self) -> None:
        ev = SqlExecutionSuccessEvaluator()
        assert ev.name == "sql_execution_success"
        assert ev.required_fields == ["response"]

    def test_aggregation_query(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlExecutionSuccessEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(response="SELECT COUNT(*) AS cnt FROM items;")
        result = ev.evaluate(rec)
        assert result.score == 1.0
        assert result.metadata["rows_returned"] == 1
