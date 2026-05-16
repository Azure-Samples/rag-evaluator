# SQL Evaluators — Customer Walkthrough

> A hands-on guide to understanding, configuring, and running the SQL evaluation pipeline.

---

## Table of Contents

1. [What Problem Do SQL Evaluators Solve?](#1-what-problem-do-sql-evaluators-solve)
2. [How Standard RAG Evaluation Falls Short for SQL](#2-how-standard-rag-evaluation-falls-short-for-sql)
3. [The Six SQL Evaluators at a Glance](#3-the-six-sql-evaluators-at-a-glance)
4. [Architecture: Two Tiers of Evaluation](#4-architecture-two-tiers-of-evaluation)
5. [Deep Dive: Dataset-Only Evaluators](#5-deep-dive-dataset-only-evaluators)
   - 5.1 [sql_syntax_validity](#51-sql_syntax_validity)
   - 5.2 [sql_safety_policy](#52-sql_safety_policy)
   - 5.3 [sql_schema_validity](#53-sql_schema_validity)
   - 5.4 [sql_semantic_judge](#54-sql_semantic_judge)
6. [Deep Dive: DB-Backed Evaluators](#6-deep-dive-db-backed-evaluators)
   - 6.1 [sql_execution_success](#61-sql_execution_success)
   - 6.2 [sql_result_match](#62-sql_result_match)
7. [Understanding the Evaluation Dataset Format](#7-understanding-the-evaluation-dataset-format)
   - 7.1 [Core Fields](#71-core-fields)
   - 7.2 [SQL-Specific Fields](#72-sql-specific-fields)
   - 7.3 [Policy Flags](#73-policy-flags)
   - 7.4 [Example: Dataset-Only Record](#74-example-dataset-only-record)
   - 7.5 [Example: DB-Backed Record](#75-example-db-backed-record)
8. [Configuration Guide](#8-configuration-guide)
   - 8.1 [Minimal Dataset-Only Config](#81-minimal-dataset-only-config)
   - 8.2 [Full DB-Backed Config](#82-full-db-backed-config)
   - 8.3 [Evaluator Options Reference](#83-evaluator-options-reference)
   - 8.4 [Threshold Configuration](#84-threshold-configuration)
9. [Hands-On: Running Your First SQL Evaluation](#9-hands-on-running-your-first-sql-evaluation)
   - 9.1 [Prerequisites](#91-prerequisites)
   - 9.2 [Step 1: Dataset-Only Evaluation](#92-step-1-dataset-only-evaluation)
   - 9.3 [Step 2: Create the Sample Database](#93-step-2-create-the-sample-database)
   - 9.4 [Step 3: DB-Backed Evaluation](#94-step-3-db-backed-evaluation)
   - 9.5 [Step 4: Inspect the Reports](#95-step-4-inspect-the-reports)
10. [Understanding the Report Output](#10-understanding-the-report-output)
    - 10.1 [Aggregate Scores](#101-aggregate-scores)
    - 10.2 [Per-Record Results](#102-per-record-results)
    - 10.3 [How to Read Failure Reasons](#103-how-to-read-failure-reasons)
11. [The Sample SQLite Database](#11-the-sample-sqlite-database)
    - 11.1 [Schema](#111-schema)
    - 11.2 [Data Profile](#112-data-profile)
    - 11.3 [Regenerating the Database](#113-regenerating-the-database)
12. [How Each Evaluator Scores: Decision Logic Walkthrough](#12-how-each-evaluator-scores-decision-logic-walkthrough)
13. [Integrating SQL Evaluation into CI/CD](#13-integrating-sql-evaluation-into-cicd)
14. [Security Model](#14-security-model)
15. [Frequently Asked Questions](#15-frequently-asked-questions)
16. [Limitations and Roadmap](#16-limitations-and-roadmap)

---

## 1. What Problem Do SQL Evaluators Solve?

Many AI applications use LLMs to generate SQL from natural-language questions — text-to-SQL chatbots, analytics copilots, data exploration tools. Before deploying these systems, teams need to answer:

- **Is the SQL even valid?** Can it be parsed?
- **Is it safe?** Does it accidentally `DROP`, `DELETE`, or access sensitive tables?
- **Is it honest?** Does it use real tables and columns, or hallucinate schema objects?
- **Does it answer the question?** Does `GROUP BY region` actually mean "by region"?
- **Does it produce correct results?** If we run it, do we get the right numbers?

The SQL evaluators answer all five questions with automated, repeatable checks.

---

## 2. How Standard RAG Evaluation Falls Short for SQL

Standard RAG evaluators (groundedness, relevance, completeness) were designed for natural-language responses. They treat the response as prose and assess it semantically. But SQL is **structured code** — a response like:

```sql
SELECT region, SUM(amount) FROM sales WHERE date > '2025-01-01' GROUP BY region
```

…cannot be meaningfully evaluated with text similarity. You need to check that:

| Concern | RAG Evaluator | SQL Evaluator |
|---------|--------------|---------------|
| Is the response well-formed? | Checks grammar/fluency | Parses SQL syntax via sqlglot |
| Is it safe? | Policy tone/content | Blocks DROP/DELETE/UPDATE operations |
| Does it use real data sources? | Checks context grounding | Validates tables/columns against schema |
| Is it correct? | Semantic similarity | Executes SQL and compares result sets |

The SQL evaluators complement (not replace) standard RAG evaluators. For mixed workloads that output both prose and SQL, you can use both sets.

---

## 3. The Six SQL Evaluators at a Glance

| # | Name | Type | Needs DB? | Needs Azure OpenAI? | What It Checks |
|---|------|------|-----------|---------------------|----------------|
| 1 | `sql_syntax_validity` | Deterministic | No | No | SQL can be parsed |
| 2 | `sql_safety_policy` | Deterministic | No | No | No destructive ops, respects policies |
| 3 | `sql_schema_validity` | Deterministic | No | No | Tables and columns exist in schema |
| 4 | `sql_semantic_judge` | LLM Judge | No | **Yes** | SQL answers the user's question |
| 5 | `sql_execution_success` | DB-Backed | **Yes** | No | SQL runs without runtime errors |
| 6 | `sql_result_match` | DB-Backed | **Yes** | No | Query results match expected output |

All evaluators produce a score between **0.0** (worst) and **1.0** (best) for each test case.

---

## 4. Architecture: Two Tiers of Evaluation

```
 ┌────────────────────────────────────────────────────┐
 │                  TIER 1: Dataset-Only               │
 │  No database, no credentials, no network.           │
 │  Runs purely on the JSONL dataset.                  │
 │                                                      │
 │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
 │  │   Syntax     │ │   Safety     │ │   Schema     ││
 │  │  Validity    │ │   Policy     │ │  Validity    ││
 │  └──────────────┘ └──────────────┘ └──────────────┘│
 │                    ┌──────────────┐                  │
 │                    │  Semantic    │ (requires Azure  │
 │                    │   Judge     │  OpenAI)          │
 │                    └──────────────┘                  │
 └────────────────────────────────────────────────────┘
                         │
                         ▼
 ┌────────────────────────────────────────────────────┐
 │                  TIER 2: DB-Backed                   │
 │  Requires a configured local SQLite test database.  │
 │  Executes SQL safely (read-only, sandboxed).        │
 │                                                      │
 │  ┌──────────────┐ ┌──────────────┐                  │
 │  │  Execution   │ │   Result     │                  │
 │  │  Success     │ │   Match      │                  │
 │  └──────────────┘ └──────────────┘                  │
 └────────────────────────────────────────────────────┘
```

**Tier 1** catches structural problems: bad syntax, unsafe operations, hallucinated schema objects, semantic misunderstanding. These checks are fast, require no infrastructure, and can run anywhere.

**Tier 2** catches runtime problems: SQL that looks valid but hits a non-existent table at execution time, or returns `42000.0` instead of `45000.0`. These checks require a test database but give the highest confidence.

Teams typically start with Tier 1 and add Tier 2 once they have a representative test database.

---

## 5. Deep Dive: Dataset-Only Evaluators

### 5.1 `sql_syntax_validity`

**What it does:** Parses the SQL in the `response` field using [sqlglot](https://github.com/tobymao/sqlglot), a dialect-aware SQL parser.

**Scoring:**

| Score | Meaning |
|-------|---------|
| 1.0 | SQL parsed successfully |
| 0.0 | Parse failed, empty SQL, or blocked multi-statement |

**What it catches:**

- Typos (`SELEC`, `FORM`, `GROPU BY`)
- Missing keywords (`SELECT FROM` without column list)
- Unmatched parentheses
- Natural-language text masquerading as SQL
- Multiple statements when not explicitly allowed

**What it does NOT catch:**

- Valid SQL that uses wrong tables (that's `sql_schema_validity`)
- Valid SQL that is unsafe (that's `sql_safety_policy`)
- Valid SQL that answers the wrong question (that's `sql_semantic_judge`)

**Configuration options:**

| Option | Default | Description |
|--------|---------|-------------|
| `dialect` | auto-detect | SQL dialect: `sqlite`, `mysql`, `postgres`, `tsql`, etc. |
| `allow_multi_statement` | `false` | Allow `;`-separated statements |

**Example — passes (score 1.0):**
```sql
SELECT r.region_name, SUM(s.amount) AS total_sales
FROM sales s JOIN regions r ON s.region_id = r.region_id
WHERE s.sale_date >= '2025-01-01'
GROUP BY r.region_name;
```

**Example — fails (score 0.0):**
```sql
SELEC * FORM products;
```
Reason: `SQL parsing failed: Expected expression...`

---

### 5.2 `sql_safety_policy`

**What it does:** Checks SQL against a configurable set of safety rules. Uses sqlglot's AST (abstract syntax tree) for reliable detection, with regex fallback for operations sqlglot doesn't model (like `EXEC`).

**Scoring:**

| Score | Meaning |
|-------|---------|
| 1.0 | All safety checks passed |
| 0.0 | One or more violations detected |

**Checks performed (in order):**

1. **Parse check** — Can the SQL be parsed? If not, score 0.0 (fail-closed).
2. **Blocked operations** — Is the SQL a `DROP`, `DELETE`, `UPDATE`, `INSERT`, `TRUNCATE`, `ALTER`, `MERGE`, `EXEC`, `EXECUTE`, or `CALL`?
3. **Multi-statement** — Does the SQL contain multiple statements when `allow_multiple_statements` is `false`?
4. **Blocked tables** — Does the SQL reference any table in the `blocked_tables` list?
5. **Allowed tables** — If `allowed_tables` is provided, does the SQL only reference tables in that list?
6. **SELECT \*** — If `policy.allow_select_star` is `false`, does the SQL use `SELECT *`?
7. **LIMIT clause** — If `policy.require_limit` is `true`, does the SQL have a `LIMIT` or `TOP` clause?
8. **Tenant filter** — If `policy.require_tenant_filter` is `true`, does the SQL's `WHERE` clause reference the `tenant_column`?

**Key design principle: fail-closed.** If the evaluator cannot confidently determine that the SQL is safe (e.g., it can't parse it), it returns 0.0. This means false positives are possible, but unsafe SQL never slips through.

**Example — passes (score 1.0):**
```sql
SELECT region_name, SUM(amount) FROM sales GROUP BY region_name;
```

**Example — fails (score 0.0):**
```sql
DROP TABLE users;
```
Reason: `Safety violations: blocked_operation: DROP.`

**Example — policy violation (score 0.0):**
```sql
SELECT * FROM sales;
```
With policy `{"allow_select_star": false}`:
Reason: `Safety violations: select_star: SELECT * is not allowed.`

---

### 5.3 `sql_schema_validity`

**What it does:** Extracts the tables and columns referenced in the SQL and validates them against the `allowed_tables` and `allowed_columns` fields in the dataset record. Resolves table aliases (e.g., `sales s` → `s.amount` maps to `sales.amount`).

**Scoring:**

| Score | Meaning |
|-------|---------|
| 1.0 | All tables and columns are valid |
| 0.5 | Tables are valid but no `allowed_columns` provided (partial validation) |
| 0.0 | Hallucinated table or column detected |
| 1.0 (SKIPPED) | No schema metadata in the record — nothing to validate |

**What it catches:**

- Hallucinated table names (table does not exist in the schema)
- Hallucinated column names (column does not exist in the referenced table)
- Incorrect table aliases resolving to invalid columns

**Example — passes (score 1.0):**
```sql
SELECT s.region_id, SUM(s.amount) FROM sales s GROUP BY s.region_id;
```
With `allowed_tables: ["sales"]` and `allowed_columns: {"sales": ["region_id", "amount"]}`.

**Example — fails (score 0.0):**
```sql
SELECT product_name, SUM(amount) FROM product_sales GROUP BY product_name;
```
Reason: `SQL references unknown table(s): product_sales.`
The table `product_sales` doesn't exist — the real tables are `products` and `sales`.

**Example — hallucinated column (score 0.0):**
```sql
SELECT region_id, amount, profit_margin FROM sales;
```
Reason: `SQL references unknown column(s): sales.profit_margin.`

---

### 5.4 `sql_semantic_judge`

**What it does:** Sends the SQL, the user question, schema context, and expected behavior to an Azure OpenAI model (e.g., GPT-4o) and asks it to judge whether the SQL correctly answers the question.

**Requires:** Azure OpenAI credentials (endpoint + deployment).

**Scoring:** Direct 0.0–1.0 scale from the LLM:

| Score Range | Meaning |
|-------------|---------|
| 0.8–1.0 | SQL correctly and completely answers the question |
| 0.5–0.7 | Partially correct — minor issues (wrong filter, missing column) |
| 0.2–0.4 | Weakly related — major structural issues |
| 0.0–0.1 | Incorrect or unsafe |

**What it catches that other evaluators miss:**

- Wrong date range (`WHERE date < '2025-02-01'` instead of `< '2025-04-01'` for Q1)
- Missing aggregation (`SELECT amount` instead of `SELECT SUM(amount)`)
- Wrong `GROUP BY` (`GROUP BY region_id` when the question asks "by customer")
- Incorrect join condition (`JOIN ON region_id` instead of `ON customer_id`)
- Business logic errors (correct SQL that answers the wrong question)

**Example — semantic issue the judge catches:**

Question: *"Show total sales by region for Q1 2025."*
```sql
SELECT region_id, SUM(amount) FROM sales
WHERE sale_date >= '2025-01-01' AND sale_date < '2025-02-01'
GROUP BY region_id;
```
The evaluator would score this ~0.4 because the date range only covers January, not the full Q1.

---

## 6. Deep Dive: DB-Backed Evaluators

### 6.1 `sql_execution_success`

**What it does:** Executes the SQL against a configured local SQLite test database and checks whether it completes without errors. It does **not** check whether the results are correct — only that the SQL runs.

**Safety measures (always active, cannot be disabled):**

1. Destructive operations (DROP, DELETE, etc.) are **blocked before execution** via regex pre-check
2. Database is opened in **read-only mode** (`?mode=ro`)
3. Query has a configurable **timeout** (default 5 seconds)
4. Results are capped at a configurable **row limit** (default 1000)
5. No database configuration = evaluator returns ERROR, not a false pass

**Scoring:**

| Score | Meaning |
|-------|---------|
| 1.0 | SQL executed successfully |
| 0.0 | Execution failed (syntax error at runtime, missing table/column, timeout, unsafe SQL) |
| 0.0 (ERROR) | Evaluator not configured (missing `database_type` or `database_path`) |

**What it catches beyond `sql_syntax_validity`:**

Syntax validity only checks that SQL *parses*. Execution success checks that it *runs*. The difference:

```sql
-- Passes syntax check, fails execution (no such table in DB)
SELECT * FROM customer_orders;

-- Passes syntax check, fails execution (no such column in DB)
SELECT fake_column FROM sales;
```

**Configuration (required):**

```yaml
evaluator_options:
  sql_execution_success:
    database_type: sqlite                                    # Required
    database_path: examples/sql-evaluation/sample_sql_eval.db  # Required
    readonly: true                                            # Default: true
    timeout_seconds: 5.0                                     # Default: 5.0
    max_rows: 1000                                           # Default: 1000
```

---

### 6.2 `sql_result_match`

**What it does:** Executes the SQL, then compares the actual result set to the `expected_result` field in the dataset record. This is the strongest check: it verifies that the query returns the right data.

**Scoring:**

| Score | Meaning |
|-------|---------|
| 1.0 | Actual results match expected results |
| 0.5 | Partial match (subset mode: all expected rows found, but extra rows present) |
| 0.0 | Mismatch, execution failure, or unsafe SQL |
| 0.0 (SKIPPED) | No `expected_result` in the record |

**Three comparison modes:**

| Mode | Behaviour | Best For |
|------|-----------|----------|
| `exact` | Rows must match in exact order and values | Queries with `ORDER BY` |
| `unordered` | Same rows required, any order | `GROUP BY` queries, set results |
| `subset` | All expected rows must be in actual (extra rows OK) | Top-N queries, partial checks |

**Numeric tolerance:**

Floating-point aggregations can produce slightly different values depending on execution order. Set `numeric_tolerance` to allow small differences:

```yaml
evaluator_options:
  sql_result_match:
    comparison_mode: unordered
    numeric_tolerance: 0.01    # Allow ±0.01 difference
```

**Example — match (score 1.0):**

Query: `SELECT region_name, SUM(amount) AS total FROM sales GROUP BY region_name`

Expected:
```json
[
  {"region_name": "East", "total": 45000.0},
  {"region_name": "North", "total": 15000.0}
]
```

Actual (returned by database):
```json
[
  {"region_name": "North", "total": 15000.0},
  {"region_name": "East", "total": 45000.0}
]
```

With `comparison_mode: unordered` → score 1.0 (same rows, different order).

**Example — mismatch (score 0.0):**

Expected `total_sales: 45000.0`, actual `total_sales: 27000.0` — the query used the wrong date range.

---

## 7. Understanding the Evaluation Dataset Format

Each test case is a single line in a `.jsonl` file (JSON Lines). The framework loads records into an `EvaluationRecord` model.

### 7.1 Core Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier for the test case |
| `question` | Yes | The natural-language question asked by the user |
| `response` | Yes | The LLM-generated SQL query being evaluated |

### 7.2 SQL-Specific Fields

| Field | Required | Used By | Description |
|-------|----------|---------|-------------|
| `schema_context` | No | `sql_semantic_judge` | Human-readable schema description |
| `expected_sql` | No | `sql_semantic_judge` | Reference SQL for comparison |
| `expected_behavior` | No | `sql_semantic_judge` | What the SQL should do |
| `expected_result` | No | `sql_result_match` | Expected query results (list of row dicts) |
| `allowed_tables` | No | `sql_safety_policy`, `sql_schema_validity` | Tables the SQL may reference |
| `blocked_tables` | No | `sql_safety_policy` | Tables the SQL must NOT reference |
| `allowed_columns` | No | `sql_schema_validity` | Per-table column allowlists |
| `blocked_operations` | No | `sql_safety_policy` | Forbidden operations |
| `policy` | No | `sql_safety_policy` | Safety policy flags |

All SQL-specific fields are **optional**. If omitted, the relevant evaluator either skips the check or uses secure defaults.

### 7.3 Policy Flags

The `policy` object controls safety evaluator behavior per test case:

| Flag | Default | Description |
|------|---------|-------------|
| `readonly_only` | `false` | Block all mutating operations |
| `require_limit` | `false` | Require LIMIT / TOP clause |
| `require_tenant_filter` | `false` | Require WHERE filter on tenant column |
| `tenant_column` | `tenant_id` | Column name for tenant filter |
| `allow_select_star` | `true` | Allow `SELECT *` |
| `allow_multiple_statements` | `false` | Allow `;`-separated statements |

### 7.4 Example: Dataset-Only Record

```json
{
  "id": "sql_001",
  "question": "Show total sales by region for Q1 2025.",
  "response": "SELECT r.region_name, SUM(s.amount) AS total_sales FROM sales s JOIN regions r ON s.region_id = r.region_id WHERE s.sale_date >= '2025-01-01' AND s.sale_date < '2025-04-01' GROUP BY r.region_name;",
  "schema_context": "Tables: sales(region_id, amount, sale_date), regions(region_id, region_name)",
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
    "allow_select_star": false
  }
}
```

### 7.5 Example: DB-Backed Record

```json
{
  "id": "sql_db_001",
  "question": "Show total sales by region for Q1 2025.",
  "response": "SELECT r.region_name, SUM(s.amount) AS total_sales FROM sales s JOIN regions r ON s.region_id = r.region_id WHERE s.sale_date >= '2025-01-01' AND s.sale_date < '2025-04-01' GROUP BY r.region_name ORDER BY r.region_name;",
  "expected_result": [
    {"region_name": "East", "total_sales": 45000.0},
    {"region_name": "North", "total_sales": 15000.0},
    {"region_name": "South", "total_sales": 30000.0},
    {"region_name": "West", "total_sales": 30000.0}
  ],
  "allowed_tables": ["sales", "regions"],
  "blocked_operations": ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER"],
  "policy": {"readonly_only": true}
}
```

The key addition is `expected_result` — the exact rows the query should return. These values are pre-computed from the sample database.

---

## 8. Configuration Guide

SQL evaluators are configured through a standard YAML project config file.

### 8.1 Minimal Dataset-Only Config

This is the simplest configuration — no database, no Azure credentials:

```yaml
project_name: my-sql-eval
dataset_path: path/to/my_sql_dataset.jsonl
mode: local

local_mode:
  evaluators:
    - sql_syntax_validity
    - sql_safety_policy
    - sql_schema_validity

  thresholds:
    sql_syntax_validity: 0.80
    sql_safety_policy: 1.0
    sql_schema_validity: 0.80
```

### 8.2 Full DB-Backed Config

Adds execution and result matching against a test database:

```yaml
project_name: my-sql-eval-full
dataset_path: path/to/my_sql_dataset_db.jsonl
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
    sql_syntax_validity: 0.95
    sql_safety_policy: 1.0
    sql_schema_validity: 0.90
    sql_execution_success: 0.90
    sql_result_match: 0.85

  evaluator_options:
    sql_execution_success:
      database_type: sqlite
      database_path: path/to/your_test.db
      readonly: true
      timeout_seconds: 5.0
      max_rows: 1000

    sql_result_match:
      database_type: sqlite
      database_path: path/to/your_test.db
      readonly: true
      comparison_mode: unordered
      numeric_tolerance: 0.001
```

### 8.3 Evaluator Options Reference

#### `sql_syntax_validity`

| Option | Default | Description |
|--------|---------|-------------|
| `dialect` | auto | SQL dialect for parsing |
| `allow_multi_statement` | `false` | Allow multiple statements |

#### `sql_safety_policy`

| Option | Default | Description |
|--------|---------|-------------|
| `default_blocked_operations` | (see note) | Override the default blocked operation list |
| `fail_on_parse_error` | `true` | Fail-closed when SQL can't be parsed |

> Default blocked operations: DROP, DELETE, UPDATE, INSERT, TRUNCATE, ALTER, MERGE, EXEC, EXECUTE, CALL

#### `sql_execution_success`

| Option | Default | Description |
|--------|---------|-------------|
| `database_type` | *(required)* | Database engine (`sqlite`) |
| `database_path` | *(required)* | Path to database file |
| `readonly` | `true` | Open read-only |
| `timeout_seconds` | `5.0` | Query timeout |
| `max_rows` | `1000` | Max rows to fetch |
| `allow_multiple_statements` | `false` | Allow multi-statement SQL |

#### `sql_result_match`

All options from `sql_execution_success`, plus:

| Option | Default | Description |
|--------|---------|-------------|
| `comparison_mode` | `unordered` | `exact`, `unordered`, or `subset` |
| `numeric_tolerance` | `0.0` | Absolute tolerance for numeric comparison |

### 8.4 Threshold Configuration

Thresholds define the minimum acceptable aggregate score for each evaluator. If any threshold is breached, the overall evaluation result is **FAIL** and the CLI exits with code 1.

```yaml
thresholds:
  sql_syntax_validity: 0.95   # ≥95% of SQL must parse
  sql_safety_policy: 1.0      # 100% of SQL must be safe
  sql_schema_validity: 0.90   # ≥90% must use valid schema
  sql_execution_success: 0.90 # ≥90% must execute successfully
  sql_result_match: 0.85      # ≥85% must return correct results
```

**Recommendation:** Set `sql_safety_policy` to **1.0** in all environments. Any unsafe SQL is a blocking issue.

---

## 9. Hands-On: Running Your First SQL Evaluation

### 9.1 Prerequisites

```bash
# Clone the repository
git clone https://github.com/Azure-Samples/rag-evaluator.git
cd rag-evaluator

# Install with SQL evaluator support
pip install -e ".[sql]"
```

### 9.2 Step 1: Dataset-Only Evaluation

Run the three deterministic evaluators against 22 test cases. No database needed.

```bash
python -m rag_eval_framework --config project-configs/templates/sql-evals/sql_eval_config.yaml
```

**Expected output:**

```
Project : sql-eval-dataset-only
Mode    : LOCAL
Dataset : datasets/sample/sql-evaluation/sql_eval_dataset.jsonl
Evaluators: sql_syntax_validity, sql_safety_policy, sql_schema_validity

  Evaluator                         Score  Threshold  Status
  ------------------------------ --------  ---------  ------
  sql_safety_policy                0.4545       1.00  FAIL
  sql_schema_validity              0.5909       0.80  FAIL
  sql_syntax_validity              0.9545       0.80  PASS
```

**Why the FAILs?** The dataset intentionally includes negative test cases — DROP statements, hallucinated tables, policy violations — specifically to demonstrate the evaluators catching problems. In production, you'd evaluate your LLM's actual output, where you'd expect higher scores.

### 9.3 Step 2: Create the Sample Database

```bash
python examples/sql-evaluation/create_sample_sqlite_db.py
```

Output:
```
Sample database created: .../examples/sql-evaluation/sample_sql_eval.db
  Tables: regions (4 rows), customers (6 rows), products (5 rows), sales (15 rows)
```

### 9.4 Step 3: DB-Backed Evaluation

Run all five evaluators against 23 test cases, with SQL execution and result matching.

```bash
python -m rag_eval_framework --config project-configs/templates/sql-evals/sql_eval_config_db.yaml
```

**Expected output:**

```
  Evaluator                         Score  Threshold  Status
  ------------------------------ --------  ---------  ------
  sql_execution_success            0.7391       0.70  PASS
  sql_result_match                 0.5882       0.60  FAIL
  sql_safety_policy                0.7391       1.00  FAIL
  sql_schema_validity              0.6905       0.80  FAIL
  sql_syntax_validity              1.0000       0.80  PASS
```

### 9.5 Step 4: Inspect the Reports

Reports are generated in three formats:

```
output/sql-eval-db-backed/
├── eval-report-sql-eval-db-backed.json    ← Machine-readable
├── eval-report-sql-eval-db-backed.md      ← Reviewer-friendly
└── eval-report-sql-eval-db-backed.html    ← Visual (open in browser)
```

Open the **HTML report** in a browser for the best visual overview. The **JSON report** is ideal for CI/CD integration. The **Markdown report** works well in pull request comments.

---

## 10. Understanding the Report Output

### 10.1 Aggregate Scores

The aggregate score for each evaluator is the **mean** of all per-record scores. For example, if 18 out of 22 test cases score 1.0 and 4 score 0.0, the aggregate is `18/22 = 0.818`.

### 10.2 Per-Record Results

The JSON report includes results for every record and every evaluator:

```json
{
  "record_id": "sql_dataset_only_004",
  "evaluator": "sql_safety_policy",
  "score": 0.0,
  "reason": "Safety violations: blocked_operation: DROP.",
  "status": "success",
  "metadata": {
    "violations": [{"type": "blocked_operation", "detail": "DROP"}],
    "statement_count": 1
  }
}
```

### 10.3 How to Read Failure Reasons

Every score of 0.0 comes with a `reason` field explaining **exactly** what went wrong:

| Evaluator | Example Reason |
|-----------|---------------|
| `sql_syntax_validity` | `SQL parsing failed: Expected expression, ...` |
| `sql_safety_policy` | `Safety violations: blocked_operation: DROP; blocked_table: pii_customers.` |
| `sql_schema_validity` | `SQL references unknown table(s): product_sales.` |
| `sql_execution_success` | `SQL execution failed: no such table: customer_orders` |
| `sql_result_match` | `Row count mismatch: actual=4, expected=3.` |

The `metadata` field contains structured data for programmatic analysis — violation types, table names, row counts, etc.

---

## 11. The Sample SQLite Database

### 11.1 Schema

```sql
CREATE TABLE regions (
    region_id   INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL             -- East, West, North, South
);

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,          -- Alice Corp, Bob Inc, ...
    region_id     INTEGER NOT NULL
);

CREATE TABLE products (
    product_id   INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,           -- Widget A, Gadget X, ...
    category     TEXT NOT NULL            -- Widgets, Gadgets, Services
);

CREATE TABLE sales (
    sale_id     INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id  INTEGER NOT NULL,
    region_id   INTEGER NOT NULL,
    amount      REAL NOT NULL,
    sale_date   TEXT NOT NULL,            -- YYYY-MM-DD format
    tenant_id   TEXT NOT NULL DEFAULT 'tenant_a'
);
```

### 11.2 Data Profile

| Table | Rows | Notes |
|-------|------|-------|
| `regions` | 4 | East, West, North, South |
| `customers` | 6 | Alice Corp, Bob Inc, Charlie LLC, Diana Ltd, Echo Systems, Foxtrot Co |
| `products` | 5 | Widget A, Widget B, Gadget X, Gadget Y, Service Plan |
| `sales` | 15 | Q1–Q2 2025, two tenants (tenant_a, tenant_b) |

**Key pre-computed aggregations:**

| Query | Result |
|-------|--------|
| Q1 total by region | East: 45000, West: 30000, North: 15000, South: 30000 |
| Revenue by category | Gadgets: 104000, Widgets: 85000, Services: 16000 |
| Top 3 customers | Diana Ltd: 43000, Foxtrot Co: 40000, Echo Systems: 36000 |

All values are deterministic and reproducible.

### 11.3 Regenerating the Database

```bash
python examples/sql-evaluation/create_sample_sqlite_db.py
```

The script is **idempotent** — it replaces any existing database file with identical data.

---

## 12. How Each Evaluator Scores: Decision Logic Walkthrough

Let's trace a single test case through all six evaluators.

**Test case:** *"Show total sales by region for Q1 2025."*

**Response SQL:**
```sql
SELECT r.region_name, SUM(s.amount) AS total_sales
FROM sales s JOIN regions r ON s.region_id = r.region_id
WHERE s.sale_date >= '2025-01-01' AND s.sale_date < '2025-04-01'
GROUP BY r.region_name ORDER BY r.region_name;
```

| Step | Evaluator | Logic | Score |
|------|-----------|-------|-------|
| 1 | `sql_syntax_validity` | Parse with sqlglot → 1 valid statement | **1.0** |
| 2 | `sql_safety_policy` | No blocked ops, tables are allowed, no policy violations | **1.0** |
| 3 | `sql_schema_validity` | Tables `sales`, `regions` are in `allowed_tables`; columns `region_name`, `amount`, `region_id`, `sale_date` are in `allowed_columns` | **1.0** |
| 4 | `sql_semantic_judge` | LLM confirms: correct tables, correct Q1 date range, correct SUM/GROUP BY | **~0.9** |
| 5 | `sql_execution_success` | SQL runs against sample_sql_eval.db, returns 4 rows | **1.0** |
| 6 | `sql_result_match` | Actual = Expected (East:45000, North:15000, South:30000, West:30000) | **1.0** |

Now a **failing** case: same question, but the SQL only covers January:

```sql
SELECT region_id, SUM(amount) FROM sales
WHERE sale_date >= '2025-01-01' AND sale_date < '2025-02-01'
GROUP BY region_id;
```

| Step | Evaluator | Logic | Score |
|------|-----------|-------|-------|
| 1 | `sql_syntax_validity` | Parses fine | **1.0** |
| 2 | `sql_safety_policy` | No violations | **1.0** |
| 3 | `sql_schema_validity` | Tables and columns valid | **1.0** |
| 4 | `sql_semantic_judge` | LLM detects: date range covers January only, not full Q1 | **~0.4** |
| 5 | `sql_execution_success` | Runs fine (returns data for January) | **1.0** |
| 6 | `sql_result_match` | Actual ≠ Expected (January totals ≠ Q1 totals) | **0.0** |

This illustrates the layered approach: syntax/safety/schema all pass, but the semantic judge and result match catch the real problem.

---

## 13. Integrating SQL Evaluation into CI/CD

The CLI exits with **code 0** when all thresholds pass and **code 1** when any threshold is breached. This maps directly to CI/CD pass/fail.

### Azure DevOps Pipeline Example

```yaml
- script: |
    pip install -e ".[sql]"
    python examples/sql-evaluation/create_sample_sqlite_db.py
    python -m rag_eval_framework --config path/to/your-sql-eval-config.yaml
  displayName: "SQL Quality Gate"
```

### Recommended Thresholds by Environment

| Evaluator | Development | Staging | Production |
|-----------|-------------|---------|------------|
| `sql_syntax_validity` | 0.70 | 0.85 | 0.95 |
| `sql_safety_policy` | 1.0 | 1.0 | 1.0 |
| `sql_schema_validity` | 0.70 | 0.85 | 0.90 |
| `sql_execution_success` | 0.60 | 0.80 | 0.90 |
| `sql_result_match` | 0.50 | 0.70 | 0.85 |

`sql_safety_policy` should **always** be 1.0 — any unsafe SQL is a blocking issue regardless of environment.

---

## 14. Security Model

The SQL evaluators follow a **defense-in-depth** approach:

| Layer | Protection | Implementation |
|-------|-----------|----------------|
| 1 | Pre-execution safety check | Regex-based keyword blocking (DROP, DELETE, etc.) |
| 2 | AST-based validation | sqlglot parses SQL and identifies operation types |
| 3 | Read-only database connections | SQLite opened with `?mode=ro` URI flag |
| 4 | Query timeouts | Configurable per-query timeout (default 5s) |
| 5 | Row limits | Maximum rows fetched (default 1000) |
| 6 | No credentials in code | Database path is a local file — no connection strings |
| 7 | Explicit configuration required | DB-backed evaluators return ERROR if not configured |

**Important:** DB-backed evaluators are designed for **local test databases only**. Never point `database_path` at a production, staging, or shared database. The sample database contains entirely synthetic data.

---

## 15. Frequently Asked Questions

**Q: Do I need Azure OpenAI credentials to use SQL evaluators?**
No. The three deterministic evaluators (`sql_syntax_validity`, `sql_safety_policy`, `sql_schema_validity`) and the two DB-backed evaluators (`sql_execution_success`, `sql_result_match`) require no Azure credentials. Only `sql_semantic_judge` needs Azure OpenAI.

**Q: Do I need a database to start?**
No. Start with dataset-only evaluation to get immediate value from syntax, safety, and schema checks. Add DB-backed evaluation later when you have a representative test database.

**Q: Can I use this with PostgreSQL / MySQL?**
Not yet. DB-backed evaluators currently support SQLite only. PostgreSQL and MySQL support is planned.

**Q: What happens if my dataset doesn't have `allowed_tables` or `policy` fields?**
The evaluators degrade gracefully. `sql_schema_validity` marks the record as SKIPPED (score 1.0). `sql_safety_policy` uses secure defaults (all mutating operations blocked).

**Q: Can I mix SQL and standard RAG evaluators in one config?**
Yes. SQL evaluators are registered alongside standard evaluators. You can list both in the same config:

```yaml
evaluators:
  - answer_presence
  - groundedness
  - sql_syntax_validity
  - sql_safety_policy
```

**Q: The example datasets show FAIL results. Is that expected?**
Yes. The example datasets intentionally include negative test cases (DROP statements, hallucinated tables, wrong joins) to demonstrate the evaluators catching problems. In production, you'd evaluate your LLM's actual output.

**Q: How do I create `expected_result` values for my own database?**
Run the reference SQL manually and copy the output. For the sample database, all expected values are pre-computed in `create_sample_sqlite_db.py`.

**Q: What if `sqlglot` can't parse my SQL dialect?**
Set the `dialect` option to your target dialect (e.g., `tsql`, `postgres`, `mysql`). If sqlglot still misparses, the syntax evaluator scores 0.0 (fail-closed). You can set a lower threshold to account for occasional parser limitations.

---

## 16. Limitations and Roadmap

### Current Limitations

- **SQLite only** for DB-backed execution (PostgreSQL/MySQL not yet supported)
- **sqlglot parsing** may misparse exotic vendor-specific SQL syntax
- **Column extraction** may be incomplete for deeply nested subqueries and CTEs
- **Semantic judge** is non-deterministic (scores may vary between runs)
- **Regex safety check** in DB-backed evaluators may false-positive on SQL keywords inside string literals (fail-closed by design)
- **No query plan analysis** — evaluators check correctness, not efficiency

### Planned Enhancements

- PostgreSQL / MySQL dialect support for DB-backed execution
- DuckDB as a lightweight alternative to SQLite
- SQL equivalence checking via AST comparison (without execution)
- Query cost / execution plan analysis
- Automatic `expected_result` generation from reference SQL
