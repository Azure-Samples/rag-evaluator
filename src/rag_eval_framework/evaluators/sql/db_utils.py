"""Shared database utilities for DB-backed SQL evaluators.

Provides safe SQL pre-execution checks, read-only SQLite connection handling,
query execution with row limits, and result normalization/comparison.

**Security**: These utilities are designed exclusively for local/sandbox
test databases. Never use against production databases.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blocked operations — fail-closed for destructive SQL
# ---------------------------------------------------------------------------

_BLOCKED_OPS: frozenset[str] = frozenset(
    {
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "TRUNCATE",
        "ALTER",
        "MERGE",
        "EXEC",
        "EXECUTE",
        "CALL",
    }
)

_BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(_BLOCKED_OPS) + r")\b",
    re.IGNORECASE,
)


def check_sql_safety(sql: str, *, allow_multiple_statements: bool = False) -> str | None:
    """Return a violation reason string if the SQL is unsafe, else ``None``.

    Checks:
    - Empty/whitespace SQL
    - Blocked operations via regex (fail-closed)
    - Multiple statements when not allowed
    """
    stripped = sql.strip()
    if not stripped:
        return "SQL is empty."

    # Check for blocked operations
    match = _BLOCKED_PATTERN.search(stripped)
    if match:
        return f"SQL execution blocked: contains destructive operation '{match.group(1).upper()}'."

    # Check for multiple statements (split on semicolons not inside strings)
    if not allow_multiple_statements:
        # Simplistic: count semicolons outside of string literals
        # Remove string literals first
        cleaned = re.sub(r"'[^']*'", "", stripped)
        cleaned = re.sub(r'"[^"]*"', "", cleaned)
        parts = [p.strip() for p in cleaned.split(";") if p.strip()]
        if len(parts) > 1:
            return "SQL execution blocked: multiple statements detected."

    return None


# ---------------------------------------------------------------------------
# SQLite connection helpers
# ---------------------------------------------------------------------------


def connect_sqlite(
    database_path: str,
    *,
    readonly: bool = True,
    timeout_seconds: float = 5.0,
) -> sqlite3.Connection:
    """Open a SQLite connection.

    Parameters
    ----------
    database_path : str
        Path to the SQLite database file.
    readonly : bool
        If True, open in read-only mode (requires SQLite URI support).
    timeout_seconds : float
        Connection timeout in seconds.

    Raises
    ------
    FileNotFoundError
        If the database file does not exist.
    sqlite3.Error
        On connection failure.
    """
    path = Path(database_path)
    if not path.exists():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    if readonly:
        uri = f"file:{path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=timeout_seconds)
    else:
        conn = sqlite3.connect(str(path), timeout=timeout_seconds)

    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------


def execute_query(
    conn: sqlite3.Connection,
    sql: str,
    *,
    max_rows: int = 1000,
    timeout_seconds: float = 5.0,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Execute a SELECT query and return (rows, column_names).

    Parameters
    ----------
    conn : sqlite3.Connection
        An open database connection.
    sql : str
        The SQL query to execute (must be a single SELECT).
    max_rows : int
        Maximum rows to fetch.
    timeout_seconds : float
        Execution timeout (set via sqlite3 progress handler).

    Returns
    -------
    tuple[list[dict[str, Any]], list[str]]
        A tuple of (result_rows_as_dicts, column_names).

    Raises
    ------
    sqlite3.Error
        On query execution failure.
    TimeoutError
        If the query exceeds the timeout.
    """
    # Set a progress handler as a timeout mechanism
    # sqlite3 progress_handler is called every N virtual machine instructions
    import time

    start = time.monotonic()

    def _timeout_handler() -> int:
        elapsed = time.monotonic() - start
        if elapsed > timeout_seconds:
            return 1  # non-zero cancels the operation
        return 0

    conn.set_progress_handler(_timeout_handler, 1000)

    try:
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows_raw = cursor.fetchmany(max_rows)
        rows = [dict(zip(columns, row, strict=False)) for row in rows_raw]
        return rows, columns
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise TimeoutError(
                f"Query execution exceeded {timeout_seconds}s timeout."
            ) from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)


# ---------------------------------------------------------------------------
# Result normalization and comparison
# ---------------------------------------------------------------------------


def normalize_value(val: Any) -> Any:
    """Normalize a single value for comparison.

    - None stays None
    - Integers and floats that are whole numbers → int
    - Strings are stripped and lowered for case-insensitive comparison
    """
    if val is None:
        return None
    if isinstance(val, float):
        if val == int(val):
            return int(val)
        return val
    if isinstance(val, str):
        return val.strip().lower()
    return val


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize all values in a row dict. Keys lowered."""
    return {k.lower(): normalize_value(v) for k, v in row.items()}


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize a list of row dicts."""
    return [normalize_row(r) for r in rows]


def compare_results(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    *,
    mode: str = "unordered",
    numeric_tolerance: float = 0.0,
) -> tuple[float, str]:
    """Compare actual vs expected result sets.

    Parameters
    ----------
    actual : list[dict]
        Actual query result rows.
    expected : list[dict]
        Expected result rows from the dataset.
    mode : str
        Comparison mode: 'exact', 'unordered', or 'subset'.
    numeric_tolerance : float
        Tolerance for numeric comparisons (absolute difference).

    Returns
    -------
    tuple[float, str]
        (score, reason) — score is 1.0 for match, 0.5 for subset, 0.0 for mismatch.
    """
    if not expected:
        return 0.0, "No expected result to compare against."

    norm_actual = normalize_rows(actual)
    norm_expected = normalize_rows(expected)

    if mode == "exact":
        return _compare_exact(norm_actual, norm_expected, numeric_tolerance)
    elif mode == "unordered":
        return _compare_unordered(norm_actual, norm_expected, numeric_tolerance)
    elif mode == "subset":
        return _compare_subset(norm_actual, norm_expected, numeric_tolerance)
    else:
        return 0.0, f"Unknown comparison mode: '{mode}'."


def _rows_equal(row_a: dict[str, Any], row_b: dict[str, Any], tolerance: float) -> bool:
    """Check if two normalized rows are equal within tolerance."""
    if set(row_a.keys()) != set(row_b.keys()):
        return False
    for key in row_a:
        va, vb = row_a[key], row_b[key]
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            return False
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            if tolerance > 0 and abs(float(va) - float(vb)) <= tolerance:
                continue
            if va != vb:
                return False
        elif va != vb:
            return False
    return True


def _compare_exact(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    tolerance: float,
) -> tuple[float, str]:
    """Exact comparison: same rows in same order."""
    if len(actual) != len(expected):
        return 0.0, (
            f"Row count mismatch: actual={len(actual)}, expected={len(expected)}."
        )
    for i, (a_row, e_row) in enumerate(zip(actual, expected, strict=True)):
        if not _rows_equal(a_row, e_row, tolerance):
            return 0.0, f"Row {i} differs between actual and expected."
    return 1.0, "Actual result matches expected result (exact comparison)."


def _compare_unordered(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    tolerance: float,
) -> tuple[float, str]:
    """Unordered comparison: same rows regardless of order."""
    if len(actual) != len(expected):
        return 0.0, (
            f"Row count mismatch: actual={len(actual)}, expected={len(expected)}."
        )
    # Try to match each expected row with an actual row
    remaining = list(actual)
    for e_row in expected:
        matched = False
        for i, a_row in enumerate(remaining):
            if _rows_equal(a_row, e_row, tolerance):
                remaining.pop(i)
                matched = True
                break
        if not matched:
            return 0.0, "Actual result does not match expected result (unordered comparison)."
    return 1.0, "Actual result matches expected result (unordered comparison)."


def _compare_subset(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    tolerance: float,
) -> tuple[float, str]:
    """Subset comparison: all expected rows must be present in actual."""
    for e_row in expected:
        found = any(_rows_equal(a_row, e_row, tolerance) for a_row in actual)
        if not found:
            return 0.0, "Not all expected rows found in actual result (subset comparison)."
    if len(actual) == len(expected):
        return 1.0, "Actual result matches expected result (subset comparison, exact set)."
    return 0.5, (
        f"All expected rows present in actual result, but actual has "
        f"{len(actual) - len(expected)} extra row(s) (subset comparison)."
    )
