# Configuration Reference

## Overview

Each RAG project is configured through a YAML file placed in the `project-configs/` directory. The configuration drives every aspect of an evaluation run: which dataset to load, which evaluators to run, what thresholds to enforce, whether to run locally or in the cloud, and where to write reports.

## Full Example — Local Mode

```yaml
project_name: hr-rag
dataset_path: datasets/hr-rag/eval.jsonl
mode: local

local_mode:
  evaluators:
    - answer_presence
    - context_presence
    - exact_match_accuracy
    # Azure SDK evaluators (require azure section)
    - groundedness
    - relevance
    - retrieval
    - response_completeness
    # LLM-as-a-judge (require azure + judge sections)
    - accuracy_judge
    - hallucination_judge
    - citation_judge
    - policy_compliance_judge
  thresholds:
    answer_presence: 0.90
    context_presence: 0.80
    exact_match_accuracy: 0.70
    groundedness: 0.70

  azure:
    endpoint: https://your-resource.openai.azure.com
    deployment_name: gpt-4
    api_version: "2024-12-01-preview"
    credential_type: default
  judge:
    model: gpt-4.1
    temperature: 0.0
    max_tokens: 1024
  evaluator_options:
    groundedness:
      model: gpt-4
    accuracy_judge:
      temperature: 0.0
      max_tokens: 512

report_format:
  - json
  - markdown
  - html

output_dir: output

metadata:
  team: hr-platform
  environment: staging
```

## Full Example — Cloud Mode

```yaml
project_name: hr-rag-cloud
dataset_path: datasets/hr-rag/eval.jsonl
mode: cloud

cloud_mode:
  evaluators:
    - groundedness
    - relevance
    - retrieval
    - response_completeness
  thresholds:
    groundedness: 0.80
    relevance: 0.75

  azure:
    endpoint: https://your-resource.openai.azure.com
    deployment_name: gpt-4
    credential_type: default
  foundry:
    endpoint: https://my-foundry-project.eastus.api.azureml.ms
    subscription_id: "00000000-0000-0000-0000-000000000000"
    resource_group: rg-ai-eval
    project_name: my-foundry-project
    credential_type: default
    poll_interval_seconds: 10
    poll_timeout_seconds: 1800

report_format:
  - json
  - markdown
  - html

output_dir: output

metadata:
  team: hr-platform
  environment: staging
```

## Field Reference

### Core Fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `project_name` | string | Yes | — | Unique name for this project. Used in report filenames and directories. |
| `dataset_path` | string | Yes | — | Path to the JSONL evaluation dataset (relative to repo root). |
| `mode` | string | No | `local` | Execution mode: `local` or `cloud`. See [Evaluation Modes](modes.md). |
| `local_mode` | object | No | — | Local mode configuration block. See below. |
| `cloud_mode` | object | No | — | Cloud mode configuration block. See below. |
| `report_format` | list[string] | No | `[json, markdown]` | Report output formats. Supported: `json`, `markdown`, `html`. |
| `output_dir` | string | No | `output` | Base directory for report output. Reports go into `{output_dir}/{project_name}/`. |
| `metadata` | dict | No | `{}` | Arbitrary key-value metadata included in reports. |

### Mode Configuration Blocks

**`local_mode`** — Used when `mode: local`

| Field | Type | Required | Description |
|---|---|---|---|
| `evaluators` | list[string] | Yes | Evaluator names from the local catalog (11 available). |
| `thresholds` | dict[string, float] | No | Minimum scores per evaluator (0.0–1.0). |
| `azure` | object | No | Azure OpenAI connection settings. See below. |
| `judge` | object | No | LLM-as-a-judge settings. See below. |
| `judge_model` | string | No | Shorthand judge deployment name (default: `gpt-4.1`). |
| `evaluator_options` | dict | No | Per-evaluator option overrides. See below. |

**`cloud_mode`** — Used when `mode: cloud`

| Field | Type | Required | Description |
|---|---|---|
| `evaluators` | list[string] | Yes | Evaluator names from the cloud catalog (4 available). |
| `thresholds` | dict[string, float] | No | Minimum scores per evaluator (0.0–1.0). |
| `azure` | object | No | Azure OpenAI connection settings. See below. |
| `foundry` | object | No | Azure AI Foundry project settings. See below. |

Available evaluators per mode are validated against the built-in catalogs.
See [Metrics Catalog](metrics-catalog.md) for the full list.

### Azure Configuration (`azure` section)

Nested inside `local_mode` or `cloud_mode`. Required for Azure SDK evaluators and LLM judges.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `endpoint` | string | Yes | — | Azure OpenAI resource endpoint URL. |
| `deployment_name` | string | No | `""` | Default model deployment name for Azure evaluators. |
| `api_version` | string | No | `2024-12-01-preview` | Azure OpenAI API version. |
| `credential_type` | string | No | `default` | Authentication: `default` (DefaultAzureCredential) or `key` (API key). |
| `api_key_env` | string | No | `AZURE_OPENAI_API_KEY` | Environment variable containing the API key when `credential_type: key`. |

### Foundry Configuration (`foundry` section)

Nested inside `cloud_mode`. Required when `mode: cloud`. Specifies the Azure AI Foundry project used for cloud evaluation.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `endpoint` | string | Yes | `""` | Azure AI Foundry project endpoint URL (from portal Settings → Overview). |
| `subscription_id` | string | Yes | `""` | Azure subscription ID. |
| `resource_group` | string | Yes | `""` | Resource group containing the AI Foundry project. |
| `project_name` | string | Yes | `""` | Azure AI Foundry project name. |
| `credential_type` | string | No | `default` | Authentication: `default`, `key`, or `env`. |
| `connection_string_env` | string | No | `AZURE_AI_PROJECT_CONNECTION_STRING` | Environment variable for the project connection string (when `credential_type: env`). |
| `poll_interval_seconds` | int | No | `10` | Polling interval for cloud run status (1–300). |
| `poll_timeout_seconds` | int | No | `1800` | Maximum wait time for cloud run completion (≥30). |

### Judge Configuration (`judge` section)

Nested inside `local_mode`. Settings for LLM-as-a-judge evaluators.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `model` | string | No | `""` | Model deployment name (overrides `judge_model`). |
| `temperature` | float | No | `0.0` | LLM temperature (0.0–2.0). |
| `max_tokens` | int | No | `1024` | Maximum response tokens. |
| `azure_endpoint` | string | No | `""` | Override endpoint specifically for judges. Falls back to `azure.endpoint`. |
| `api_version` | string | No | `2024-12-01-preview` | API version override for judges. |

### Per-Evaluator Options (`evaluator_options` section)

Nested inside `local_mode`. Dict of evaluator name → key-value overrides. Allows per-evaluator customisation:

```yaml
local_mode:
  evaluators: [...]
  evaluator_options:
    groundedness:
      model: gpt-4          # override model for this evaluator
    accuracy_judge:
      temperature: 0.1
      max_tokens: 512
```

## Validation Rules

- `project_name` must be present and non-empty.
- `evaluators` must contain at least one non-empty string.
- `report_format` values must be one of: `json`, `markdown`, `html`.
- `thresholds` values must be between `0.0` and `1.0` inclusive.
- `azure.credential_type` must be `default`, `key`, or `env`.
- `foundry.credential_type` must be `default`, `key`, or `env`.
- `foundry.poll_interval_seconds` must be between `1` and `300`.
- `foundry.poll_timeout_seconds` must be `≥30`.
- `mode` must be `local` or `cloud`.
- `local_mode.evaluators` must only contain names from the local catalog.
- `cloud_mode.evaluators` must only contain names from the cloud catalog.
- `judge.temperature` must be between `0.0` and `2.0`.
- **Unrecognised fields are rejected** — the config model uses `extra="forbid"`, so any unknown keys in the YAML file will produce a clear validation error.

> See [Evaluation Modes](modes.md) for full details on mode separation
> and the [FAQ](faq.md) for common configuration questions.

## Templates

A starter template is available at `project-configs/templates/project-template.yaml`. Copy and customise it for your project.

## CLI Override

The `--output` CLI flag overrides the `output_dir` field, and `--mode` overrides `mode`:

```bash
# Override output directory
rag-eval --config project-configs/hr-rag.yaml --output /tmp/eval-output

# Override execution mode
rag-eval --config project-configs/hr-rag.yaml --mode cloud
```

## Threshold Behaviour

When a threshold is defined for an evaluator, the framework computes the **mean score** across all records (excluding SKIPPED results) and compares it to the threshold. If the mean falls below the threshold, the run is marked as **FAILED** and the CLI exits with code 3.

**Per-record pass/fail**: Each record is also marked pass/fail individually based on whether all its evaluator scores meet the configured thresholds. Records with SKIPPED evaluators are not failed for those evaluators.

Evaluators without a threshold are still scored and reported but do not affect the pass/fail outcome.

## Model Resolution

The judge model is resolved in priority order:

1. `judge.model` (from the `judge` section)
2. `judge_model` (top-level field)
3. `azure.deployment_name` (fallback)

Similarly, the judge endpoint resolves:

1. `judge.azure_endpoint`
2. `azure.endpoint`
