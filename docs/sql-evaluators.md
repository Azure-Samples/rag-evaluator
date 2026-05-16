# SQL Evaluators — Complete User Guide

## Table of Contents

1. [Overview](#overview)
2. [Why SQL Evaluation Needs Custom Evaluators](#why-sql-evaluation-needs-custom-evaluators)
3. [Evaluator List](#evaluator-list)
4. [Dataset-Only Evaluators](#dataset-only-evaluators)
5. [DB-Backed Evaluators](#db-backed-evaluators)
6. [Dataset Field Reference](#dataset-field-reference)
7. [Example Dataset Records](#example-dataset-records)
8. [YAML Configuration Examples](#yaml-configuration-examples)
9. [How to Run Dataset-Only Evaluation](#how-to-run-dataset-only-evaluation)
10. [How to Create the Sample SQLite Database](#how-to-create-the-sample-sqlite-database)
11. [How to Run DB-Backed Evaluation](#how-to-run-db-backed-evaluation)
12. [How to Interpret Scores](#how-to-interpret-scores)
13. [Security Warnings](#security-warnings)
14. [CI/CD Gating Guidance](#cicd-gating-guidance)
15. [Limitations](#limitations)
16. [Troubleshooting](#troubleshooting)
17. [Future Enhancements](#future-enhancements)

---

## Overview

SQL evaluators extend the framework to validate **LLM-generated SQL queries**. While standard RAG evaluators assess natural-language responses for groundedness, relevance, and accuracy, SQL evaluation requires specialised checks for **syntax correctness**, **safety policy compliance**, **schema validity**, **semantic correctness**, and **execution accuracy**.

These evaluators are designed for production AI workloads where an LLM generates SQL from user questions — a common pattern in text-to-SQL, data chatbot, and analytics copilot applications.

The framework provides **six SQL evaluators** in two tiers:

- **Dataset-only** (4) — validate SQL structure using only the dataset record. No database required.
- **DB-backed** (2) — execute SQL against a configured local/sandbox test database to verify runtime behaviour and result correctness.

---

## Why SQL Evaluation Needs Custom Evaluators

| Aspect | RAG Evaluation | SQL Evaluation |
|--------|---------------|----------------|
| Output | Natural language | Structured SQL code |
| Correctness | Semantic similarity to ground truth | Parseable, executable, schema-valid |
| Safety | Policy compliance (tone, content) | Read-only enforcement, blocked operations |
| Validation | LLM judges, human review | Deterministic parsing + LLM judges |
| Execution | N/A | Optional DB execution for result match |

Standard RAG evaluators (groundedness, relevance, completeness) cannot assess whether `SELECT * FROM sales WHERE date > '2025-01-01'` is valid SQL, uses allowed tables, avoids destructive operations, or returns the correct result set. SQL evaluators fill this gap.

---

## Evaluator List

| Evaluator | Type | Requires DB | Required Fields | Dep |
|-----------|------|-------------|-----------------|-----|
| `sql_syntax_validity` | Deterministic | No | `response` | sqlglot |
| `sql_safety_policy` | Deterministic | No | `response` | sqlglot |
| `sql_schema_validity` | Deterministic | No | `response` | sqlglot |
| `sql_semantic_judge` | LLM Judge | No | `question`, `response` | Azure OpenAI |
| `sql_execution_success` | DB-backed | Yes | `response` | sqlite3 (stdlib) |
| `sql_result_match` | DB-backed | Yes | `response`, `expected_result` | sqlite3 (stdlib) |

---

## Dataset-Only Evaluators

These evaluators use only the fields present in the dataset record. No live database connection is needed.

### `sql_syntax_validity`

Validates whether the SQL in `response` can be parsed using [sqlglot](https://github.com/tobymao/sqlglot).

| Score | Meaning |
|-------|---------|
| 1.0 | SQL parsed successfully |
| 0.0 | Parse failed, empty SQL, or multiple statements when disallowed |

**Configuration** (via `evaluator_options`):

| Option | Default | Description |
|--------|---------|-------------|
| `dialect` | auto-detect | SQL dialect: `mysql`, `postgres`, `sqlite`, `tsql`, etc. |
| `allow_multi_statement` | `false` | Allow multiple SQL statements separated by `;` |

### `sql_safety_policy`

Checks whether the SQL respects safety policies. Uses a **fail-closed** approach: if the SQL cannot be parsed confidently, it is scored `0.0`.

| Score | Meaning |
|-------|---------|
| 1.0 | All safety checks passed |
| 0.0 | One or more violations detected |

**Checks performed:**

- Blocked operations (DROP, DELETE, UPDATE, INSERT, TRUNCATE, ALTER, MERGE, EXEC, EXECUTE, CALL)
- Blocked table access
- Allowed table enforcement
- SELECT * restriction (if `policy.allow_select_star` is `false`)
- LIMIT clause requirement (if `policy.require_limit` is `true`)
- Tenant filter requirement (if `policy.require_tenant_filter` is `true`)
- Multiple statement restriction

**Policy flags** (set per record via the `policy` field):

| Flag | Default | Description |
|------|---------|-------------|
| `readonly_only` | `true` | Block all mutating operations |
| `require_limit` | `false` | Require LIMIT / TOP clause |
| `require_tenant_filter` | `false` | Require WHERE filter on tenant column |
| `tenant_column` | `tenant_id` | Column name for tenant filter |
| `allow_select_star` | `true` | Allow SELECT * |
| `allow_multiple_statements` | `false` | Allow multi-statement SQL |

### `sql_schema_validity`

Validates tables and columns against schema metadata in the dataset record.

| Score | Meaning |
|-------|---------|
| 1.0 | All tables and columns are valid |
| 0.5 | Tables valid but column validation incomplete (no `allowed_columns`) |
| 0.0 | Hallucinated table or column detected |
| 1.0 (SKIPPED) | No schema metadata provided |

**Features:** Table alias resolution, case-insensitive matching, SELECT * passes table validation, partial metadata support.

### `sql_semantic_judge`

Uses an LLM to evaluate whether the SQL semantically answers the user's question. Reuses the framework's `BaseLLMJudge` pattern.

**Requires:** Azure OpenAI credentials (`azure` config section).

| Score | Meaning |
|-------|---------|
| 0.8–1.0 | SQL correctly answers the question |
| 0.4–0.7 | Partial correctness (wrong filter, missing aggregation) |
| 0.0–0.3 | SQL does not answer the question |

**Evaluation criteria:** correct tables, correct filters (date ranges, WHERE), correct aggregation, correct joins, business meaning preserved.

---

## DB-Backed Evaluators

DB-backed evaluators **execute SQL against a configured local/sandbox test database**. They include safety guards: blocked destructive operations, read-only connections, and query timeouts.

### `sql_execution_success`

Executes the SQL in `response` against a configured SQLite database and checks whether it completes without errors.

| Score | Meaning |
|-------|---------|
| 1.0 | SQL executed successfully |
| 0.0 | Execution failed, unsafe SQL, or not configured |

**Configuration** (via `evaluator_options`):

| Option | Default | Description |
|--------|---------|-------------|
| `database_type` | (required) | Database engine: `sqlite` |
| `database_path` | (required) | Path to the database file |
| `readonly` | `true` | Open database in read-only mode |
| `timeout_seconds` | `5.0` | Query timeout in seconds |
| `max_rows` | `1000` | Maximum rows returned |
| `allow_multiple_statements` | `false` | Allow multi-statement SQL |

### `sql_result_match`

Executes SQL and compares the result set to `expected_result` from the dataset record.

| Score | Meaning |
|-------|---------|
| 1.0 | Results match expected output |
| 0.5 | Partial/subset match (when `comparison_mode='subset'`) |
| 0.0 | Mismatch, execution failure, or unsafe SQL |
| SKIPPED | No `expected_result` provided |

**Configuration** (via `evaluator_options`): same as `sql_execution_success`, plus:

| Option | Default | Description |
|--------|---------|-------------|
| `comparison_mode` | `unordered` | `exact`, `unordered`, or `subset` |
| `numeric_tolerance` | `0.0` | Tolerance for floating-point comparison |

**Comparison modes:**

- **`exact`** — Row order and values must match exactly.
- **`unordered`** — Same rows required, any order. Good for GROUP BY queries.
- **`subset`** — All expected rows must appear in actual results (actual may have extra). Scores 0.5 for partial matches.

---

## Dataset Field Reference

| Field | Required | Used By | Description |
|-------|----------|---------|-------------|
| `response` | Yes | All | The LLM-generated SQL query |
| `question` | Yes | `sql_semantic_judge` | The user's natural-language question |
| `schema_context` | No | `sql_semantic_judge` | Database schema description (free text) |
| `expected_sql` | No | `sql_semantic_judge` | Reference SQL for comparison |
| `expected_behavior` | No | `sql_semantic_judge` | Description of expected behavior |
| `expected_result` | No | `sql_result_match` | Expected query result as list of row dicts |
| `allowed_tables` | No | `sql_safety_policy`, `sql_schema_validity` | Tables the SQL may reference |
| `blocked_tables` | No | `sql_safety_policy` | Tables the SQL must NOT reference |
| `allowed_columns` | No | `sql_schema_validity` | Per-table column allowlists |
| `blocked_operations` | No | `sql_safety_policy` | Forbidden SQL operations |
| `policy` | No | `sql_safety_policy` | Safety policy flags (see above) |

All SQL-specific fields are optional with sensible defaults. Existing RAG datasets work without modification.

---

## Example Dataset Records

### Dataset-Only Record

```json
{
  "id": "sql_dataset_only_001",
  "question": "Show total sales by region for Q1 2025.",
  "response": "SELECT r.region_name, SUM(s.amount) AS total_sales FROM sales s JOIN regions r ON s.region_id = r.region_id WHERE s.sale_date >= '2025-01-01' AND s.sale_date < '2025-04-01' GROUP BY r.region_name;",
  "schema_context": "Tables: sales(region_id, amount, sale_date, tenant_id), regions(region_id, region_name)",
  "expected_behavior": "Aggregate total sales by region for Q1 2025 via join.",
  "allowed_tables": ["sales", "regions"],
  "blocked_tables": ["employee_salary", "pii_customers"],
  "allowed_columns": {
    "sales": ["region_id", "amount", "sale_date", "tenant_id"],
    "regions": ["region_id", "region_name"]
  },
  "blocked_operations": ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER"],
  "policy": {
    "readonly_only": true,
    "require_limit": false,
    "require_tenant_filter": false,
    "allow_select_star": false,
    "max_rows": 1000
  }
}
```

### DB-Backed Record

```json
{
  "id": "sql_db_001",
  "question": "Show total sales by region for Q1 2025.",
  "response": "SELECT r.region_name, SUM(s.amount) AS total_sales FROM sales s JOIN regions r ON s.region_id = r.region_id WHERE s.sale_date >= '2025-01-01' AND s.sale_date < '2025-04-01' GROUP BY r.region_name ORDER BY r.region_name;",
  "schema_context": "Tables: sales(sale_id, customer_id, product_id, region_id, amount, sale_date, tenant_id), regions(region_id, region_name)",
  "expected_behavior": "Aggregate total sales by region for Q1 2025.",
  "expected_result": [
    {"region_name": "East", "total_sales": 45000.0},
    {"region_name": "North", "total_sales": 15000.0},
    {"region_name": "South", "total_sales": 30000.0},
    {"region_name": "West", "total_sales": 30000.0}
  ],
  "allowed_tables": ["sales", "regions"],
  "allowed_columns": {
    "sales": ["sale_id", "customer_id", "product_id", "region_id", "amount", "sale_date", "tenant_id"],
    "regions": ["region_id", "region_name"]
  },
  "blocked_operations": ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER"],
  "policy": {"readonly_only": true}
}
```

---

## YAML Configuration Examples

### Dataset-Only Evaluation

```yaml
project_name: sql-eval-dataset-only
dataset_path: datasets/sample/sql-evaluation/sql_eval_dataset.jsonl
mode: local

report_format:
  - json
  - markdown
  - html
output_dir: output

local_mode:
  evaluators:
    - sql_syntax_validity
    - sql_safety_policy
    - sql_schema_validity
    # Uncomment for LLM judge (requires Azure OpenAI):
    # - sql_semantic_judge

  thresholds:
    sql_syntax_validity: 0.80
    sql_safety_policy: 1.0
    sql_schema_validity: 0.80

  # Required for sql_semantic_judge:
  # azure:
  #   endpoint: "https://your-endpoint.openai.azure.com"
  #   deployment_name: "gpt-4o-mini"
  #   api_version: "2024-12-01-preview"
  #   credential_type: default
```

### DB-Backed Evaluation

```yaml
project_name: sql-eval-db-backed
dataset_path: datasets/sample/sql-evaluation/sql_eval_dataset_db.jsonl
mode: local

report_format:
  - json
  - markdown
  - html
output_dir: output

local_mode:
  evaluators:
    - sql_syntax_validity
    - sql_safety_policy
    - sql_schema_validity
    - sql_execution_success
    - sql_result_match

  thresholds:
    sql_syntax_validity: 0.80
    sql_safety_policy: 1.0
    sql_schema_validity: 0.80
    sql_execution_success: 0.70
    sql_result_match: 0.60

  evaluator_options:
    sql_execution_success:
      database_type: sqlite
      database_path: examples/sql-evaluation/sample_sql_eval.db
      readonly: true
      timeout_seconds: 5.0
      max_rows: 1000

    sql_result_match:
      database_type: sqlite
      database_path: examples/sql-evaluation/sample_sql_eval.db
      readonly: true
      comparison_mode: unordered
      numeric_tolerance: 0.001
```

---

## How to Run Dataset-Only Evaluation

```bash
# 1. Install with SQL support
pip install -e ".[sql]"

# 2. Run using the project-configs template
rag-eval --config project-configs/templates/sql-evals/sql_eval_config.yaml

# Alternative if rag-eval is not on PATH:
python -m rag_eval_framework --config project-configs/templates/sql-evals/sql_eval_config.yaml
```

> **Note:** The example datasets contain intentional negative cases (invalid SQL, unsafe operations, hallucinated tables). Threshold breaches in the report are expected and demonstrate the evaluators correctly detecting issues.

No database or Azure credentials are needed for the three deterministic evaluators (`sql_syntax_validity`, `sql_safety_policy`, `sql_schema_validity`). The `sql_semantic_judge` requires Azure OpenAI — uncomment the `azure` section in the config to enable it.

---

## How to Create the Sample SQLite Database

```bash
python examples/sql-evaluation/create_sample_sqlite_db.py
```

This creates `examples/sql-evaluation/sample_sql_eval.db` with four tables:

| Table | Rows | Description |
|-------|------|-------------|
| `regions` | 4 | East, West, North, South |
| `customers` | 6 | Synthetic company names |
| `products` | 5 | Widgets, Gadgets, Services |
| `sales` | 15 | Q1–Q2 2025 transactions with tenant_id |

All data is deterministic, synthetic, and non-sensitive. The script is **idempotent** — it replaces any existing database file.

---

## How to Run DB-Backed Evaluation

```bash
# 1. Install with SQL support
pip install -e ".[sql]"

# 2. Create the sample database
python examples/sql-evaluation/create_sample_sqlite_db.py

# 3. Run evaluation
rag-eval --config project-configs/templates/sql-evals/sql_eval_config_db.yaml

# Alternative if rag-eval is not on PATH:
python -m rag_eval_framework --config project-configs/templates/sql-evals/sql_eval_config_db.yaml
```

---

## How to Interpret Scores

### Per-Evaluator Scores

Each evaluator produces a score from 0.0 to 1.0 for every record. The **aggregate score** is the mean across all records.

| Evaluator | Good (≥) | Acceptable (≥) | Action Required (<) |
|-----------|----------|-----------------|---------------------|
| `sql_syntax_validity` | 0.95 | 0.80 | LLM producing unparseable SQL |
| `sql_safety_policy` | 1.0 | 0.90 | LLM generating unsafe operations |
| `sql_schema_validity` | 0.90 | 0.80 | LLM hallucinating tables/columns |
| `sql_semantic_judge` | 0.80 | 0.60 | LLM misunderstanding questions |
| `sql_execution_success` | 0.90 | 0.70 | Generated SQL cannot execute |
| `sql_result_match` | 0.80 | 0.60 | Results do not match expectations |

### Score of 0.0 on a Record

- **syntax** — SQL cannot be parsed. Check for typos, missing keywords.
- **safety** — Destructive operation, blocked table, or policy violation detected.
- **schema** — Hallucinated table or column name.
- **execution** — SQL error at runtime (table not found, column not found, timeout).
- **result_match** — Actual results differ from expected. Check filters, joins, aggregation.

### Threshold Gating

If a threshold is set (e.g., `sql_safety_policy: 1.0`) and the aggregate score falls below it, the evaluation report marks it as **FAIL**. Use this to gate deployments.

---

## Security Warnings

> **Generated SQL must never be executed against a production database as part of evaluation.**

DB-backed evaluators are designed exclusively for:

- Local SQLite databases
- Synthetic sample databases
- Sandbox / development databases
- Read-only database clones
- Masked development databases

**Safety measures built into DB-backed evaluators:**

1. **Blocked operations** — DROP, DELETE, UPDATE, INSERT, TRUNCATE, ALTER, MERGE, EXEC, EXECUTE, CALL are rejected before execution.
2. **Read-only connections** — SQLite databases are opened with `?mode=ro` URI parameter.
3. **Query timeouts** — Configurable timeout prevents runaway queries.
4. **Row limits** — Maximum row count prevents excessive memory usage.
5. **No credentials** — DB path is a local file. No connection strings, no passwords, no network access.

**Never:**
- Point `database_path` at a production database
- Disable the `readonly` flag on a shared database
- Set `allow_multiple_statements: true` unless strictly necessary
- Store real customer data in the sample database

---

## CI/CD Gating Guidance

Use SQL evaluators as quality gates in your CI/CD pipeline:

```yaml
# azure-pipelines.yml example
- script: |
    pip install -e ".[sql,dev]"
    python examples/sql-evaluation/create_sample_sqlite_db.py
    python -m rag_eval_framework --config project-configs/templates/sql-evals/sql_eval_config_db.yaml
  displayName: "SQL Evaluation Gate"
  failOnStderr: false
```

The CLI exits with code 1 when any threshold is breached, which will fail the pipeline step. Use thresholds in the YAML config to control the quality gate:

**Recommended thresholds for CI/CD:**

| Evaluator | Staging | Production |
|-----------|---------|------------|
| `sql_syntax_validity` | 0.80 | 0.95 |
| `sql_safety_policy` | 1.0 | 1.0 |
| `sql_schema_validity` | 0.80 | 0.90 |
| `sql_execution_success` | 0.70 | 0.85 |
| `sql_result_match` | 0.60 | 0.75 |

The `sql_safety_policy` threshold should always be `1.0` — any unsafe SQL is a blocking issue.

---

## Limitations

- **sqlglot parsing** — Covers most SQL dialects but may misparse exotic vendor-specific syntax. Use the `dialect` option to improve accuracy.
- **Column extraction** — Complex SQL (deeply nested subqueries, CTEs with aliased columns) may yield incomplete column extraction.
- **Safety evaluator** — Validates SQL structure, not runtime behaviour. Not a substitute for proper database access controls.
- **Semantic judge** — Non-deterministic. Set `temperature: 0.0` for maximum consistency.
- **DB-backed evaluators** — SQLite only. No PostgreSQL, MySQL, or other databases.
- **DB-backed safety** — DB-backed evaluators use a regex-based pre-execution safety check that is intentionally fail-closed. SQL containing blocked keywords (even inside string literals) will be rejected. This may cause false positives for queries like `WHERE name = 'DELETE record'`, which is the safe default.
- **No production connections** — DB-backed evaluators are designed for local test databases only.
- **Result comparison** — Floating-point results may require `numeric_tolerance` for approximate matching.

---

## Troubleshooting

### `ImportError: sqlglot is not installed`

Install the SQL optional dependency group:

```bash
pip install -e ".[sql]"
```

If using a virtual environment, ensure it is activated before installing.

### All evaluator scores are 0.0

1. Check that `sqlglot` is installed **in the active virtual environment**, not in user site-packages.
2. Run `python -c "import sqlglot; print(sqlglot.__version__)"` to verify.
3. Check the evaluation report for error messages in the `reason` field.

### DB-backed evaluator shows "not configured"

Ensure `evaluator_options` in the YAML config includes both `database_type` and `database_path`:

```yaml
evaluator_options:
  sql_execution_success:
    database_type: sqlite
    database_path: examples/sql-evaluation/sample_sql_eval.db
```

### Database file not found

Run the database creation script first:

```bash
python examples/sql-evaluation/create_sample_sqlite_db.py
```

The `database_path` in the config is relative to the working directory.

### Result match scores are unexpectedly low

1. Verify `expected_result` values match the actual database data by running the SQL manually.
2. Try `comparison_mode: unordered` if row order varies.
3. Increase `numeric_tolerance` for floating-point aggregations (e.g., `0.01`).

### `sql_semantic_judge` returns errors

This evaluator requires Azure OpenAI credentials. Ensure the `azure` section is configured:

```yaml
azure:
  endpoint: "https://your-endpoint.openai.azure.com"
  deployment_name: "gpt-4o-mini"
  api_version: "2024-12-01-preview"
  credential_type: default
```

---

## Future Enhancements

- PostgreSQL / MySQL dialect support for DB-backed execution
- DuckDB support as an alternative local database engine
- SQL equivalence checking (AST comparison without execution)
- Query cost / execution plan analysis
- Automatic `expected_result` generation from reference SQL
