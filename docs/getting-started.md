# Getting Started

## Prerequisites

- Python 3.10 or later
- `pip` (or a compatible package manager)

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd rag-eval-framework
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Install the package

```bash
# Install with development dependencies
pip install -e ".[dev]"
```

For Azure SDK evaluators and LLM-as-a-judge (optional):

```bash
pip install -e ".[dev,azure]"
```

For cloud evaluation via Azure AI Foundry:

```bash
pip install -e ".[dev,cloud]"
```

Or install everything:

```bash
pip install -e ".[dev,all]"
```

This additionally installs `azure-ai-evaluation`, `azure-ai-projects`, `azure-identity`, and `openai`.

## Your First Evaluation Run

The repository ships with a sample project configuration and dataset so you can verify everything works immediately.

### Run the sample evaluation

```bash
python -m rag_eval_framework --config project-configs/sample-rag.yaml
```

Or using the longer module path:

```bash
python -m rag_eval_framework.cli.run --config project-configs/sample-rag.yaml
```

Or via the installed CLI command:

```bash
rag-eval --config project-configs/sample-rag.yaml
```

### What happens

1. The config file at `project-configs/sample-rag.yaml` is loaded and validated.
2. The dataset at `datasets/sample/eval.jsonl` is loaded and validated.
3. Three scaffold evaluators run against every record:
   - `answer_presence` — checks the response is non-trivial
   - `context_presence` — checks that context passages were provided
   - `exact_match_accuracy` — checks if the ground-truth answer appears in the response
4. Aggregate scores are computed and checked against thresholds.
5. Reports are written to the `output/sample-rag/` directory:
   - `eval-report-sample-rag.json` — machine-readable
   - `eval-report-sample-rag.md` — human-readable

### Running with Azure evaluators

If you have Azure credentials configured, you can use the Phase 2 sample config:

```bash
rag-eval --config project-configs/sample-rag-phase2.yaml
```

This config includes Azure SDK evaluators (groundedness, relevance) and LLM judges. See [Configuration](configuration.md) for setting up the `azure` and `judge` sections.

### Running in cloud mode

To submit evaluations to Azure AI Foundry instead of running locally:

```bash
rag-eval --config project-configs/sample-rag-cloud.yaml
```

Or override the mode on any config:

```bash
rag-eval --config project-configs/sample-rag-phase2.yaml --mode cloud
```

Cloud mode requires:
- The `[cloud]` optional dependency: `pip install -e ".[cloud]"`
- A `foundry` section in the config with subscription, resource group, and project name
- Azure credentials configured (DefaultAzureCredential, API key, or connection string)

See [Configuration](configuration.md#foundry-configuration-foundry-section) for full details.

### Check the output

```bash
cat output/sample-rag/eval-report-sample-rag.md
```

## Onboarding Your Own Project

See [Configuration](configuration.md) and [Datasets](datasets.md) for the full reference.

### Quick steps

1. **Copy the template config**

   ```bash
   cp project-configs/templates/project-template.yaml project-configs/my-project.yaml
   ```

2. **Edit the config** — set `project_name`, `dataset_path`, `evaluators`, and `thresholds`.

3. **Create a dataset** — prepare a `.jsonl` file matching the schema described in [Datasets](datasets.md).

4. **Run**

   ```bash
   rag-eval --config project-configs/my-project.yaml
   ```

## Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov
```

## Next Steps

- [Evaluation Modes](modes.md) — local vs. cloud mode comparison
- [Configuration reference](configuration.md)
- [Dataset format](datasets.md)
- [Metrics Catalog](metrics-catalog.md) — all 11 evaluators in detail
- [Report contents](reporting.md)
- [FAQ](faq.md) — common questions
