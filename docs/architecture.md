# Architecture

## Overview

The RAG Evaluation Framework follows a modular, layered architecture where each module has a single responsibility and communicates through well-defined interfaces.

## Data Flow

```
YAML Config → Config Loader → ProjectConfig
                                ├── mode (local | cloud)
                                ├── LocalModeConfig  (evaluators, thresholds)
                                ├── CloudModeConfig  (evaluators, thresholds)
                                ├── AzureConfig
                                ├── JudgeConfig
                                ├── FoundryConfig (cloud mode)
                                └── evaluator_options
JSONL Dataset → Dataset Loader ─┐
                                 ▼
                          mode = ?
                        ┌──────┴───────┐
                        │              │
                    local          cloud
                        │              │
                  Local Runner     Foundry Runner
                       │              │
             ┌─────────┤              FoundryAdapter
             │ setup(config)  │    ├─ connect()
             │ on each eval   │    ├─ submit_evaluation()
             └─────────┤              ├─ get_results() (poll)
                       │           └─ normalise results
        ┌──────────────┼──────────────┐
        │              │               │
   Scaffold (3)  Azure SDK (4)   LLM Judges (4)
   LOCAL only    LOCAL + CLOUD   LOCAL only
   ├ answer_pres ├ groundedness  ├ accuracy
   ├ context_pres├ relevance     ├ hallucination
   └ exact_match ├ retrieval     ├ citation
                 └ completeness  └ policy_compliance
        │              │               │
        └──────────────┼──────────────┘
                       ▼
             Per-record pass/fail +
             Aggregate threshold check
                       │
                 Report Engine
            ┌──────────┼──────────┐
       JSON Report  MD Report  HTML Report
       (+ mode      (+ mode    (+ mode
        banner)      banner)    banner)
```

## Mode Separation

The framework enforces a clear separation between **local** and **cloud**
evaluation modes at the configuration level:

- Each mode has its own **evaluator catalog** defined in `config/models.py`.
- `LocalModeConfig` validates evaluators against the 11-evaluator local catalog.
- `CloudModeConfig` validates evaluators against the 4-evaluator cloud catalog.
- Cross-mode contamination (e.g. scaffold evaluators in cloud mode) is
  rejected at config validation time.
- Reports include a **mode banner** and **metric descriptions** so readers
  always know which mode produced the scores.

See [Evaluation Modes](modes.md) for the full comparison.

## Module Responsibilities

### Config (`src/rag_eval_framework/config/`)

- Parse and validate project YAML configuration files
- Provide `ProjectConfig`, `AzureConfig`, `JudgeConfig`, `FoundryConfig`, `LocalModeConfig`, `CloudModeConfig` Pydantic models
- Evaluator catalogs (`LOCAL_EVALUATOR_CATALOG`, `CLOUD_EVALUATOR_CATALOG`) enforced at validation time
- Support mode-separated `local_mode` / `cloud_mode` config blocks
- Surface clear validation errors; unknown fields rejected (`extra="forbid"`)

### Datasets (`src/rag_eval_framework/datasets/`)

- Load JSONL evaluation datasets
- Validate each record against the `EvaluationRecord` schema
- Phase 2 fields: `retrieved_documents`, `ground_truth_documents`
- Helper methods: `has_contexts()`, `has_ground_truth()`
- Report invalid rows with line numbers and field-level details

### Evaluators (`src/rag_eval_framework/evaluators/`)

- `BaseEvaluator` ABC with `required_fields` property and `setup(config)` lifecycle hook
- `EvaluatorStatus` enum: SUCCESS, SKIPPED, ERROR
- `EvaluatorResult` model with score, reason, status, metadata, raw_output
- `EvaluatorRegistry` maps names → instances (11 built-in)
- Three evaluator tiers:
  - **Built-in** (`builtin/`) — 3 lightweight deterministic evaluators
  - **Azure SDK** (`azure/`) — 4 adapters wrapping `azure-ai-evaluation` SDK classes
  - **LLM Judges** (`judges/`) — 4 prompt-based evaluators via Azure OpenAI

### Runners (`src/rag_eval_framework/runners/`)

- `BaseRunner` abstract interface with typed result models
- `LocalRunner` orchestrates evaluation in-process:
  - Calls `setup(config)` on each evaluator
  - Checks `required_fields` before `evaluate()` — skips if missing
  - Computes per-record pass/fail against thresholds
  - Aggregates scores (SKIPPED excluded from mean)
  - Builds structured `ThresholdResult` objects
- `FoundryRunner` submits evaluation jobs to Azure AI Foundry:
  - Delegates SDK interactions to `FoundryAdapter`
  - Normalises cloud results via `normaliser` module
  - Returns same `EvaluationRunResult` as local runner
- **Foundry adapter** (`runners/foundry/`):
  - `FoundryAdapter` — connect, submit, poll, retrieve results
  - `normaliser` — convert cloud metrics/rows to framework models
  - Lazy SDK imports; clear error hints when SDK missing

### Reports (`src/rag_eval_framework/reports/`)

- **JSON** — full structured output including `threshold_results`, `skipped_evaluators`
- **Markdown** — dataset statistics, evaluator summary with thresholds, failed records
- **HTML** — self-contained report with inline CSS, color-coded pass/fail
- `ReportEngine` orchestrates generation across all configured formats

### CLI (`src/rag_eval_framework/cli/`)

- `click`-based CLI with rich terminal output
- Evaluator summary table with Score, Threshold, Status columns
- `--mode` flag to override execution mode (local/cloud)
- Exit codes: 0 = PASSED, 1 = config error, 2 = runtime error, 3 = threshold breach

### Utils (`src/rag_eval_framework/utils/`)

- Shared logging helpers
- Common utility functions

## Evaluator Lifecycle

1. **Registry lookup** — runner resolves evaluator names → instances from the registry
2. **`setup(config)`** — each evaluator receives the `ProjectConfig` for lazy SDK/client initialisation
3. **Field check** — runner checks `required_fields` against the record; missing → SKIPPED
4. **`evaluate(record)`** — evaluator produces `EvaluatorResult` with score, reason, status, metadata
5. **Aggregation** — SKIPPED results excluded from mean; ERROR results scored 0.0

## Extension Points

| Extension Point | Module | Status |
|---|---|---|
| Custom evaluators | `evaluators/` | Available |
| Azure AI SDK evaluators | `evaluators/azure/` | Phase 2 (done) |
| LLM-as-a-judge evaluators | `evaluators/judges/` | Phase 2 (done) |
| HTML report renderer | `reports/` | Phase 2 (done) |
| Cloud evaluation runner (Azure AI Foundry) | `runners/cloud.py` | Phase 3A (done) |
| Foundry SDK adapter | `runners/foundry/` | Phase 3A (done) |
| Application Insights export | `reports/` | Phase 3B |
| Trend analysis and drift monitoring | `reports/` | Phase 4 |

## Design Principles

1. **Config-driven** — project-specific behaviour is externalised into YAML
2. **Pluggable** — new evaluators via subclass + registry registration
3. **Type-safe** — Pydantic models and type hints throughout
4. **Small modules** — each file has a single responsibility
5. **Testable** — 256+ tests, zero cloud dependencies required for local evaluation
6. **Strict** — unrecognised fields rejected; no hidden migration behind the scenes
7. **Mode-aware** — strict evaluator catalogs prevent cross-mode contamination
