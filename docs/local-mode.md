# Local Mode Guide

Local mode runs all evaluators **in the current Python process**.  This
is the default execution mode and supports the full evaluator catalog:
scaffold checks, Azure AI Evaluation SDK evaluators, and LLM-as-a-judge
evaluators.

---

## Prerequisites

| Evaluator Tier   | Install Command                     | Azure Required? |
|------------------|-------------------------------------|:---------------:|
| Scaffold         | `pip install -e .`                  | No              |
| Azure SDK        | `pip install -e ".[azure]"`         | Yes             |
| LLM Judges       | `pip install -e ".[judges]"`        | Yes             |
| All              | `pip install -e ".[all]"`           | Yes             |

### Azure Credentials (for SDK + Judge evaluators)

The framework uses `DefaultAzureCredential` by default.  The simplest
setup:

```bash
az login
```

Alternatively, set `credential_type: key` and provide your API key via
an environment variable:

```yaml
local_mode:
  azure:
    credential_type: key
    api_key_env: AZURE_OPENAI_API_KEY
```

---

## Configuration

### Minimal (scaffold only)

```yaml
project_name: my-rag
dataset_path: datasets/my-project/eval.jsonl
mode: local

local_mode:
  evaluators:
    - answer_presence
    - context_presence
    - exact_match_accuracy
  thresholds:
    answer_presence: 0.90
```

No Azure credentials needed.  Run with:

```bash
rag-eval --config project-configs/my-project.yaml
```

### Full (all three tiers)

```yaml
project_name: my-rag-full
dataset_path: datasets/my-project/eval.jsonl
mode: local

local_mode:
  evaluators:
    # Tier 1 — Scaffold (no external dependency)
    - answer_presence
    - context_presence
    - exact_match_accuracy
    # Tier 2 — Azure AI Evaluation SDK
    - groundedness
    - relevance
    - retrieval
    - response_completeness
    # Tier 3 — LLM-as-a-Judge
    - accuracy_judge
    - hallucination_judge
    - citation_judge
    # - policy_compliance_judge  # requires 'policy' in record metadata

  thresholds:
    answer_presence: 0.90
    context_presence: 0.80
    groundedness: 0.70
    relevance: 0.70
    accuracy_judge: 0.60

  azure:
    endpoint: https://your-resource.openai.azure.com
    deployment_name: gpt-4
    api_version: "2024-12-01-preview"
    credential_type: default
    # is_reasoning_model: true  # set for o-series or reasoning models

  judge:
    model: gpt-4.1
    temperature: 0.0
    max_tokens: 1024
    azure_endpoint: https://your-resource.openai.azure.com  # optional override
    api_version: "2024-12-01-preview"

  judge_model: gpt-4.1  # shorthand (overridden by judge.model if set)
  evaluator_options: {}  # per-evaluator overrides

report_format:
  - json
  - markdown
  - html
output_dir: output

metadata:
  team: platform-ai
  environment: development
```

---

## Available Evaluators

### Tier 1 — Scaffold (Built-in)

These evaluators require no external services.  They are fast,
deterministic, and work offline.

| Evaluator              | What It Checks                                    | Score Range |
|------------------------|---------------------------------------------------|-------------|
| `answer_presence`      | Response contains ≥ 2 words                       | 0.0 or 1.0  |
| `context_presence`     | At least one non-empty context passage             | 0.0 or 1.0  |
| `exact_match_accuracy` | Ground-truth answer appears in response (normalised)| 0.0, 0.5, 1.0 |

**`exact_match_accuracy` scoring:**
- 1.0 — Ground truth found in response (case-insensitive, whitespace-normalised)
- 0.5 — No ground truth provided (inconclusive)
- 0.0 — Ground truth not found in response

### Tier 2 — Azure AI Evaluation SDK

These evaluators use the `azure-ai-evaluation` SDK to call Azure's
hosted model-based evaluation endpoints.  They produce 1–5 scores
that are normalised to 0.0–1.0.

| Evaluator              | What It Measures                                  | Required Fields     |
|------------------------|---------------------------------------------------|---------------------|
| `groundedness`         | Response grounded in provided context              | question, response, contexts |
| `relevance`            | Response relevant to the question                  | question, response  |
| `retrieval`            | Quality of retrieved context passages              | question, response, contexts |
| `response_completeness`| Response fully addresses the question vs. ground truth | question, response, ground_truth_answer |

**Score normalisation:** Azure SDK scores (1–5) → framework scores (0.0–1.0):
- 1 → 0.00, 2 → 0.25, 3 → 0.50, 4 → 0.75, 5 → 1.00

### Tier 3 — LLM-as-a-Judge

These evaluators call Azure OpenAI directly with tailored prompts that
instruct the model to act as an evaluation judge.  They produce 1–5
scores (normalised to 0.0–1.0) with a natural-language reason.

| Evaluator                | What It Assesses                                  | Required Fields     |
|--------------------------|---------------------------------------------------|---------------------|
| `accuracy_judge`         | Factual accuracy vs. ground truth                  | question, response, ground_truth_answer |
| `hallucination_judge`    | Claims not supported by context                    | question, response, contexts |
| `citation_judge`         | Evidence usage from context                        | question, response, contexts |
| `policy_compliance_judge`| Compliance with a policy document                  | question, response + metadata.policy |

---

## Thresholds

Thresholds define the minimum acceptable aggregate score for each
evaluator.  If any evaluator's aggregate score falls below its
threshold, the evaluation run **fails** (exit code 3).

```yaml
local_mode:
  thresholds:
    answer_presence: 0.90    # 90% of records must have substantive answers
    groundedness: 0.70       # average groundedness ≥ 0.70
    accuracy_judge: 0.60     # average accuracy ≥ 0.60
```

Thresholds are applied:
1. **Per record** — each record is marked pass/fail against thresholds
2. **Aggregate** — mean score per evaluator is checked against threshold

Evaluators without a threshold are reported but do not affect pass/fail.

---

## Reasoning Models

If your Azure OpenAI deployment uses a reasoning model (o-series, or
models that require `max_completion_tokens` instead of `max_tokens`),
set:

```yaml
local_mode:
  azure:
    is_reasoning_model: true
```

This flag is forwarded to both Azure SDK evaluators and LLM judge
evaluators, which will use `max_completion_tokens` instead of
`max_tokens`.

---

## Per-Evaluator Options

Override settings for individual evaluators:

```yaml
local_mode:
  evaluator_options:
    groundedness:
      model: gpt-4o          # use a different model for this evaluator
    accuracy_judge:
      temperature: 0.2       # higher temperature for judge diversity
      max_tokens: 2048        # longer responses
```

---

## Troubleshooting

### SDK evaluators return ERROR

**Symptom:** Azure SDK evaluators produce `ERROR` status with
"has not been configured" message.

**Cause:** Missing `azure` section or missing credentials.

**Fix:**
1. Ensure `local_mode.azure` is configured with endpoint + deployment.
2. Run `az login` or set `AZURE_OPENAI_API_KEY`.
3. Install: `pip install -e ".[azure]"`

### LLM judges return ERROR

**Symptom:** Judge evaluators produce `ERROR` with
"not configured" message.

**Cause:** Missing `judge` section or Azure OpenAI not reachable.

**Fix:**
1. Configure `local_mode.judge` with model and endpoint.
2. Verify `az login` credentials have access to the OpenAI resource.
3. Install: `pip install -e ".[judges]"`

### max_tokens error with reasoning models

**Symptom:** `BadRequestError: max_tokens is not supported`

**Fix:** Set `is_reasoning_model: true` in the azure configuration.

---

## Related Documentation

- [Evaluation Modes](modes.md) — comparison of local vs. cloud
- [Cloud Mode Guide](cloud-mode.md) — for Azure AI Foundry evaluation
- [Metrics Catalog](metrics-catalog.md) — complete evaluator reference
- [Configuration Reference](configuration.md) — all YAML fields
