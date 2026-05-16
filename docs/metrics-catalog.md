# Metrics Catalog

Complete reference for all evaluators available in the RAG Evaluation
Framework.  Each entry describes what the metric measures, how it
scores, what dataset fields it requires, and which execution modes
support it.

---

## Overview

The framework provides **17 evaluators** organized into two domains —
**RAG** (11 evaluators across three tiers) and **SQL** (6 evaluators
across two tiers):

| Domain | Tier           | Count | Dependencies          | Modes          |
|--------|----------------|:-----:|----------------------|----------------|
| RAG    | Scaffold       | 3     | None (built-in)      | Local only     |
| RAG    | Azure SDK      | 4     | azure-ai-evaluation  | Local + Cloud  |
| RAG    | LLM Judge      | 4     | openai + Azure creds | Local only     |
| SQL    | Dataset-only   | 4     | sqlglot              | Local only     |
| SQL    | DB-backed      | 2     | sqlglot + SQLite DB  | Local only     |

> **RAG vs. SQL:** RAG evaluators assess natural-language responses against
> retrieved context.  SQL evaluators assess generated SQL queries against
> schema definitions and optionally a test database.  Choose the evaluators
> that match your use case — you can even mix both in a single config.

---

## Tier 1 — Scaffold Evaluators

Deterministic, zero-dependency checks that run instantly.  These are
ideal for smoke-testing your dataset and ensuring records have the
expected structure before running more expensive evaluators.

### `answer_presence`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | Scaffold                                         |
| **Modes**         | Local                                            |
| **Required fields** | `question`, `response`                        |
| **Score range**   | 0.0 or 1.0                                      |
| **Dependencies**  | None                                             |

**What it checks:** Whether the response contains a substantive answer
(at least 2 words).

**Scoring:**
- **1.0** — Response has ≥ 2 words
- **0.0** — Response is empty or a single word

**When to use:** As a basic sanity check that the RAG system produced
an actual response (not an empty string or single-word fallback).

---

### `context_presence`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | Scaffold                                         |
| **Modes**         | Local                                            |
| **Required fields** | `question`, `response`                        |
| **Score range**   | 0.0 or 1.0                                      |
| **Dependencies**  | None                                             |

**What it checks:** Whether at least one non-empty context passage was
retrieved.

**Scoring:**
- **1.0** — At least one context passage is non-empty
- **0.0** — No contexts, or all contexts are empty/whitespace

**When to use:** As a sanity check that the retrieval pipeline returned
context documents.  A score of 0.0 means the RAG system answered without
any retrieved context.

**Note:** This evaluator checks the `contexts` field but does not list
it as a `required_field` — it handles missing contexts gracefully by
returning 0.0 instead of skipping the record.

---

### `exact_match_accuracy`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | Scaffold                                         |
| **Modes**         | Local                                            |
| **Required fields** | `question`, `response`                        |
| **Score range**   | 0.0, 0.5, or 1.0                                |
| **Dependencies**  | None                                             |

**What it checks:** Whether the ground-truth answer appears as a
substring in the response (after normalisation).

**Normalisation:** Both response and ground truth are lowercased,
punctuation is stripped, and whitespace is collapsed before comparison.

**Scoring:**
- **1.0** — Normalised ground truth is a substring of normalised response
- **0.5** — No ground truth provided (inconclusive)
- **0.0** — Ground truth not found in response

**When to use:** For fact-based Q&A where the expected answer is a
specific value (e.g. "90 days", "Section 4.2.1").  Not suitable for
open-ended questions where the answer may be phrased differently.

---

## Tier 2 — Azure AI Evaluation SDK

These evaluators use Microsoft's Azure AI Evaluation SDK to assess
response quality via hosted model-based evaluation.  They produce
scores on a 1–5 scale that are automatically normalised to 0.0–1.0.

**Prerequisites:**
- `pip install -e ".[azure]"` (or `".[all]"`)
- Azure OpenAI credentials (via `DefaultAzureCredential` or API key)
- `azure` config section with endpoint and deployment

### `groundedness`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | Azure SDK                                        |
| **Modes**         | Local, Cloud                                     |
| **Required fields** | `question`, `response`, `contexts`            |
| **Score range**   | 0.0–1.0 (normalised from 1–5)                   |
| **SDK class**     | `azure.ai.evaluation.GroundednessEvaluator`      |

**What it measures:** Whether the response is grounded in (supported by)
the provided context passages.  A grounded response only makes claims
that can be traced back to the retrieved documents.

**Score interpretation:**
- 0.75–1.00 — Response is well-grounded in context
- 0.50–0.75 — Partially grounded; some claims may lack support
- 0.00–0.50 — Significant ungrounded claims

---

### `relevance`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | Azure SDK                                        |
| **Modes**         | Local, Cloud                                     |
| **Required fields** | `question`, `response`                        |
| **Score range**   | 0.0–1.0 (normalised from 1–5)                   |
| **SDK class**     | `azure.ai.evaluation.RelevanceEvaluator`         |

**What it measures:** Whether the response is relevant to the user's
question.  A relevant response addresses the question directly without
digressions.

**Score interpretation:**
- 0.75–1.00 — Highly relevant; directly answers the question
- 0.50–0.75 — Partially relevant; some off-topic content
- 0.00–0.50 — Largely irrelevant to the question

---

### `retrieval`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | Azure SDK                                        |
| **Modes**         | Local, Cloud                                     |
| **Required fields** | `question`, `response`, `contexts`            |
| **Score range**   | 0.0–1.0 (normalised from 1–5)                   |
| **SDK class**     | `azure.ai.evaluation.RetrievalEvaluator`         |

**What it measures:** The quality of the retrieved context passages.
High retrieval scores indicate the retrieval pipeline found documents
that are useful for answering the question.

**Score interpretation:**
- 0.75–1.00 — Retrieved passages are highly relevant to the question
- 0.50–0.75 — Some relevant passages, some noise
- 0.00–0.50 — Retrieved passages are mostly irrelevant

---

### `response_completeness`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | Azure SDK                                        |
| **Modes**         | Local, Cloud                                     |
| **Required fields** | `question`, `response`, `ground_truth_answer` |
| **Score range**   | 0.0–1.0 (normalised from 1–5)                   |
| **SDK class**     | `azure.ai.evaluation.ResponseCompletenessEvaluator` |

**What it measures:** How completely the response addresses all aspects
of the question, compared to the ground-truth answer.

**Score interpretation:**
- 0.75–1.00 — Response covers all key points from ground truth
- 0.50–0.75 — Partially complete; some points missing
- 0.00–0.50 — Significant information missing

---

## Tier 3 — LLM-as-a-Judge

These evaluators call Azure OpenAI directly with carefully designed
prompts that instruct the model to evaluate the response on a 1–5
scale with a natural-language reason.  Scores are normalised to
0.0–1.0.

**Prerequisites:**
- `pip install -e ".[judges]"` (or `".[all]"`)
- Azure OpenAI credentials
- `judge` config section with model, endpoint, and temperature

### `accuracy_judge`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | LLM Judge                                        |
| **Modes**         | Local                                            |
| **Required fields** | `question`, `response`, `ground_truth_answer` |
| **Score range**   | 0.0–1.0 (normalised from 1–5)                   |
| **Judge prompt**  | Assesses factual accuracy vs. ground truth       |

**What it assesses:** Whether the response is factually accurate when
compared to the ground-truth answer.  The judge evaluates correctness
of claims, not just coverage.

**1–5 scale:**
- 5 — Perfectly accurate; all facts match ground truth
- 3 — Partially accurate; some correct and some incorrect facts
- 1 — Completely inaccurate; contradicts ground truth

---

### `hallucination_judge`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | LLM Judge                                        |
| **Modes**         | Local                                            |
| **Required fields** | `question`, `response`, `contexts`            |
| **Score range**   | 0.0–1.0 (normalised from 1–5)                   |
| **Judge prompt**  | Detects unsupported claims                       |

**What it assesses:** Whether the response contains claims that are
not supported by the provided context.  **Higher scores = fewer
hallucinations** (5 = fully supported, 1 = severe hallucination).

**1–5 scale:**
- 5 — No hallucinations; all claims supported by context
- 3 — Some claims unsupported
- 1 — Severe hallucination; most claims fabricated

---

### `citation_judge`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | LLM Judge                                        |
| **Modes**         | Local                                            |
| **Required fields** | `question`, `response`, `contexts`            |
| **Score range**   | 0.0–1.0 (normalised from 1–5)                   |
| **Judge prompt**  | Assesses evidence usage from context             |

**What it assesses:** How well the response uses evidence from the
retrieved context.  High scores indicate the response cites or
references the context material appropriately.

**1–5 scale:**
- 5 — Exemplary use of context evidence
- 3 — Some context usage but could be stronger
- 1 — No evidence usage; ignores context entirely

---

### `policy_compliance_judge`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | LLM Judge                                        |
| **Modes**         | Local                                            |
| **Required fields** | `question`, `response`                        |
| **Score range**   | 0.0–1.0 (normalised from 1–5)                   |
| **Judge prompt**  | Checks compliance with a policy document         |

**What it assesses:** Whether the response complies with a policy
document provided in the record's `metadata.policy` field.

**1–5 scale:**
- 5 — Fully compliant with all policy requirements
- 3 — Partially compliant
- 1 — Non-compliant; violates policy

**Note:** The policy text must be provided in `record.metadata.policy`.
If no policy is found, the judge uses a generic "be helpful and safe"
policy.

---

## Tier 4 — SQL Evaluators

SQL evaluators assess generated SQL queries for text-to-SQL use cases.
They are split into **dataset-only** evaluators (analyse the SQL string
without executing it) and **DB-backed** evaluators (run the SQL against
a test database).

**Prerequisites:**
- `pip install -e ".[sql]"` (or `".[all]"`) — installs `sqlglot`
- For DB-backed evaluators: a SQLite test database + `database_path` in config

> **RAG vs. SQL:** RAG evaluators score natural-language answers against
> retrieved context.  SQL evaluators score generated SQL against schema
> definitions and optionally a test database.  The two sets target
> different use cases and should not be mixed in the same dataset.

### `sql_syntax_validity`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | SQL — Dataset-only                               |
| **Modes**         | Local                                            |
| **Required fields** | `response`                                    |
| **Score range**   | 0.0 or 1.0                                      |
| **Dependencies**  | sqlglot                                          |

**What it checks:** Whether the generated SQL parses successfully.

**Scoring:**
- **1.0** — SQL parsed without errors (one or more valid statements)
- **0.0** — SQL failed to parse, is empty, or violates multi-statement policy

---

### `sql_safety_policy`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | SQL — Dataset-only                               |
| **Modes**         | Local                                            |
| **Required fields** | `response`                                    |
| **Score range**   | 0.0 or 1.0                                      |
| **Dependencies**  | sqlglot                                          |

**What it checks:** Whether the SQL complies with configurable safety
policies — e.g. read-only mode, blocked operations (DROP, DELETE, etc.),
blocked tables, required LIMIT clauses, and tenant filters.

**Scoring:**
- **1.0** — SQL complies with all configured policies
- **0.0** — One or more policy violations detected

**Configuration:**
```yaml
evaluator_options:
  sql_safety_policy:
    readonly: true
    blocked_operations: [DROP, DELETE, TRUNCATE]
    require_limit: true
```

---

### `sql_schema_validity`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | SQL — Dataset-only                               |
| **Modes**         | Local                                            |
| **Required fields** | `response`, `schema_context`                  |
| **Score range**   | 0.0 or 1.0                                      |
| **Dependencies**  | sqlglot                                          |

**What it checks:** Whether the SQL references only tables and columns
that exist in the declared schema context.

**Scoring:**
- **1.0** — All tables and columns are valid per schema
- **0.0** — Unknown table or column references found

---

### `sql_semantic_judge`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | SQL — LLM Judge                                  |
| **Modes**         | Local                                            |
| **Required fields** | `question`, `response`, `schema_context`      |
| **Score range**   | 0.0–1.0 (continuous)                             |
| **Dependencies**  | sqlglot, Azure OpenAI + `judge` config           |

**What it assesses:** Whether the generated SQL semantically answers
the user's question, given the database schema and optionally a
reference SQL query.

---

### `sql_execution_success`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | SQL — DB-backed                                  |
| **Modes**         | Local                                            |
| **Required fields** | `response`                                    |
| **Score range**   | 0.0 or 1.0                                      |
| **Dependencies**  | sqlglot, configured SQLite database              |

**What it checks:** Whether the SQL executes against a test database
without raising a runtime error.

**Scoring:**
- **1.0** — SQL executed successfully
- **0.0** — SQL raised an error at runtime

**Configuration:**
```yaml
evaluator_options:
  sql_execution_success:
    database_path: path/to/test.db
    timeout_seconds: 5
```

---

### `sql_result_match`

| Property          | Value                                            |
|-------------------|--------------------------------------------------|
| **Category**      | SQL — DB-backed                                  |
| **Modes**         | Local                                            |
| **Required fields** | `response`, `expected_result`                 |
| **Score range**   | 0.0 or 1.0                                      |
| **Dependencies**  | sqlglot, configured SQLite database              |

**What it checks:** Whether the actual query results match the expected
output provided in the dataset.

**Scoring:**
- **1.0** — Actual result set matches expected result set
- **0.0** — Results differ (row count, values, or order mismatch)

**Configuration:**
```yaml
evaluator_options:
  sql_result_match:
    database_path: path/to/test.db
    comparison_mode: exact  # or "unordered"
```

---

## Score Normalisation

All evaluators in this framework produce scores on a **0.0–1.0 scale**.

- **Scaffold evaluators** produce binary (0.0 or 1.0) or ternary
  (0.0, 0.5, 1.0) scores natively.
- **Azure SDK evaluators** produce 1–5 scores that are mapped:
  `normalised = (raw - 1) / 4`, clamped to [0.0, 1.0].
- **LLM judges** produce 1–5 scores that are mapped the same way.
- **SQL evaluators** produce binary 0.0 or 1.0 scores (except
  `sql_semantic_judge` which produces continuous 0.0–1.0).

---

## Required Dataset Fields

### RAG Evaluators

| Field               | Type       | Evaluators That Use It                    |
|--------------------|------------|-------------------------------------------|
| `question`         | string     | All RAG evaluators                        |
| `response`         | string     | All RAG evaluators                        |
| `contexts`         | list[str]  | groundedness, retrieval, hallucination_judge, citation_judge |
| `ground_truth_answer` | string  | exact_match_accuracy, response_completeness, accuracy_judge |
| `metadata.policy`  | string     | policy_compliance_judge                   |

### SQL Evaluators

| Field               | Type       | Evaluators That Use It                    |
|--------------------|------------|-------------------------------------------|
| `response`         | string     | All SQL evaluators (the generated SQL)    |
| `question`         | string     | sql_semantic_judge                        |
| `schema_context`   | string     | sql_schema_validity, sql_semantic_judge   |
| `expected_sql`     | string     | sql_semantic_judge (optional reference)   |
| `expected_result`  | list[dict] | sql_result_match                          |

**Field presence handling:**
- If a required field is missing/empty, the evaluator is **skipped**
  for that record (status = `SKIPPED`, score = 0.0).
- Scaffold evaluators like `context_presence` and `exact_match_accuracy`
  handle missing optional fields gracefully without skipping.

---

## Custom Evaluators

To add a custom evaluator:

1. Create a class inheriting from `BaseEvaluator`.
2. Implement the `name` property and `evaluate()` method.
3. Register it in `registry.py`.
4. Add the name to the appropriate catalog in `config/models.py`.

See [Contributing Guide](contributing.md) for details.

---

## Related Documentation

- [Evaluation Modes](modes.md) — local vs. cloud mode comparison
- [Local Mode Guide](local-mode.md) — local-specific setup
- [Cloud Mode Guide](cloud-mode.md) — cloud-specific setup
- [Configuration Reference](configuration.md) — all YAML fields
