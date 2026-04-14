# Contributing

## Development Setup

```bash
# Clone and install
git clone <repo-url>
cd rag-eval-framework
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov

# Specific test file
pytest tests/test_config.py
```

## Code Quality

### Linting

```bash
ruff check src/ tests/
```

### Formatting

```bash
ruff format src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Code Style Guidelines

- **Type hints** on all public function signatures
- **Pydantic models** for data structures at module boundaries
- **Small, focused modules** — one responsibility per file
- **Docstrings** on all public classes and functions (Google or NumPy style)
- **No hardcoded paths** — use config values or Path objects
- Prefer `from __future__ import annotations` for forward references

## Adding a New Evaluator

### Scaffold / built-in evaluator

1. Create a new file in `src/rag_eval_framework/evaluators/builtin/`
2. Subclass `BaseEvaluator` and implement `name`, `required_fields`, and `evaluate()`
3. Register it in `_create_default_registry()` in `registry.py`
4. Add tests in `tests/test_evaluators.py`
5. Document it in `docs/evaluators.md`

### Azure SDK evaluator

1. Create a new file in `src/rag_eval_framework/evaluators/azure/`
2. Subclass `AzureEvaluatorBase` from `evaluators/azure/adapter.py`
3. Override `name`, `required_fields`, `_sdk_class_path`, `_sdk_input_mapping`, and `evaluate()`
4. Register it in `_create_default_registry()` in `registry.py`
5. Add tests (mock the SDK) in `tests/test_azure_evaluators.py`

### LLM judge evaluator

1. Create a new file in `src/rag_eval_framework/evaluators/judges/`
2. Subclass `BaseLLMJudge` from `evaluators/judges/base.py`
3. Add prompt templates to `evaluators/judges/prompts.py`
4. Override `name`, `required_fields`, `system_prompt`, `user_prompt_template`
5. Register and test like other evaluators

See [Evaluators — Writing a Custom Evaluator](evaluators.md#writing-a-custom-evaluator) for a complete example.

## Adding a New Report Format

1. Create a renderer function in `src/rag_eval_framework/reports/`
2. Register it in `ReportEngine.generate()` in `engine.py`
3. Add the format name to the `report_format_must_be_supported` validator in `config/models.py`
4. Add tests in `tests/test_reports.py`
5. Document it in `docs/reporting.md`

## Pull Request Checklist

- [ ] Tests pass (`pytest`)
- [ ] Linting passes (`ruff check`)
- [ ] New code has type hints
- [ ] Public functions/classes have docstrings
- [ ] Documentation updated if needed
- [ ] No hardcoded paths or secrets

## Project Structure

See the [Architecture](architecture.md) document for a detailed description of the module layout and responsibilities.

## What's Intentionally Deferred

The following are **not** in scope for Phase 2 and should not be implemented yet:

- Cloud evaluation runner / Azure AI Foundry submission (Phase 3)
- CI/CD pipeline templates with threshold gating (Phase 3)
- Application Insights / Log Analytics export (Phase 3)
- Trend analysis and drift monitoring (Phase 4)
- Dashboard integration / Power BI (Phase 4)
- Interactive HTML with filtering/charts (Phase 4)

When contributing, keep these boundaries in mind. It's fine to create interfaces and extension points, but keep implementations focused on the current phase.
