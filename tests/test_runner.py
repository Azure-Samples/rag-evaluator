"""Tests for the local evaluation runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval_framework.config.models import ProjectConfig
from rag_eval_framework.runners.local import LocalRunner
from tests.conftest import make_config, make_record


@pytest.fixture()
def runner_config(tmp_path: Path) -> ProjectConfig:
    """Create a valid config pointing to a temp dataset."""
    dataset_path = tmp_path / "eval.jsonl"
    records = [
        make_record(id="r-001"),
        make_record(id="r-002", contexts=[], ground_truth_answer="wrong answer"),
        make_record(id="r-003", response="ok fine", ground_truth_answer="90 days"),
    ]
    lines = [json.dumps(r) for r in records]
    dataset_path.write_text("\n".join(lines), encoding="utf-8")

    data = make_config(
        dataset_path=str(dataset_path),
        output_dir=str(tmp_path / "output"),
        thresholds={"answer_presence": 0.5},
    )
    return ProjectConfig(**data)


class TestLocalRunner:
    def test_run_produces_result(self, runner_config: ProjectConfig) -> None:
        runner = LocalRunner()
        result = runner.run(runner_config)
        assert result.project_name == "test-project"
        assert result.total_records == 3
        assert len(result.record_results) == 3

    def test_aggregate_scores_present(self, runner_config: ProjectConfig) -> None:
        runner = LocalRunner()
        result = runner.run(runner_config)
        for evaluator_name in runner_config.evaluators:
            assert evaluator_name in result.aggregate_scores

    def test_threshold_pass(self, runner_config: ProjectConfig) -> None:
        runner = LocalRunner()
        result = runner.run(runner_config)
        # All records have multi-word responses → answer_presence should be 1.0,
        # which exceeds the 0.5 threshold.
        assert result.passed is True

    def test_threshold_breach_detected(self, tmp_path: Path) -> None:
        dataset_path = tmp_path / "eval.jsonl"
        # All records have empty contexts → context_presence = 0.0
        records = [
            make_record(id="r-001", contexts=[]),
            make_record(id="r-002", contexts=[]),
        ]
        dataset_path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        data = make_config(
            dataset_path=str(dataset_path),
            evaluators=["context_presence"],
            thresholds={"context_presence": 0.9},
        )
        config = ProjectConfig(**data)
        runner = LocalRunner()
        result = runner.run(config)
        assert result.passed is False
        assert len(result.threshold_breaches) == 1
        assert result.threshold_breaches[0].evaluator == "context_presence"

    def test_unknown_evaluator_raises(self) -> None:
        """Unknown evaluator is now rejected at config parse time by the catalog validator."""
        data = make_config(evaluators=["nonexistent"])
        with pytest.raises(ValidationError, match="not in the local catalog"):
            ProjectConfig(**data)
