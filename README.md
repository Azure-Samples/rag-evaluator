# RAG Evaluation Framework

A **reusable, config-driven evaluation framework** for Retrieval-Augmented Generation (RAG) systems, with first-class support for **Azure AI Foundry** and **Azure OpenAI**.

Evaluate any RAG application by adding a YAML config and a JSONL dataset — no core code changes required.

---

## Key Features

- **11 pluggable evaluators** across three tiers — scaffold, Azure AI Evaluation SDK, and LLM-as-a-judge
- **Local and cloud execution** — run evaluators in-process or submit batch jobs to Azure AI Foundry
- **Config-driven** — one YAML file per project; no code changes to onboard new apps
- **Strict evaluator catalogs** — mode-aware validation prevents misconfiguration
- **JSON, Markdown & HTML reports** with per-record and aggregate pass/fail
- **Threshold enforcement** — structured breach detection with CLI exit codes for CI/CD
- **Extensible** — add custom evaluators by subclassing `BaseEvaluator`

## Supported Evaluators

| Evaluator | Tier | Local | Cloud | Description |
|---|---|:---:|:---:|---|
| `answer_presence` | Scaffold | ✅ | — | Response contains a substantive answer |
| `context_presence` | Scaffold | ✅ | — | At least one non-empty context retrieved |
| `exact_match_accuracy` | Scaffold | ✅ | — | Ground truth appears in the response |
| `groundedness` | Azure SDK | ✅ | ✅ | Response grounded in provided context |
| `relevance` | Azure SDK | ✅ | ✅ | Response relevant to the question |
| `retrieval` | Azure SDK | ✅ | ✅ | Quality of retrieved context passages |
| `response_completeness` | Azure SDK | ✅ | ✅ | Response completeness vs. ground truth |
| `accuracy_judge` | LLM Judge | ✅ | — | Factual accuracy (1–5 → 0–1) |
| `hallucination_judge` | LLM Judge | ✅ | — | Claims not supported by context |
| `citation_judge` | LLM Judge | ✅ | — | Evidence usage from context |
| `policy_compliance_judge` | LLM Judge | ✅ | — | Compliance with a policy document |

## Architecture

```
Mode: local                           Mode: cloud
┌───────────────────────┐             ┌──────────────────────────┐
│  YAML Config          │             │  YAML Config             │
│  ↓                    │             │  ↓                       │
│  LocalRunner          │             │  FoundryRunner           │
│  ├─ Scaffold evals    │             │  ├─ FoundryAdapter       │
│  ├─ Azure SDK evals   │             │  │  └─ azure.ai.projects │
│  └─ LLM Judge evals   │             │  └─ Result normaliser    │
│  ↓                    │             │  ↓                       │
│  Reports (JSON/MD/HTML)│             │  Reports (JSON/MD/HTML)  │
└───────────────────────┘             └──────────────────────────┘
```

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/your-org/rag-eval-framework.git
cd rag-eval-framework

python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

pip install -e ".[dev]"
```

**Optional extras:**

```bash
pip install -e ".[azure]"    # Azure SDK evaluators (local mode)
pip install -e ".[judges]"   # LLM-as-a-judge evaluators
pip install -e ".[cloud]"    # Cloud mode (Azure AI Foundry)
pip install -e ".[all]"      # Everything
```

### 2. Run the Sample Evaluation

The included sample dataset uses only scaffold evaluators — no Azure credentials needed:

```bash
rag-eval --config project-configs/sample-rag.yaml
```

### 3. View Reports

Reports are written to `output/<project-name>/`:

```bash
cat output/sample-rag/eval-report-sample-rag.md
```

### 4. Run Tests

```bash
pytest
```

---

## Onboarding a New Project

1. Copy the template:
   ```bash
   cp project-configs/templates/project-template.yaml project-configs/my-project.yaml
   ```
2. Prepare a JSONL dataset at `datasets/my-project/eval.jsonl` (see [Datasets](docs/datasets.md))
3. Edit your config — choose evaluators, set thresholds, configure Azure credentials if needed
4. Run:
   ```bash
   rag-eval --config project-configs/my-project.yaml
   ```

See [Getting Started](docs/getting-started.md) for a detailed walkthrough.

---

## Configuration Overview

Each project is driven by a YAML config with a `mode` field and a corresponding mode block:

```yaml
# Local mode — all 11 evaluators available
project_name: my-rag
dataset_path: datasets/my-project/eval.jsonl
mode: local

local_mode:
  evaluators:
    - answer_presence
    - groundedness
    - accuracy_judge
  thresholds:
    answer_presence: 0.90
    groundedness: 0.70
  azure:
    endpoint: https://your-resource.openai.azure.com
    deployment_name: gpt-4
    credential_type: default
  judge:
    model: gpt-4.1
```

```yaml
# Cloud mode — Azure SDK evaluators via Azure AI Foundry
mode: cloud

cloud_mode:
  evaluators:
    - groundedness
    - relevance
  thresholds:
    groundedness: 0.80
  azure:
    endpoint: https://your-resource.openai.azure.com
  foundry:
    endpoint: https://your-project.services.ai.azure.com/api/projects/your-proj
    subscription_id: "00000000-0000-0000-0000-000000000000"
    resource_group: your-resource-group
    project_name: your-foundry-project
```

See [Configuration Reference](docs/configuration.md) for all fields.

---

## Repository Structure

```
rag-eval-framework/
├── pyproject.toml                     # Python project metadata and dependencies
├── README.md                          # This file
├── SPEC.md                            # Full specification and roadmap
├── .env.example                       # Environment variable template
├── .github/workflows/ci.yml           # GitHub Actions CI + eval quality gate
├── azure-pipelines.yml                # Azure DevOps CI + eval quality gate
├── src/rag_eval_framework/
│   ├── config/                        # YAML config loading and Pydantic models
│   ├── datasets/                      # Dataset loading and validation
│   ├── evaluators/
│   │   ├── builtin/                   # Scaffold evaluators (3)
│   │   ├── azure/                     # Azure SDK evaluator adapters (4)
│   │   └── judges/                    # LLM-as-a-judge evaluators (4)
│   ├── runners/
│   │   ├── local.py                   # In-process evaluation runner
│   │   ├── cloud.py                   # Azure AI Foundry runner
│   │   └── foundry/                   # Foundry SDK adapter + normaliser
│   ├── reports/                       # JSON, Markdown, HTML report generators
│   ├── cli/                           # CLI entrypoint (click-based)
│   └── utils/                         # Logging and normalisation helpers
├── project-configs/
│   ├── sample-rag.yaml                # Minimal local mode example
│   ├── sample-rag-phase2.yaml         # All evaluator tiers (local)
│   ├── sample-rag-cloud.yaml          # Cloud mode example
│   └── templates/
│       └── project-template.yaml      # Starter template for new projects
├── datasets/
│   └── sample/                        # Synthetic HR Q&A dataset (10 records)
├── scripts/
│   └── collect_rag_data.py            # Data collection utility with adapters
├── docs/                              # Full documentation
└── tests/                             # Unit tests
```

---

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | System design and module responsibilities |
| [Evaluation Modes](docs/modes.md) | Local vs. Cloud comparison and decision guide |
| [Local Mode Guide](docs/local-mode.md) | Local mode setup, all 3 evaluator tiers |
| [Cloud Mode Guide](docs/cloud-mode.md) | Cloud mode setup with Azure AI Foundry |
| [Metrics Catalog](docs/metrics-catalog.md) | All 11 evaluators — descriptions, scores, required fields |
| [Configuration Reference](docs/configuration.md) | Full YAML config field reference |
| [Datasets](docs/datasets.md) | Dataset format, fields, and validation rules |
| [Evaluators](docs/evaluators.md) | Built-in evaluators and how to create custom ones |
| [Reporting](docs/reporting.md) | Report formats, structure, and output directory |
| [Getting Started](docs/getting-started.md) | Installation and first run walkthrough |
| [FAQ](docs/faq.md) | Common questions about modes, scores, and config |
| [Contributing](docs/contributing.md) | Development workflow, testing, and guidelines |

---

## CI/CD Integration

The CLI uses structured exit codes designed for pipeline gating:

| Exit Code | Meaning | Pipeline Effect |
|---|---|---|
| `0` | All thresholds passed | **Merge allowed** |
| `1` | Config load error | Fail the job |
| `2` | Evaluation runtime error | Fail the job |
| `3` | Threshold breaches detected | **Block the merge** |

### Ready-made pipeline templates

| Platform | File | Description |
|---|---|---|
| GitHub Actions | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Tests + scaffold eval gate (+ optional Azure eval) |
| Azure DevOps | [`azure-pipelines.yml`](azure-pipelines.yml) | Tests + scaffold eval gate (+ optional Azure eval) |

Both templates include:
1. **Unit tests & lint** across Python 3.10 – 3.12
2. **Scaffold evaluation quality gate** — runs the sample config, fails on threshold breach
3. **Optional Azure SDK evaluation stage** (commented out) — uncomment and add credentials to enable

### Quick example: block a PR on quality regression

```yaml
# In your own pipeline — just call rag-eval:
- run: rag-eval --config project-configs/my-rag.yaml
  # exit 0 → merge allowed
  # exit 3 → quality regression → PR blocked
```

---

## Development

### Prerequisites

- Python ≥ 3.10
- (Optional) Azure CLI for `az login` when using Azure SDK or LLM judge evaluators

### Setup

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest                          # all tests
pytest tests/test_config.py     # specific module
pytest -x --tb=short            # fail fast with short tracebacks
```

### Lint

```bash
ruff check src/ tests/
mypy src/
```

---


## Contributing

Contributions are welcome. Please see [Contributing](docs/contributing.md) for:

- Development setup
- Code style (ruff, mypy)
- Testing requirements
- Pull request process

---

## License

This project is licensed under the [MIT License](LICENSE).
