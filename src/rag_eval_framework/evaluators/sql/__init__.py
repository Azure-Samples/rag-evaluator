"""SQL evaluation evaluators.

This package provides evaluators for validating LLM-generated SQL queries:

* :class:`SqlSyntaxValidityEvaluator` — syntax parsing via sqlglot
* :class:`SqlSafetyPolicyEvaluator` — read-only / safety policy checks
* :class:`SqlSchemaValidityEvaluator` — table and column validation
* :class:`SqlSemanticJudge` — LLM-as-a-judge semantic correctness
* :class:`SqlExecutionSuccessEvaluator` — DB-backed execution check
* :class:`SqlResultMatchEvaluator` — DB-backed result comparison
"""

_SQLGLOT_INSTALL_HINT = (
    "The 'sqlglot' package is required for SQL evaluators. "
    "Install with:  pip install 'rag-eval-framework[sql]'"
)


def require_sqlglot() -> None:
    """Import ``sqlglot`` or raise a clear :class:`ImportError`."""
    try:
        import sqlglot as _sqlglot  # noqa: F401
    except ImportError as exc:
        raise ImportError(_SQLGLOT_INSTALL_HINT) from exc
