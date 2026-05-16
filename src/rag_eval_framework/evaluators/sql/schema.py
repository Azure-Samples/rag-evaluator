"""SQL schema validity evaluator — checks tables and columns against metadata.

Parses the generated SQL with ``sqlglot``, extracts referenced tables and
columns, and compares them against the ``allowed_tables`` and
``allowed_columns`` fields in the evaluation record.

**Required dataset fields**: ``response``
"""

from __future__ import annotations

import logging
from typing import Any

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import (
    BaseEvaluator,
    EvaluatorResult,
    EvaluatorStatus,
)
from rag_eval_framework.evaluators.sql import require_sqlglot

logger = logging.getLogger(__name__)


def _extract_tables(statements: list[Any]) -> list[str]:
    """Extract all table names from parsed sqlglot statements."""
    import sqlglot.expressions as exp

    tables: list[str] = []
    for stmt in statements:
        if stmt is None:
            continue
        for table in stmt.find_all(exp.Table):
            if table.name:
                tables.append(table.name)
    return tables


def _extract_columns(statements: list[Any]) -> list[tuple[str, str]]:
    """Extract ``(table_or_alias, column)`` pairs from parsed statements.

    Returns pairs where the table part may be empty when no qualifier is
    present (e.g. bare ``column`` references).
    """
    import sqlglot.expressions as exp

    columns: list[tuple[str, str]] = []
    for stmt in statements:
        if stmt is None:
            continue
        for col in stmt.find_all(exp.Column):
            col_name = col.name
            table_ref = col.table or ""
            if col_name:
                columns.append((table_ref, col_name))
    return columns


def _resolve_aliases(statements: list[Any]) -> dict[str, str]:
    """Build a mapping from table alias → real table name."""
    import sqlglot.expressions as exp

    aliases: dict[str, str] = {}
    for stmt in statements:
        if stmt is None:
            continue
        for table in stmt.find_all(exp.Table):
            alias_node = table.args.get("alias")
            if alias_node and table.name:
                aliases[alias_node.name.lower()] = table.name.lower()
    return aliases


class SqlSchemaValidityEvaluator(BaseEvaluator):
    """Validate SQL tables and columns against schema metadata.

    Scoring
    -------
    * **1.0** — all referenced tables and columns are valid.
    * **0.5** — tables are valid but column validation was incomplete.
    * **0.0** — hallucinated table or clearly invalid column detected.

    When no schema metadata is provided the evaluator scores ``1.0`` with
    status ``SKIPPED`` to avoid false negatives.
    """

    @property
    def name(self) -> str:
        return "sql_schema_validity"

    @property
    def description(self) -> str:
        return "Verifies SQL uses valid tables/columns from the declared schema."

    @property
    def required_fields(self) -> list[str]:
        return ["response"]

    def setup(self, config: Any) -> None:
        require_sqlglot()

    def evaluate(self, record: EvaluationRecord) -> EvaluatorResult:
        import sqlglot

        sql = record.response.strip()
        allowed_tables = record.allowed_tables
        allowed_columns = record.allowed_columns

        # If no schema metadata at all, skip gracefully
        if not allowed_tables and not allowed_columns:
            return EvaluatorResult(
                score=1.0,
                status=EvaluatorStatus.SKIPPED,
                reason="No schema metadata (allowed_tables / allowed_columns) to validate against.",
                metadata={"validation_level": "none"},
            )

        try:
            statements = sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.RAISE)
        except sqlglot.errors.ParseError as exc:
            return EvaluatorResult(
                score=0.0,
                reason=f"SQL could not be parsed for schema validation: {exc}",
                metadata={"validation_level": "parse_failed"},
            )

        valid_stmts = [s for s in statements if s is not None]
        if not valid_stmts:
            return EvaluatorResult(
                score=0.0,
                reason="No executable SQL statements found for schema validation.",
                metadata={"validation_level": "no_statements"},
            )

        # --- Table validation ---------------------------------------------
        referenced_tables = _extract_tables(valid_stmts)
        ref_tables_lower = [t.lower() for t in referenced_tables]
        ref_tables_set = set(ref_tables_lower)

        unknown_tables: list[str] = []
        if allowed_tables:
            allowed_lower = {t.lower() for t in allowed_tables}
            unknown_tables = sorted(ref_tables_set - allowed_lower)

        if unknown_tables:
            return EvaluatorResult(
                score=0.0,
                reason=f"SQL references unknown table(s): {', '.join(unknown_tables)}.",
                metadata={
                    "validation_level": "table",
                    "referenced_tables": sorted(ref_tables_set),
                    "unknown_tables": unknown_tables,
                },
            )

        # --- Column validation --------------------------------------------
        if not allowed_columns:
            return EvaluatorResult(
                score=0.5 if allowed_tables else 1.0,
                reason=(
                    "Tables are valid. Column validation skipped (no allowed_columns provided)."
                    if allowed_tables
                    else "Schema validation passed."
                ),
                metadata={
                    "validation_level": "table_only",
                    "referenced_tables": sorted(ref_tables_set),
                },
            )

        aliases = _resolve_aliases(valid_stmts)
        columns = _extract_columns(valid_stmts)

        # Normalise allowed_columns to lower-case
        allowed_cols_lower: dict[str, set[str]] = {
            tbl.lower(): {c.lower() for c in cols}
            for tbl, cols in allowed_columns.items()
        }

        unknown_columns: list[str] = []
        for table_ref, col_name in columns:
            # Skip star expressions
            if col_name == "*":
                continue
            # Resolve alias → real table
            real_table = aliases.get(table_ref.lower(), table_ref.lower()) if table_ref else ""
            if not real_table:
                # Bare column — try to match against any allowed table
                found = any(
                    col_name.lower() in cols for cols in allowed_cols_lower.values()
                )
                if not found:
                    unknown_columns.append(col_name)
            else:
                col_set = allowed_cols_lower.get(real_table)
                if col_set is not None and col_name.lower() not in col_set:
                    unknown_columns.append(f"{real_table}.{col_name}")

        unknown_columns = sorted(set(unknown_columns))

        if unknown_columns:
            return EvaluatorResult(
                score=0.0,
                reason=f"SQL references unknown column(s): {', '.join(unknown_columns)}.",
                metadata={
                    "validation_level": "column",
                    "referenced_tables": sorted(ref_tables_set),
                    "unknown_columns": unknown_columns,
                },
            )

        return EvaluatorResult(
            score=1.0,
            reason="All referenced tables and columns are valid.",
            metadata={
                "validation_level": "column",
                "referenced_tables": sorted(ref_tables_set),
            },
        )
