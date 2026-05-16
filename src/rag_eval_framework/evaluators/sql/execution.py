"""SQL execution success evaluator — runs SQL against a safe test database.

Executes the generated SQL from ``response`` against a configured local
SQLite database and checks whether it completes successfully.

**Security**: This evaluator is designed exclusively for local/sandbox
test databases.  It blocks destructive operations, enforces read-only
connections, and will not execute SQL without explicit database configuration.

**Required dataset fields**: ``response``
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
    connect_sqlite,
    execute_query,
)

logger = logging.getLogger(__name__)


class SqlExecutionSuccessEvaluator(BaseEvaluator):
    """Execute generated SQL against a test database and check for success.

    Scoring
    -------
    * **1.0** — SQL executed successfully.
    * **0.0** — SQL failed to execute, is unsafe, or no database configured.
    """

    _database_type: str = ""
    _database_path: str = ""
    _readonly: bool = True
    _timeout_seconds: float = 5.0
    _max_rows: int = 1000
    _allow_multiple_statements: bool = False
    _configured: bool = False

    @property
    def name(self) -> str:
        return "sql_execution_success"

    @property
    def description(self) -> str:
        return "Executes SQL against a test database and checks for runtime success."

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

        if self._database_type and self._database_path:
            self._configured = True
            logger.info(
                "sql_execution_success configured: type=%s, path=%s, readonly=%s",
                self._database_type,
                self._database_path,
                self._readonly,
            )

    def evaluate(self, record: EvaluationRecord) -> EvaluatorResult:
        if not self._configured:
            return EvaluatorResult(
                score=0.0,
                status=EvaluatorStatus.ERROR,
                reason=(
                    "sql_execution_success is not configured. "
                    "Set database_type and database_path in evaluator_options."
                ),
            )

        sql = record.response.strip()

        # --- Safety check before execution --------------------------------
        violation = check_sql_safety(
            sql, allow_multiple_statements=self._allow_multiple_statements
        )
        if violation:
            return EvaluatorResult(
                score=0.0,
                reason=violation,
                metadata={"database_type": self._database_type},
            )

        # --- Execute against database -------------------------------------
        if self._database_type == "sqlite":
            return self._execute_sqlite(sql)
        else:
            return EvaluatorResult(
                score=0.0,
                status=EvaluatorStatus.ERROR,
                reason=f"Unsupported database_type: '{self._database_type}'. Supported: sqlite.",
            )

    def _execute_sqlite(self, sql: str) -> EvaluatorResult:
        """Execute SQL against a SQLite database."""
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
            return EvaluatorResult(
                score=1.0,
                reason="SQL executed successfully against the configured SQLite test database.",
                metadata={
                    "database_type": "sqlite",
                    "rows_returned": len(rows),
                    "columns": columns,
                },
            )
        except TimeoutError as exc:
            return EvaluatorResult(
                score=0.0,
                reason=str(exc),
                metadata={"database_type": "sqlite"},
            )
        except sqlite3.Error as exc:
            return EvaluatorResult(
                score=0.0,
                reason=f"SQL execution failed: {exc}",
                metadata={"database_type": "sqlite"},
            )
        finally:
            conn.close()
