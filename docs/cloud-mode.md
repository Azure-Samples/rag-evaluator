# Cloud Mode Guide

Cloud mode submits evaluation jobs to **Azure AI Foundry** for
server-side execution.  Only evaluators supported by the Azure AI
Evaluation SDK are available.

---

## Prerequisites

### 1. Install Cloud Dependencies

```bash
pip install -e ".[cloud]"
```

This installs `azure-ai-projects`, `azure-ai-evaluation`, and
`azure-identity`.

### 2. Azure AI Foundry Project

You need an Azure AI Foundry project.  Note the following from the
portal (Settings → Overview):

| Setting             | Where to Find                         | Example                                                    |
|---------------------|---------------------------------------|------------------------------------------------------------|
| **Endpoint**        | AI Foundry portal → Settings          | `https://my-project.services.ai.azure.com/api/projects/my-proj` |
| **Subscription ID** | Azure Portal → Subscription           | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`                     |
| **Resource Group**  | Azure Portal → Resource Group         | `rg-ai-eval`                                               |
| **Project Name**    | AI Foundry portal → project name      | `my-foundry-project`                                       |

### 3. Azure Credentials

The framework uses `DefaultAzureCredential` by default:

```bash
az login
```

Ensure your identity has the **Azure AI Developer** role (or equivalent)
on the Foundry project resource.

---

## Configuration

```yaml
project_name: my-rag-cloud
dataset_path: datasets/my-project/eval.jsonl
mode: cloud

report_format:
  - json
  - markdown
  - html
output_dir: output-cloud

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
    api_version: "2024-12-01-preview"
    credential_type: default
    # is_reasoning_model: true  # set for o-series / reasoning models

  foundry:
    endpoint: https://your-project.services.ai.azure.com/api/projects/your-proj
    subscription_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    resource_group: rg-ai-eval
    project_name: your-foundry-project
    credential_type: default
    # poll_interval_seconds: 10   # how often to check run status
    # poll_timeout_seconds: 1800  # max wait time (30 minutes)

metadata:
  team: platform-ai
  environment: cloud-eval
```

---

## Available Evaluators

Cloud mode supports exactly **4 evaluators** — all from the Azure AI
Evaluation SDK:

| Evaluator              | What It Measures                                  | Required Dataset Fields |
|------------------------|---------------------------------------------------|------------------------|
| `groundedness`         | Response grounded in provided context              | question, response, contexts |
| `relevance`            | Response relevant to the question                  | question, response     |
| `retrieval`            | Quality of retrieved context passages              | question, response, contexts |
| `response_completeness`| Response fully addresses the question vs. ground truth | question, response, ground_truth_answer |

### What Is NOT Available in Cloud Mode

The following evaluators are **local-mode only** and will be rejected
if included in a `cloud_mode` configuration:

- **Scaffold evaluators**: `answer_presence`, `context_presence`,
  `exact_match_accuracy`
- **LLM judges**: `accuracy_judge`, `hallucination_judge`,
  `citation_judge`, `policy_compliance_judge`

If you need these evaluators, use [local mode](local-mode.md).

---

## Score Normalisation

Azure AI Evaluation SDK scores use a 1–5 scale.  The framework
normalises these to 0.0–1.0 for consistency:

| SDK Score | Framework Score |
|:---------:|:---------------:|
| 1         | 0.00            |
| 2         | 0.25            |
| 3         | 0.50            |
| 4         | 0.75            |
| 5         | 1.00            |

The normaliser handles multiple key patterns returned by the Foundry
service (e.g. `groundedness`, `groundedness.groundedness`,
`groundedness.gpt_groundedness`).

---

## How It Works

1. **Connect** — The framework creates an `AIProjectClient` using your
   Foundry endpoint and credentials.

2. **Submit** — Your dataset (JSONL) and evaluator selection are sent
   to the Foundry evaluation service via `azure.ai.evaluation.evaluate()`.

3. **Wait** — The SDK's `evaluate()` call is synchronous; it returns
   when the evaluation completes.

4. **Normalise** — Raw Foundry results are normalised to framework
   models (`RecordResult`, `EvaluationRunResult`).

5. **Report** — Reports are generated just as in local mode, with a
   "CLOUD" mode banner.

---

## Foundry Configuration Reference

| Field                    | Type    | Default | Description                                    |
|--------------------------|---------|---------|------------------------------------------------|
| `endpoint`               | string  | `""`    | Foundry project endpoint URL (required)        |
| `subscription_id`        | string  | `""`    | Azure subscription ID                          |
| `resource_group`         | string  | `""`    | Resource group name                            |
| `project_name`           | string  | `""`    | Foundry project name                           |
| `credential_type`        | string  | `"default"` | `default`, `key`, or `env`                 |
| `connection_string_env`  | string  | `"AZURE_AI_PROJECT_CONNECTION_STRING"` | Env var for connection string |
| `poll_interval_seconds`  | int     | `10`    | Status polling interval (1–300)                |
| `poll_timeout_seconds`   | int     | `1800`  | Maximum wait time (≥ 30)                       |

---

## Troubleshooting

### "Azure AI Projects SDK is not installed"

```
ImportError: Azure AI Projects SDK is not installed
```

**Fix:** `pip install -e ".[cloud]"`

### "Failed to initialise cloud evaluation"

**Cause:** Usually a credential or endpoint issue.

**Steps:**
1. Verify `az login` is active: `az account show`
2. Verify the Foundry endpoint URL is correct.
3. Ensure your identity has sufficient permissions on the Foundry
   resource.

### "Evaluator 'X' is not in the cloud catalog"

**Cause:** You've included a local-only evaluator in `cloud_mode.evaluators`.

**Fix:** Only use these evaluators in cloud mode:
`groundedness`, `relevance`, `retrieval`, `response_completeness`.

### Evaluation appears to hang

The `evaluate()` call is synchronous and can take several minutes for
large datasets.  The `poll_timeout_seconds` setting controls the maximum
wait time (default: 30 minutes).

### max_tokens error

If your Azure deployment uses a reasoning model:

```yaml
cloud_mode:
  azure:
    is_reasoning_model: true
```

### Score differences between local and cloud

This is expected.  Although both modes use the Azure AI Evaluation SDK
under the hood, the execution context differs:

- **Local mode** calls SDK evaluators one record at a time in-process.
- **Cloud mode** sends the entire dataset to Foundry for batch evaluation.

Model routing, batching, and potential version differences can lead to
slight score variations.  Do not try to force metric equivalence between
modes.

---

## Related Documentation

- [Evaluation Modes](modes.md) — comparison of local vs. cloud
- [Local Mode Guide](local-mode.md) — for in-process evaluation
- [Metrics Catalog](metrics-catalog.md) — complete evaluator reference
- [Configuration Reference](configuration.md) — all YAML fields
