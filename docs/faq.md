# Frequently Asked Questions

## Modes

### Which mode should I use?

| Situation                                      | Recommended Mode |
|------------------------------------------------|:----------------:|
| First time evaluating a RAG system             | Local            |
| Need maximum control over evaluators           | Local            |
| Want LLM-as-a-Judge assessment                 | Local            |
| Already using Azure AI Foundry                 | Cloud            |
| Don't want to manage Azure OpenAI credentials  | Cloud            |
| Need only groundedness/relevance/retrieval     | Either           |

See [Evaluation Modes](modes.md) for a full decision guide.

### Can I run both modes on the same dataset?

Yes.  Create two project configs — one with `mode: local` and one with
`mode: cloud` — and point them at the same dataset.  Each run produces
its own output.

### Why can't I use LLM judges in cloud mode?

Cloud mode submits your evaluation job to Azure AI Foundry, which runs
the scoring on its own infrastructure.  The framework has no way to
inject custom LLM judge prompts into that pipeline.  If you need
judge-style evaluation, use local mode.

### Why can't I use scaffold evaluators in cloud mode?

Scaffold evaluators (answer_presence, context_presence,
exact_match_accuracy) are deterministic Python functions that run
locally.  Azure AI Foundry doesn't execute custom Python code — it
only supports its own hosted evaluators.

---

## Scores and Thresholds

### Are scores comparable between modes?

**No.**  Local and cloud modes use different implementations and
different underlying models.  A `groundedness` score of 0.8 in local
mode is not equivalent to 0.8 in cloud mode.

**Do not** average or compare scores across modes.  Establish
thresholds independently for each mode.

### What is the score range?

All evaluators produce scores between **0.0** and **1.0**.

- Scaffold evaluators produce discrete values (0, 0.5, or 1).
- Azure SDK evaluators measure on a 1–5 scale and are normalised:
  `(raw - 1) / 4`.
- LLM judges also measure on 1–5 and are normalised the same way.

### How should I set thresholds?

1. Run an initial evaluation without thresholds.
2. Review the score distribution in the report.
3. Set thresholds based on the distribution — e.g. if the median
   groundedness is 0.7, a threshold of 0.65 is a reasonable
   starting point.
4. Adjust over time as your RAG system improves.

Thresholds are defined per-evaluator in the mode block:

```yaml
local_mode:
  evaluators: [groundedness, relevance]
  thresholds:
    groundedness: 0.7
    relevance: 0.6
```

### What happens when a threshold is not met?

The report marks the evaluator as failing.  In the markdown report,
failing metrics appear with a ❌ indicator.  The CLI also logs warnings.
The current framework does not exit with a non-zero code on threshold
failures (it is informational only).

---

## Dataset

### What columns does my dataset need?

At minimum, every record needs `question` and `response`.

For evaluators that check against context: `contexts` (a list of
strings).

For evaluators that check against a reference answer:
`ground_truth_answer`.

See [Metrics Catalog — Required Dataset Fields](metrics-catalog.md#required-dataset-fields)
for the full mapping.

### What formats are supported?

- **JSONL** (`.jsonl`) — recommended.  One JSON object per line.
- **CSV** (`.csv`) — supported.  The `contexts` field must be a
  JSON-encoded list.

### What happens if a record is missing a required field?

The evaluator is **skipped** for that record.  Its status is logged as
`SKIPPED` and the score counts as 0.0 in the average.  Other
evaluators that don't need the missing field still run normally.

---

## Configuration

### How do I migrate from the old flat config format?

The legacy flat format (top-level `execution_mode`, `evaluators`, `thresholds`,
`azure`, etc.) is **no longer supported**.  Unrecognised top-level fields are
rejected.  To migrate, move mode-specific fields into a `local_mode` or
`cloud_mode` block:

**Before (flat — no longer accepted):**
```yaml
execution_mode: local
evaluators:
  - answer_presence
  - groundedness
thresholds:
  groundedness: 0.7
azure:
  endpoint: https://...
```

**After (mode-separated — required):**
```yaml
mode: local
local_mode:
  evaluators:
    - answer_presence
    - groundedness
  thresholds:
    groundedness: 0.7
  azure:
    endpoint: https://...
```

### What happens if I put a cloud evaluator in `local_mode`?

Validation fails with an error listing the invalid evaluators and
showing the available ones.

### What happens if I put a judge evaluator in `cloud_mode`?

Same — validation fails immediately with a clear error message.

---

## Azure and Credentials

### How does authentication work?

By default, `credential_type: default` uses Azure
`DefaultAzureCredential`, which tries (in order):

1. Environment variables
2. Managed identity
3. Azure CLI (`az login`)
4. Visual Studio Code credentials

For most development, `az login` is sufficient.

### Do I need an Azure OpenAI resource for local mode?

Only if you use Azure SDK evaluators (tier 2) or LLM judges (tier 3).
Scaffold evaluators (tier 1) have no Azure dependency.

### What Azure AI Foundry permissions do I need for cloud mode?

Your identity needs:
- **Contributor** or **Owner** on the AI Foundry project resource
- Access to the underlying Azure OpenAI resource (if using your own
  deployments)

---

## Troubleshooting

### `ValueError: Invalid evaluators for local mode`

You have an evaluator name that doesn't exist in the local catalog.
Check spelling — common mistakes:
- `response_completeness` (correct) vs `completeness` (wrong)
- `accuracy_judge` (correct) vs `accuracy` (wrong)

### `ValueError: Invalid evaluators for cloud mode`

Cloud mode only supports 4 evaluators: `groundedness`, `relevance`,
`retrieval`, `response_completeness`.  You may have scaffold or judge
evaluators in your cloud config.

### `ModuleNotFoundError: azure.ai.evaluation`

Install the Azure extras: `pip install -e ".[azure]"`

### `ModuleNotFoundError: openai`

Install the judges extras: `pip install -e ".[judges]"`

### Scores are all 0.0

Check:
1. Dataset fields — run scaffold evaluators first to verify data.
2. Azure credentials — `az login` may have expired.
3. The model deployment — verify it's available and responsive.

### Cloud mode evaluation hangs

Azure AI Foundry evaluations are asynchronous.  The framework polls for
completion.  Long datasets (100+ records) with all 4 evaluators can
take 5–10 minutes.  Check the Foundry portal for status.

---

## Related Documentation

- [Evaluation Modes](modes.md)
- [Local Mode Guide](local-mode.md)
- [Cloud Mode Guide](cloud-mode.md)
- [Metrics Catalog](metrics-catalog.md)
- [Configuration Reference](configuration.md)
