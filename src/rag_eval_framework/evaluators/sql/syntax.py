"""SQL syntax validity evaluator — checks whether generated SQL parses correctly.

Uses ``sqlglot`` for dialect-aware SQL parsing.  Returns ``score=1.0`` when
the SQL is syntactically valid and ``score=0.0`` otherwise.

**Required dataset fields**: ``response``
"""

from __future__ import annotations

import logging
from typing import Any

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import (
    BaseEvaluator,
    EvaluatorResult,
)
from rag_eval_framework.evaluators.sql import require_sqlglot

logger = logging.getLogger(__name__)


class SqlSyntaxValidityEvaluator(BaseEvaluator):
    """Validate whether the generated SQL is syntactically valid.

    Scoring
    -------
    * **1.0** — SQL parsed successfully (one or more statements).
    * **0.0** — SQL failed to parse, is empty, or contains multiple
      statements when ``allow_multi_statement`` is ``False``.
    """

    _dialect: str | None = None
    _allow_multi_statement: bool = False

    @property
    def name(self) -> str:
        return "sql_syntax_validity"

    @property
    def description(self) -> str:
        return "Validates SQL syntax via parsing (sqlglot)."

    @property
    def required_fields(self) -> list[str]:
        return ["response"]

    def setup(self, config: Any) -> None:
        from rag_eval_framework.config.models import ProjectConfig

        require_sqlglot()

        if not isinstance(config, ProjectConfig):
            return
        opts = config.evaluator_options.get(self.name, {})
        dialect = opts.get("dialect")
        self._dialect = dialect if dialect else None
        self._allow_multi_statement = bool(opts.get("allow_multi_statement", False))

    def evaluate(self, record: EvaluationRecord) -> EvaluatorResult:
        import sqlglot

        sql = record.response.strip()

        try:
            statements = sqlglot.parse(
                sql,
                dialect=self._dialect,
                error_level=sqlglot.ErrorLevel.RAISE,
            )
        except sqlglot.errors.ParseError as exc:
            return EvaluatorResult(
                score=0.0,
                reason=f"SQL parsing failed: {exc}",
                metadata={"parser": "sqlglot", "dialect": self._dialect or "auto"},
            )

        # Filter out empty/None statements (e.g. trailing semicolons)
        valid_stmts = [s for s in statements if s is not None]

        if not valid_stmts:
            return EvaluatorResult(
                score=0.0,
                reason="No executable SQL statements found.",
                metadata={"parser": "sqlglot", "statement_count": 0},
            )

        if len(valid_stmts) > 1 and not self._allow_multi_statement:
            return EvaluatorResult(
                score=0.0,
                reason=(
                    f"Multiple SQL statements detected ({len(valid_stmts)}), "
                    "but allow_multi_statement is false."
                ),
                metadata={
                    "parser": "sqlglot",
                    "statement_count": len(valid_stmts),
                    "dialect": self._dialect or "auto",
                },
            )

        return EvaluatorResult(
            score=1.0,
            reason=f"SQL parsed successfully ({len(valid_stmts)} statement(s)).",
            metadata={
                "parser": "sqlglot",
                "statement_count": len(valid_stmts),
                "dialect": self._dialect or "auto",
            },
        )
