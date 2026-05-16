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

Copy the template and run:

```bash
cp project-configs/templates/rag-eval/project-template.yaml my-sample.yaml
# Edit my-sample.yaml — set project_name and dataset_path
python -m rag_eval_framework --config my-sample.yaml
```

Or using the longer module path:

```bash
python -m rag_eval_framework.cli.run --config my-sample.yaml
```

Or via the installed CLI command:

```bash
rag-eval --config my-sample.yaml
```

### What happens

1. The config file is loaded and validated.
2. The dataset at `datasets/rag-evaluation/eval.jsonl` is loaded and validated.
3. Three scaffold evaluators run against every record:
   - `answer_presence` — checks the response is non-trivial
   - `context_presence` — checks that context passages were provided
   - `exact_match_accuracy` — checks if the ground-truth answer appears in the response
4. Aggregate scores are computed and checked against thresholds.
5. Reports are written to the `output/sample-rag/` directory:
   - `eval-report-sample-rag.json` — machine-readable
   - `eval-report-sample-rag.md` — human-readable

### Running with Azure evaluators

If you have Azure credentials configured, add Azure SDK evaluators and LLM judges to your config:

```yaml
local_mode:
  evaluators:
    - answer_presence
    - groundedness
    - relevance
    - accuracy_judge
```

Then run:

```bash
rag-eval --config my-config.yaml
```

See [Configuration](configuration.md) for setting up the `azure` and `judge` sections.

### Running with SQL evaluators

For text-to-SQL evaluation, use the SQL config template:

```bash
cp project-configs/templates/sql-evals/sql_eval_config.yaml my-sql-eval.yaml
# Edit my-sql-eval.yaml — set project_name and dataset_path
rag-eval --config my-sql-eval.yaml
```

SQL evaluators require `pip install -e ".[sql]"` and a JSONL dataset
with SQL-specific fields (see [Datasets](datasets.md)).

### Running in cloud mode

To submit evaluations to Azure AI Foundry instead of running locally, set `mode: cloud` in your config or override on the command line:

```bash
rag-eval --config my-config.yaml --mode cloud
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
   cp project-configs/templates/rag-eval/project-template.yaml my-project.yaml
   ```

2. **Edit the config** — set `project_name`, `dataset_path`, `evaluators`, and `thresholds`.

3. **Create a dataset** — prepare a `.jsonl` file matching the schema described in [Datasets](datasets.md).

4. **Run**

   ```bash
   rag-eval --config my-project.yaml
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
- [Metrics Catalog](metrics-catalog.md) — all 17 evaluators in detail (11 RAG + 6 SQL)
- [Report contents](reporting.md)
- [FAQ](faq.md) — common questions
