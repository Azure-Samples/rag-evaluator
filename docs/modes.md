# Evaluation Modes — Local vs. Cloud

The RAG Evaluation Framework supports two distinct execution modes:
**Local** and **Cloud**.  Each mode has its own evaluator catalog,
configuration block, and operational characteristics.  This document
explains why two modes exist, what each one offers, and how to choose.

---

## Why Two Modes?

RAG evaluation metrics come from different sources with different
trade-offs:

| Dimension          | Local Mode                          | Cloud Mode                          |
|--------------------|-------------------------------------|-------------------------------------|
| **Where it runs**  | In your Python process              | Azure AI Foundry service            |
| **Evaluator count**| 11 (scaffold + Azure SDK + judges)  | 4 (Azure SDK only)                  |
| **LLM judges**     | Yes — full control over prompt & model | No                                |
| **Custom scaffold** | Yes                                | No (SDK evaluators only)            |
| **Azure required** | Only for SDK/judge evaluators       | Always                              |
| **Latency**        | Depends on model call volume        | Depends on Foundry queue + compute  |
| **Cost**           | Per-token (your Azure OpenAI)       | Azure AI Evaluation pricing         |
| **Offline capable**| Yes (scaffold evaluators)           | No                                  |

> **Important:** Do not compare scores across modes for the same evaluator
> name.  Local mode uses the Azure AI Evaluation SDK *in-process* while
> cloud mode uses the Foundry *service*.  Although both rely on the same
> underlying SDK, the execution context, batching, and model routing may
> differ.  Each mode's scores are valid within their own context.

---

## Mode Selection

Set the `mode` field in your project YAML:

```yaml
mode: local   # or "cloud"
```

The mode determines which configuration block is used:

- `mode: local` → `local_mode:` block
- `mode: cloud` → `cloud_mode:` block

### CLI Override

You can override the mode from the command line:

```bash
rag-eval --config project-configs/my-project.yaml --mode cloud
```

---

## Quick Comparison

### Local Mode

```yaml
project_name: my-rag
dataset_path: datasets/my-project/eval.jsonl
mode: local

local_mode:
  evaluators:
    - answer_presence        # scaffold
    - context_presence       # scaffold
    - exact_match_accuracy   # scaffold
    - groundedness           # Azure SDK
    - relevance              # Azure SDK
    - accuracy_judge         # LLM judge
    - hallucination_judge    # LLM judge
  thresholds:
    answer_presence: 0.90
    groundedness: 0.70
  azure:
    endpoint: https://your-resource.openai.azure.com
    deployment_name: gpt-4
    credential_type: default
  judge:
    model: gpt-4.1
    temperature: 0.0
    max_tokens: 1024
```

See [Local Mode Guide](local-mode.md) for full details.

### Cloud Mode

```yaml
project_name: my-rag-cloud
dataset_path: datasets/my-project/eval.jsonl
mode: cloud

cloud_mode:
  evaluators:
    - groundedness
    - relevance
    - retrieval
    - response_completeness
  thresholds:
    groundedness: 0.80
  azure:
    endpoint: https://your-resource.openai.azure.com
    deployment_name: gpt-4
    credential_type: default
  foundry:
    endpoint: https://your-project.region.api.azureml.ms
    subscription_id: ...
    resource_group: ...
    project_name: ...
    credential_type: default
```

See [Cloud Mode Guide](cloud-mode.md) for full details.

---

## Evaluator Catalog by Mode

| Evaluator                 | Local | Cloud | Category     | Requires              |
|---------------------------|:-----:|:-----:|--------------|----------------------|
| `answer_presence`         | ✅    | —     | Scaffold     | Nothing              |
| `context_presence`        | ✅    | —     | Scaffold     | Nothing              |
| `exact_match_accuracy`    | ✅    | —     | Scaffold     | Nothing              |
| `groundedness`            | ✅    | ✅    | Azure SDK    | Azure credentials    |
| `relevance`               | ✅    | ✅    | Azure SDK    | Azure credentials    |
| `retrieval`               | ✅    | ✅    | Azure SDK    | Azure credentials    |
| `response_completeness`   | ✅    | ✅    | Azure SDK    | Azure credentials    |
| `accuracy_judge`          | ✅    | —     | LLM Judge    | Azure OpenAI         |
| `hallucination_judge`     | ✅    | —     | LLM Judge    | Azure OpenAI         |
| `citation_judge`          | ✅    | —     | LLM Judge    | Azure OpenAI         |
| `policy_compliance_judge` | ✅    | —     | LLM Judge    | Azure OpenAI         |

For detailed descriptions of each metric, see
[Metrics Catalog](metrics-catalog.md).

---

## Reports and Mode Awareness

All report formats (JSON, Markdown, HTML) include:

1. **Mode banner** — prominently displays which mode was used.
2. **Metric descriptions** — explains what each evaluator measures,
   specific to the mode.
3. **Runner type** — `local` or `cloud` clearly labelled.

This ensures that anyone reading a report understands the evaluation
context without needing to check the YAML config.

---

## Decision Guide

Use **Local Mode** when:
- You need LLM-as-a-judge evaluators (accuracy, hallucination, citation).
- You want scaffold checks (answer_presence, context_presence, exact_match).
- You want full control over the evaluation process and prompts.
- You're running offline or in a CI pipeline without Foundry access.
- You want to iterate quickly on evaluator configuration.

Use **Cloud Mode** when:
- You want Azure-managed evaluation infrastructure.
- You only need the 4 Azure SDK metrics (groundedness, relevance,
  retrieval, response_completeness).
- You want to leverage Foundry's evaluation service for scale.
- You're integrating with other Azure AI Foundry workflows.

---

## Related Documentation

- [Local Mode Guide](local-mode.md) — detailed setup and configuration
- [Cloud Mode Guide](cloud-mode.md) — Foundry setup and troubleshooting
- [Metrics Catalog](metrics-catalog.md) — complete evaluator reference
- [Configuration Reference](configuration.md) — all YAML fields
- [FAQ](faq.md) — common questions about modes
