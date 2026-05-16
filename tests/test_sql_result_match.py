"""Tests for the sql_result_match evaluator."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import EvaluatorStatus
from rag_eval_framework.evaluators.sql.result_match import SqlResultMatchEvaluator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(**overrides: Any) -> EvaluationRecord:
    base: dict[str, Any] = {
        "id": "match-test",
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
    comparison_mode: str = "unordered",
    numeric_tolerance: float = 0.0,
    timeout_seconds: float = 5.0,
    max_rows: int = 1000,
    allow_multiple_statements: bool = False,
) -> Any:
    from rag_eval_framework.config.models import ProjectConfig

    db_path = tmp_path / db_name
    return ProjectConfig.model_validate(
        {
            "project_name": "match-test",
            "dataset_path": "datasets/rag-evaluation/eval.jsonl",
            "mode": "local",
            "local_mode": {
                "evaluators": ["sql_result_match"],
                "evaluator_options": {
                    "sql_result_match": {
                        "database_type": database_type,
                        "database_path": str(db_path),
                        "readonly": readonly,
                        "comparison_mode": comparison_mode,
                        "numeric_tolerance": numeric_tolerance,
                        "timeout_seconds": timeout_seconds,
                        "max_rows": max_rows,
                        "allow_multiple_statements": allow_multiple_statements,
                    },
                },
            },
        }
    )


def _create_test_db(tmp_path: Path, db_name: str = "test.db") -> Path:
    """Create a small SQLite DB with numeric data for testing."""
    db_path = tmp_path / db_name
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, price REAL)"
    )
    conn.execute("INSERT INTO items VALUES (1, 'alpha', 10.0)")
    conn.execute("INSERT INTO items VALUES (2, 'beta', 20.0)")
    conn.execute("INSERT INTO items VALUES (3, 'gamma', 30.0)")
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSqlResultMatch:
    """Unit tests for SqlResultMatchEvaluator."""

    def test_exact_match(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path, comparison_mode="exact"))
        rec = _make_record(
            response="SELECT id, name FROM items ORDER BY id;",
            expected_result=[
                {"id": 1, "name": "alpha"},
                {"id": 2, "name": "beta"},
                {"id": 3, "name": "gamma"},
            ],
        )
        result = ev.evaluate(rec)
        assert result.score == 1.0

    def test_unordered_match(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path, comparison_mode="unordered"))
        rec = _make_record(
            response="SELECT id, name FROM items ORDER BY id;",
            expected_result=[
                {"id": 3, "name": "gamma"},
                {"id": 1, "name": "alpha"},
                {"id": 2, "name": "beta"},
            ],
        )
        result = ev.evaluate(rec)
        assert result.score == 1.0

    def test_numeric_tolerance(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path, comparison_mode="unordered", numeric_tolerance=0.5))
        rec = _make_record(
            response="SELECT id, price FROM items WHERE id = 1;",
            expected_result=[{"id": 1, "price": 10.3}],
        )
        result = ev.evaluate(rec)
        assert result.score == 1.0

    def test_numeric_tolerance_exceeded(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path, comparison_mode="unordered", numeric_tolerance=0.01))
        rec = _make_record(
            response="SELECT id, price FROM items WHERE id = 1;",
            expected_result=[{"id": 1, "price": 99.0}],
        )
        result = ev.evaluate(rec)
        assert result.score == 0.0

    def test_result_mismatch(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(
            response="SELECT id, name FROM items WHERE id = 1;",
            expected_result=[{"id": 999, "name": "nonexistent"}],
        )
        result = ev.evaluate(rec)
        assert result.score == 0.0

    def test_execution_failure(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(
            response="SELECT * FROM nonexistent;",
            expected_result=[{"id": 1}],
        )
        result = ev.evaluate(rec)
        assert result.score == 0.0

    def test_missing_expected_result(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(
            response="SELECT * FROM items;",
            expected_result=[],
        )
        result = ev.evaluate(rec)
        assert result.score == 0.0
        assert result.status == EvaluatorStatus.SKIPPED

    def test_unsafe_sql_blocked(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(
            response="DELETE FROM items;",
            expected_result=[{"id": 1}],
        )
        result = ev.evaluate(rec)
        assert result.score == 0.0
        assert "blocked" in result.reason.lower() or "safety" in result.reason.lower()

    def test_row_count_mismatch(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path, comparison_mode="exact"))
        rec = _make_record(
            response="SELECT id, name FROM items ORDER BY id;",
            expected_result=[
                {"id": 1, "name": "alpha"},
            ],
        )
        result = ev.evaluate(rec)
        assert result.score == 0.0

    def test_empty_actual_result(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path))
        rec = _make_record(
            response="SELECT * FROM items WHERE id = 999;",
            expected_result=[{"id": 1, "name": "alpha", "price": 10.0}],
        )
        result = ev.evaluate(rec)
        assert result.score == 0.0

    def test_not_configured(self) -> None:
        ev = SqlResultMatchEvaluator()
        rec = _make_record(
            response="SELECT 1;",
            expected_result=[{"1": 1}],
        )
        result = ev.evaluate(rec)
        assert result.score == 0.0
        assert result.status == EvaluatorStatus.ERROR
        assert "not configured" in result.reason.lower()

    def test_name_and_required_fields(self) -> None:
        ev = SqlResultMatchEvaluator()
        assert ev.name == "sql_result_match"
        assert ev.required_fields == ["response"]

    def test_subset_match(self, tmp_path: Path) -> None:
        _create_test_db(tmp_path)
        ev = SqlResultMatchEvaluator()
        ev.setup(_make_config(tmp_path, comparison_mode="subset"))
        rec = _make_record(
            response="SELECT id, name FROM items ORDER BY id;",
            expected_result=[
                {"id": 1, "name": "alpha"},
                {"id": 2, "name": "beta"},
            ],
        )
        result = ev.evaluate(rec)
        assert result.score >= 0.5
