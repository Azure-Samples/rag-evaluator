# Dataset Format

## Overview

Evaluation datasets are stored as **JSONL** (JSON Lines) files — one JSON object per line. Each record represents a single test case that will be scored by every evaluator listed in the project config.

## Record Schema

```json
{
  "id": "case-001",
  "question": "What is the retention period?",
  "response": "The retention period is 90 days.",
  "contexts": [
    "Policy states retention is 90 days."
  ],
  "ground_truth_answer": "90 days",
  "retrieved_documents": [
    {"content": "Policy states retention is 90 days.", "score": 0.95}
  ],
  "ground_truth_documents": ["policy-doc-001"],
  "metadata": {
    "scenario": "policy_qa"
  }
}
```

### Field Reference

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | string | Yes | — | Unique identifier for the test case. |
| `question` | string | Yes | — | The user question / query. Must not be empty. |
| `response` | string | Yes | — | The RAG system's generated response. Must not be empty. |
| `contexts` | list[string] | No | `[]` | Retrieved context passages used to generate the response. |
| `ground_truth_answer` | string | No | `""` | Expected correct answer for comparison evaluators. |
| `retrieved_documents` | list[dict] | No | `[]` | Structured retrieved document objects (each with at least a `content` key). |
| `ground_truth_documents` | list[string] | No | `[]` | Expected document identifiers for retrieval quality evaluation. |
| `metadata` | dict | No | `{}` | Arbitrary metadata for filtering or grouping (e.g., scenario, category, policy). |

### Convenience Helpers

The `EvaluationRecord` model provides helper methods:

- `has_contexts()` — returns `True` if at least one non-empty context is present
- `has_ground_truth()` — returns `True` if a non-empty ground-truth answer is present

## Validation Rules

The framework validates every record before evaluation begins:

- **`id`** must be present.
- **`question`** must be present and non-empty (after trimming whitespace).
- **`response`** must be present and non-empty (after trimming whitespace).
- Records that fail validation are reported with the record ID and field-level error messages.

### Strict vs. non-strict mode

| Mode | Behaviour |
|---|---|
| **Strict** (default) | Any invalid record causes the entire load to fail. |
| **Non-strict** | Invalid records are skipped with a warning; valid records are still evaluated. |

The CLI uses strict mode. Non-strict mode is available programmatically:

```python
from rag_eval_framework.datasets import load_dataset
records = load_dataset("datasets/my-project/eval.jsonl", strict=False)
```

## Preparing a Dataset

### Option A — Manual

1. Export question–response pairs from your RAG system.
2. Enrich each record with:
   - Retrieved `contexts` (for groundedness / retrieval evaluators)
   - `ground_truth_answer` (for accuracy evaluators)
3. Save as a `.jsonl` file with one JSON object per line.
4. Place it under `datasets/<project-name>/eval.jsonl`.

### Option B — Automated collection script

Use `scripts/collect_rag_data.py` to query your RAG API and generate the JSONL automatically.

**1. Prepare a CSV** with your test questions:

```csv
id,question,ground_truth_answer,metadata_scenario
q-001,What is the retention period?,90 days,policy_qa
q-002,How do I request time off?,Submit a form 5 days in advance,process_qa
```

**2. Run the collector** (using the built-in HTTP adapter):

```bash
python scripts/collect_rag_data.py \
    --questions datasets/my-project/questions.csv \
    --output datasets/my-project/eval.jsonl \
    --adapter http \
    --rag-url http://localhost:8000/api/chat
```

**3. Run the evaluation**:

```bash
rag-eval --config project-configs/my-project.yaml
```

#### Adapters

| Adapter | Description |
|---|---|
| `http` | Generic REST adapter — POSTs `{"question": ...}` and reads `response` + `contexts` from the JSON reply. |
| `azure_agent` | Placeholder for Azure AI Foundry Agent API. Subclass and implement `query()`. |

Custom adapters can be added by subclassing `RagAdapter` in the script and registering in `ADAPTER_REGISTRY`.

See `scripts/collect_rag_data.py --help` for all options (API key, field mapping, timeout, rate-limit delay).

A sample questions file is at `datasets/sample/questions.csv`.

### Manual creation script

```python
import json

records = [
    {
        "id": "case-001",
        "question": "What is the return policy?",
        "response": "You can return items within 30 days.",
        "contexts": ["Return policy: items may be returned within 30 days of purchase."],
        "ground_truth_answer": "30 days",
        "metadata": {"category": "returns"},
    },
    # ... more records
]

with open("datasets/my-project/eval.jsonl", "w") as f:
    for r in records:
        f.write(json.dumps(r) + "\n")
```

## Sample Dataset

A sample dataset is provided at `datasets/sample/eval.jsonl` with 10 records covering HR policy, IT support, and benefits questions.
