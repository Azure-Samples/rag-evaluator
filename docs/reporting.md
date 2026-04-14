# Reporting

## Overview

After an evaluation run completes, the framework generates reports in the formats specified in the project config. Reports are written to `{output_dir}/{project_name}/`.

## Supported Formats

| Format | Status | Output File |
|---|---|---|
| JSON | Available | `eval-report-{project_name}.json` |
| Markdown | Available | `eval-report-{project_name}.md` |
| HTML | Available | `eval-report-{project_name}.html` |

## Report Contents

All three formats include:

### Mode Banner

A prominent section identifying the evaluation mode (LOCAL or CLOUD)
with a brief description of what that mode provides.  This ensures
readers always know how the scores were produced.

### Metric Descriptions

After the evaluator summary table, each report includes a section
listing the description of every evaluator that was used.  Descriptions
are drawn from the evaluator catalogs in `config/models.py`.

### Executive Summary

- Project name
- Pass/fail status
- Runner type (local or cloud)
- Timestamp
- Dataset path
- Number of records evaluated (total, passed, failed)
- List of evaluators used

### Dataset Statistics

- Total records
- Passed records
- Failed records
- Skipped evaluator/record pairs

### Evaluator Summary

Aggregate (mean) score per evaluator with threshold status:
- Evaluator name
- Mean score
- Threshold (if configured)
- Pass/fail status

### Threshold Breaches

For each evaluator where the aggregate score fell below the configured threshold:
- Evaluator name
- Threshold value
- Actual score
- Delta (how far below)

### Threshold Results

Structured pass/fail result for every configured threshold (available in JSON output):
- Evaluator name
- Threshold
- Actual score
- Passed (boolean)

### Failed Records

Records where at least one evaluator scored below 0.5. Shows:
- Record ID
- Evaluator name
- Score
- Reason

The Markdown and HTML reports show up to 10–20 sample failed records. The JSON report includes all records.

### Run Metadata

Arbitrary metadata from the config (e.g., team, environment) plus:
- `elapsed_seconds` — total run time
- `config_reference` — path to the configuration file
- `cloud_run_id` — Azure AI Foundry run identifier (cloud mode only)
- `evaluation_mode` — `local` or `cloud`

## JSON Report Structure

```json
{
  "evaluation_mode": "local",
  "evaluator_descriptions": {
    "answer_presence": "Checks response is non-empty (deterministic).",
    "context_presence": "Checks at least one context passage was retrieved (deterministic).",
    "exact_match_accuracy": "Checks ground-truth answer appears in response (deterministic)."
  },
  "project_name": "sample-rag",
  "timestamp": "2026-03-30T12:00:00+00:00",
  "dataset_path": "datasets/sample/eval.jsonl",
  "total_records": 10,
  "evaluators_used": ["answer_presence", "context_presence", "exact_match_accuracy"],
  "aggregate_scores": {
    "answer_presence": 1.0,
    "context_presence": 0.9,
    "exact_match_accuracy": 0.85
  },
  "threshold_breaches": [],
  "threshold_results": [
    {"evaluator": "answer_presence", "threshold": 0.9, "actual": 1.0, "passed": true}
  ],
  "passed": true,
  "record_results": [
    {
      "record_id": "case-001",
      "passed": true,
      "evaluator_results": {
        "answer_presence": {"score": 1.0, "reason": "...", "status": "success"},
        "context_presence": {"score": 1.0, "reason": "...", "status": "success"},
        "exact_match_accuracy": {"score": 1.0, "reason": "...", "status": "success"}
      }
    }
  ],
  "run_metadata": {
    "elapsed_seconds": 0.042,
    "team": "platform-ai",
    "environment": "development"
  },
  "skipped_evaluators": {},
  "config_reference": "project-configs/sample-rag.yaml"
}
```

## Markdown Report Example

The Markdown report is designed for human review. It includes:

- A header with pass/fail status
- Dataset statistics section
- An evaluator summary table with score, threshold, and pass/fail status
- A table of threshold breaches (if any)
- A bullet list of sample failed records
- Skipped evaluator/record pairs (if any)
- Run metadata and config reference

## HTML Report

The HTML report is a self-contained file with inline CSS (no external dependencies). It includes all the same sections as the Markdown report with color-coded pass/fail indicators.

## Output Directory

Reports are written to `{output_dir}/{project_name}/`. The directory is created automatically if it does not exist.

The output directory can be overridden via CLI:

```bash
rag-eval --config project-configs/sample-rag.yaml --output /tmp/reports
```

## Future Enhancements

- **Trend comparison** across multiple runs
- **Application Insights / Log Analytics export** for production monitoring
- **Power BI integration** for leadership dashboards
- **Interactive HTML** with filtering and sorting
