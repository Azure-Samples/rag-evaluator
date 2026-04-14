# Evaluators

## Overview

Evaluators are the core scoring units of the framework. Each evaluator receives a single dataset record and returns a score (0.0–1.0) with an optional reason.

The evaluator system is **pluggable**: new evaluators can be added by subclassing `BaseEvaluator` and registering them in the evaluator registry, without changing any framework core code.

The framework provides **11 built-in evaluators** across three tiers:

| Tier | Count | Modes |
|---|---|---|
| Scaffold (built-in) | 3 | Local only |
| Azure SDK | 4 | Local + Cloud |
| LLM-as-a-judge | 4 | Local only |

Evaluators are validated against per-mode **catalogs** at config time.
See [Metrics Catalog](metrics-catalog.md) for detailed descriptions,
score ranges, and required fields for every evaluator.
See [Evaluation Modes](modes.md) for mode selection guidance.

## Built-in Evaluators (Phase 1)

Three **scaffold evaluators** — simple, deterministic implementations that verify the framework works end-to-end. These require no cloud access.

### `answer_presence`

Checks whether the response contains a substantive answer (at least 2 words).

| Score | Meaning |
|---|---|
| 1.0 | Response has 2+ words |
| 0.0 | Response is a single word or empty |

### `context_presence`

Checks whether at least one non-empty context passage was provided.

| Score | Meaning |
|---|---|
| 1.0 | At least one non-empty context |
| 0.0 | No contexts or all empty |

### `exact_match_accuracy`

Checks whether the normalised ground-truth answer appears in the normalised response. Normalisation includes: lower-casing, stripping punctuation, and collapsing whitespace.

| Score | Meaning |
|---|---|
| 1.0 | Ground truth found in response |
| 0.5 | No ground truth provided (indeterminate) |
| 0.0 | Ground truth not found in response |

## Azure SDK Evaluators (Phase 2)

These evaluators wrap the [Azure AI Evaluation SDK](https://learn.microsoft.com/en-us/azure/ai-studio/how-to/develop/evaluate-sdk) (`azure-ai-evaluation` package). They require an `azure` section in the project config with valid Azure OpenAI credentials.

Scores from the SDK (1–5 scale) are normalised to 0.0–1.0.

### `groundedness`

Evaluates whether the response is grounded in the provided context passages using the Azure GroundednessEvaluator.

- **Required fields**: `question`, `response`, `contexts`
- **SDK class**: `azure.ai.evaluation.GroundednessEvaluator`

### `relevance`

Evaluates whether the response is relevant to the user's question.

- **Required fields**: `question`, `response`
- **SDK class**: `azure.ai.evaluation.RelevanceEvaluator`

### `retrieval`

Evaluates the quality of the retrieved context passages for answering the question.

- **Required fields**: `question`, `response`, `contexts`
- **SDK class**: `azure.ai.evaluation.RetrievalEvaluator`

### `response_completeness`

Evaluates whether the response fully and completely answers the question compared to the ground truth.

- **Required fields**: `question`, `response`, `ground_truth_answer`
- **SDK class**: `azure.ai.evaluation.ResponseCompletenessEvaluator`

## LLM-as-a-Judge Evaluators (Phase 2)

These evaluators send structured prompts to an Azure OpenAI deployment and parse the LLM's JSON response.
They require both `azure` and `judge` sections in the project config.

Scores from the LLM (1–5 scale) are normalised to 0.0–1.0. Each response includes a human-readable `reason`.

### `accuracy_judge`

Assesses whether the response accurately answers the question compared to the ground truth.

- **Required fields**: `question`, `response`, `ground_truth_answer`

### `hallucination_judge`

Detects claims in the response that are not supported by the provided context passages.

- **Required fields**: `question`, `response`, `contexts`

### `citation_judge`

Evaluates how well the response cites and references evidence from the context passages.

- **Required fields**: `question`, `response`, `contexts`

### `policy_compliance_judge`

Checks whether the response complies with policy guidelines (from `metadata.policy` or `evaluator_options`).

- **Required fields**: `question`, `response`

## Writing a Custom Evaluator

### 1. Create the evaluator class

```python
# src/rag_eval_framework/evaluators/builtin/my_custom_eval.py

from rag_eval_framework.datasets.models import EvaluationRecord
from rag_eval_framework.evaluators.base import BaseEvaluator, EvaluatorResult


class MyCustomEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "my_custom_eval"

    @property
    def description(self) -> str:
        return "Checks a custom business rule."

    @property
    def required_fields(self) -> list[str]:
        return ["question", "response", "contexts"]

    def evaluate(self, record: EvaluationRecord) -> EvaluatorResult:
        # Your scoring logic here
        score = 1.0 if "important keyword" in record.response.lower() else 0.0
        return EvaluatorResult(
            score=score,
            reason="Keyword found." if score == 1.0 else "Keyword missing.",
        )
```

### 2. Register it

Add the registration to the `_create_default_registry()` function in `src/rag_eval_framework/evaluators/registry.py`:

```python
from rag_eval_framework.evaluators.builtin.my_custom_eval import MyCustomEvaluator

registry.register(MyCustomEvaluator)
```

### 3. Use it in a config

```yaml
local_mode:
  evaluators:
    - answer_presence
    - my_custom_eval
```

## Evaluator Interface

All evaluators implement the `BaseEvaluator` abstract base class:

```python
class BaseEvaluator(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def description(self) -> str:
        return ""

    @property
    def required_fields(self) -> list[str]:
        """Dataset fields this evaluator needs (checked by the runner)."""
        return ["question", "response"]

    def setup(self, config: Any) -> None:
        """Optional lifecycle hook for lazy initialisation (e.g. SDK clients)."""

    @abstractmethod
    def evaluate(self, record: EvaluationRecord) -> EvaluatorResult: ...
```

The return type is:

```python
class EvaluatorStatus(str, Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"

class EvaluatorResult(BaseModel):
    score: float                        # 0.0 to 1.0
    reason: str                         # human-readable explanation
    status: EvaluatorStatus             # SUCCESS, SKIPPED, or ERROR
    metadata: dict[str, Any]            # evaluator-specific metadata
    raw_output: dict[str, Any] | None   # raw SDK/LLM output
```

### Evaluator Lifecycle

1. **Registry lookup** — runner resolves evaluator name → instance
2. **`setup(config)`** — runner passes `ProjectConfig` for lazy client init
3. **Field check** — runner verifies `required_fields` against the record
4. **`evaluate(record)`** — evaluator scores the record
5. **Aggregation** — SKIPPED scores excluded from mean

## Evaluator Registry

The `EvaluatorRegistry` maps string names to evaluator classes:

```python
from rag_eval_framework.evaluators import EvaluatorRegistry, default_registry

# Check available evaluators
print(default_registry.list_evaluators())

# List evaluators for a specific mode
print(default_registry.list_for_mode("local"))   # 11 evaluators
print(default_registry.list_for_mode("cloud"))   # 4 evaluators

# Get an instance (validates against mode catalog)
evaluator = default_registry.get_for_mode("groundedness", "local")
```
