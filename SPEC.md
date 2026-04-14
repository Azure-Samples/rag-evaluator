# SPEC.md — Multi-Project RAG Evaluation Framework for Azure AI Foundry

## 1. Executive Summary

This repository provides a **reusable, enterprise-grade evaluation framework** for Retrieval-Augmented Generation (RAG) systems built on **Azure AI Foundry**.

The framework is designed to support **multiple independent RAG projects** through a shared, modular, and configuration-driven architecture.

Its primary purpose is to evaluate and report on the quality, reliability, and accuracy of RAG systems using:

* **Azure AI Evaluation SDK**
* **Azure AI Foundry project-based cloud evaluation**
* **LLM-as-a-judge**
* **built-in RAG evaluators**
* **custom business evaluators**

The framework must be reusable across internal teams and projects with minimal onboarding effort.

A new project must be onboarded by:

1. adding a project configuration file
2. providing an evaluation dataset
3. defining optional custom evaluators

without modifying framework core code.

---

## 2. Goals

The framework must provide:

### 2.1 Multi-project support

Support multiple RAG applications from a single shared framework.

### 2.2 Repeatable evaluation

Provide deterministic, repeatable evaluation runs for:

* development
* regression testing
* release validation
* production drift analysis

### 2.3 Config-driven architecture

Project-specific behavior must be externalized into configuration files.

### 2.4 Azure-native integration

Integrate with:

* Azure AI Evaluation SDK
* Azure AI Foundry project evaluation
* Azure OpenAI deployments
* optional Application Insights / Log Analytics export

### 2.5 Human-readable reporting

Generate reports suitable for:

* engineering teams
* product owners
* leadership reviews
* release gates

---

## 3. Non-Goals

This framework is **not**:

* a RAG application itself
* a document ingestion pipeline
* a vector store framework
* a prompt orchestration framework
* an experiment management platform

The framework evaluates outputs from RAG systems but does not own the generation workflow.

---

## 4. Target Users

Primary users:

* AI Engineers
* Applied AI Architects
* Platform Engineers
* MLOps / LLMOps Engineers
* QA / Validation teams

Secondary users:

* Product managers
* Technical leads
* Governance teams

---

## 5. High-Level Architecture

```text
+----------------------------------------------------+
|            Shared Evaluation Framework             |
|                                                    |
|  +----------------------------------------------+  |
|  | Core Framework                               |  |
|  | - config loader                              |  |
|  | - dataset validation                         |  |
|  | - evaluator registry                         |  |
|  | - local runner                               |  |
|  | - cloud runner                               |  |
|  | - reporting engine                           |  |
|  +----------------------------------------------+  |
|                                                    |
|  +----------------------------------------------+  |
|  | Project Configurations                       |  |
|  | - hr-rag.yaml                                |  |
|  | - legal-rag.yaml                             |  |
|  | - security-rag.yaml                          |  |
|  +----------------------------------------------+  |
|                                                    |
|  +----------------------------------------------+  |
|  | Evaluation Datasets                          |  |
|  +----------------------------------------------+  |
+----------------------------------------------------+
```

---

## 6. Repository Structure

```text
rag-eval-framework/
│
├── SPEC.md
├── README.md
├── pyproject.toml
│
├── src/rag_eval_framework/
│   ├── config/
│   ├── datasets/
│   ├── evaluators/
│   ├── runners/
│   ├── reports/
│   ├── cli/
│   └── utils/
│
├── project-configs/
│   ├── sample-rag.yaml
│   └── templates/
│
├── datasets/
│   └── sample/
│
├── docs/
│   ├── architecture.md
│   ├── getting-started.md
│   ├── configuration.md
│   ├── evaluators.md
│   └── reporting.md
│
├── tests/
│
└── .github/workflows/
```

---

## 7. Functional Requirements

---

### FR-1 Configuration Management

The framework must load project-specific YAML configuration files.

Example:

```yaml
project_name: hr-rag
dataset_path: datasets/hr-rag/eval.jsonl
mode: local

local_mode:
  evaluators:
    - groundedness
    - relevance
    - retrieval
    - accuracy_judge
  judge_model: gpt-4.1

report_format:
  - json
  - markdown
```

Required fields:

* project_name
* dataset_path
* evaluator list
* judge model
* thresholds
* output directory

---

### FR-2 Dataset Loader and Validation

The framework must support JSONL datasets.

Each record must follow this schema:

```json
{
  "id": "case-001",
  "question": "What is the retention period?",
  "response": "The retention period is 90 days.",
  "contexts": [
    "Policy states retention is 90 days."
  ],
  "ground_truth_answer": "90 days",
  "metadata": {
    "scenario": "policy_qa"
  }
}
```

Validation rules:

* required fields must exist
* empty responses must fail validation
* malformed records must be reported
* schema violations must be surfaced clearly

---

### FR-3 Evaluator Registry

The framework must implement a pluggable evaluator registry.

Example:

```python
registry.register("groundedness", GroundednessEvaluator)
registry.register("accuracy_judge", AccuracyJudgeEvaluator)
```

Evaluators must be dynamically loaded from config.

---

### FR-4 Built-in Evaluator Support

Must support wrappers for:

* groundedness
* relevance
* retrieval quality
* completeness
* similarity
* latency
* token usage

These must align with Azure AI Evaluation SDK concepts.

---

### FR-5 LLM-as-a-Judge

The framework must support custom LLM-based judging.

Mandatory supported use cases:

* answer accuracy
* hallucination detection
* citation verification
* answer completeness
* policy compliance

Judge output schema:

```json
{
  "score": 0.92,
  "reason": "Answer fully supported by retrieved evidence"
}
```

---

### FR-6 Local Evaluation Runner

Must support local execution for development.

CLI example:

```bash
python -m rag_eval_framework.cli.run \
  --config project-configs/hr-rag.yaml
```

Responsibilities:

* load config
* load dataset
* run evaluators
* generate report

---

### FR-7 Cloud Evaluation Runner

Must support Azure AI Foundry cloud evaluation.

This must be abstracted behind an adapter.

Example:

```python
CloudEvaluationRunner.run(project_config)
```

Cloud runner responsibilities:

* submit evaluation run
* retrieve results
* normalize output
* store report artifacts

---

### FR-8 Report Generation

Required report formats:

* JSON
* Markdown

Optional:

* HTML

Required sections:

* executive summary
* metric summary
* failures
* threshold breaches
* sample failed cases
* trend comparison

---

### FR-9 Threshold Validation

Must support pass/fail thresholds.

Example:

```yaml
local_mode:
  thresholds:
    groundedness: 0.85
    accuracy_judge: 0.90
```

Threshold breaches must fail pipeline execution.

---

### FR-10 CI/CD Integration

Framework must support CI execution.

Example workflow use cases:

* pull request validation
* release gates
* nightly regression evaluation

---

## 8. Non-Functional Requirements

---

### NFR-1 Maintainability

* modular design
* clean interfaces
* small cohesive modules

---

### NFR-2 Extensibility

Adding new evaluator must not require core framework modification.

---

### NFR-3 Type Safety

All public modules must use type hints.

---

### NFR-4 Testability

Core modules must be unit-testable.

Minimum coverage targets:

* config loader
* dataset validator
* evaluator registry
* report generation

---

### NFR-5 Observability

Framework must log:

* run metadata
* errors
* execution time
* evaluator timings

---

## 9. Core Modules

---

### Config Module

Responsibilities:

* YAML parsing
* validation
* defaults
* schema enforcement

---

### Dataset Module

Responsibilities:

* load JSONL
* validate schema
* normalize records

---

### Evaluator Module

Responsibilities:

* base evaluator interface
* registry
* built-in wrappers
* custom evaluators

---

### Runner Module

Responsibilities:

* orchestration
* local runner
* cloud runner

---

### Reporting Module

Responsibilities:

* aggregate scores
* render outputs
* export artifacts

---

## 10. Base Interfaces

Example evaluator interface:

```python
class BaseEvaluator(Protocol):
    def evaluate(self, record: dict) -> dict:
        ...
```

Example runner interface:

```python
class BaseRunner(Protocol):
    def run(self, config: ProjectConfig) -> EvaluationResult:
        ...
```

---

## 11. Documentation Requirements

Mandatory docs:

* getting started
* architecture
* configuration
* onboarding a new project
* writing custom evaluators
* CI integration

---

## 12. Acceptance Criteria

The first release is complete when:

* config loads successfully
* sample dataset validates
* at least 3 evaluators work
* local runner works
* markdown + JSON report generated
* unit tests pass
* documentation complete

---

## 13. Implementation Phases

### Phase 1

* repo structure
* config loader
* dataset loader
* local runner
* reporting

### Phase 2

* Azure built-in evaluators
* LLM judge
* threshold enforcement

### Phase 3

* cloud evaluation runner
* CI/CD integration
* trend analysis

### Phase 4

* dashboard integration
* historical reporting
* drift monitoring

---

## 14. Future Enhancements

* Power BI export
* historical trend store
* experiment comparison
* benchmark suites
* evaluator marketplace
* automatic dataset sampling
* production telemetry evaluation

```
```
