"""SQL result match evaluator — compares query results to expected output.

Executes the generated SQL from ``response`` against a configured local
SQLite database and compares the actual result set to ``expected_result``
from the dataset record.

**Security**: This evaluator is designed exclusively for local/sandbox
test databases.  It blocks destructive operations, enforces read-only
connections, and will not execute SQL without explicit database configuration.

**Required dataset fields**: ``response``, ``expected_result``
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import (
    BaseEvaluator,
    EvaluatorResult,
    EvaluatorStatus,
)
from rag_eval_framework.evaluators.sql.db_utils import (
    check_sql_safety,
    compare_results,
    connect_sqlite,
    execute_query,
)

logger = logging.getLogger(__name__)


class SqlResultMatchEvaluator(BaseEvaluator):
    """Execute generated SQL and compare results to expected output.

    Scoring
    -------
    * **1.0** — actual result matches expected result.
    * **0.5** — partial/subset match (when ``comparison_mode='subset'``).
    * **0.0** — result mismatch, execution failure, or unsafe SQL.
    """

    _database_type: str = ""
    _database_path: str = ""
    _readonly: bool = True
    _timeout_seconds: float = 5.0
    _max_rows: int = 1000
    _allow_multiple_statements: bool = False
    _comparison_mode: str = "unordered"
    _numeric_tolerance: float = 0.0
    _configured: bool = False

    @property
    def name(self) -> str:
        return "sql_result_match"

    @property
    def description(self) -> str:
        return "Executes SQL and compares results to expected output."

    @property
    def required_fields(self) -> list[str]:
        return ["response"]

    def setup(self, config: Any) -> None:
        from rag_eval_framework.config.models import ProjectConfig

        if not isinstance(config, ProjectConfig):
            return

        opts = config.evaluator_options.get(self.name, {})
        self._database_type = opts.get("database_type", "")
        self._database_path = opts.get("database_path", "")
        self._readonly = bool(opts.get("readonly", True))
        self._timeout_seconds = float(opts.get("timeout_seconds", 5.0))
        self._max_rows = int(opts.get("max_rows", 1000))
        self._allow_multiple_statements = bool(opts.get("allow_multiple_statements", False))
        self._comparison_mode = opts.get("comparison_mode", "unordered")
        self._numeric_tolerance = float(opts.get("numeric_tolerance", 0.0))

        if self._database_type and self._database_path:
            self._configured = True
            logger.info(
                "sql_result_match configured: type=%s, path=%s, mode=%s",
                self._database_type,
                self._database_path,
                self._comparison_mode,
            )

    def evaluate(self, record: EvaluationRecord) -> EvaluatorResult:
        if not self._configured:
            return EvaluatorResult(
                score=0.0,
                status=EvaluatorStatus.ERROR,
                reason=(
                    "sql_result_match is not configured. "
                    "Set database_type and database_path in evaluator_options."
                ),
            )

        sql = record.response.strip()
        expected = record.expected_result

        if not expected:
            return EvaluatorResult(
                score=0.0,
                status=EvaluatorStatus.SKIPPED,
                reason="No expected_result provided for result comparison.",
                metadata={
                    "database_type": self._database_type,
                    "comparison_mode": self._comparison_mode,
                },
            )

        # --- Safety check before execution --------------------------------
        violation = check_sql_safety(
            sql, allow_multiple_statements=self._allow_multiple_statements
        )
        if violation:
            return EvaluatorResult(
                score=0.0,
                reason=violation,
                metadata={
                    "database_type": self._database_type,
                    "comparison_mode": self._comparison_mode,
                },
            )

        # --- Execute and compare ------------------------------------------
        if self._database_type == "sqlite":
            return self._execute_and_compare_sqlite(sql, expected)
        else:
            return EvaluatorResult(
                score=0.0,
                status=EvaluatorStatus.ERROR,
                reason=f"Unsupported database_type: '{self._database_type}'. Supported: sqlite.",
            )

    def _execute_and_compare_sqlite(
        self, sql: str, expected: list[dict[str, Any]]
    ) -> EvaluatorResult:
        """Execute SQL against SQLite and compare results."""
        try:
            conn = connect_sqlite(
                self._database_path,
                readonly=self._readonly,
                timeout_seconds=self._timeout_seconds,
            )
        except FileNotFoundError as exc:
            return EvaluatorResult(
                score=0.0,
                status=EvaluatorStatus.ERROR,
                reason=str(exc),
                metadata={"database_type": "sqlite"},
            )
        except sqlite3.Error as exc:
            return EvaluatorResult(
                score=0.0,
                status=EvaluatorStatus.ERROR,
                reason=f"Database connection failed: {exc}",
                metadata={"database_type": "sqlite"},
            )

        try:
            rows, columns = execute_query(
                conn,
                sql,
                max_rows=self._max_rows,
                timeout_seconds=self._timeout_seconds,
            )
        except TimeoutError as exc:
            return EvaluatorResult(
                score=0.0,
                reason=str(exc),
                metadata={"database_type": "sqlite", "comparison_mode": self._comparison_mode},
            )
        except sqlite3.Error as exc:
            return EvaluatorResult(
                score=0.0,
                reason=f"SQL execution failed: {exc}",
                metadata={"database_type": "sqlite", "comparison_mode": self._comparison_mode},
            )
        finally:
            conn.close()

        # --- Compare results ----------------------------------------------
        score, reason = compare_results(
            rows,
            expected,
            mode=self._comparison_mode,
            numeric_tolerance=self._numeric_tolerance,
        )

        return EvaluatorResult(
            score=score,
            reason=reason,
            metadata={
                "database_type": "sqlite",
                "comparison_mode": self._comparison_mode,
                "expected_rows": len(expected),
                "actual_rows": len(rows),
                "numeric_tolerance": self._numeric_tolerance,
            },
        )
