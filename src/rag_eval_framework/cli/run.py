"""CLI command: run a local or cloud evaluation.

Usage
-----
    python -m rag_eval_framework.cli.run --config project-configs/sample-rag.yaml
    rag-eval --config project-configs/sample-rag.yaml
"""

from __future__ import annotations

import logging
import sys

import click

from rag_eval_framework.config.loader import ConfigLoadError, load_config
from rag_eval_framework.reports.engine import ReportEngine
from rag_eval_framework.runners.base import BaseRunner
from rag_eval_framework.runners.local import LocalRunner


def _build_runner(mode: str) -> BaseRunner:
    """Return the appropriate runner for the configured execution mode."""
    if mode == "cloud":
        from rag_eval_framework.runners.cloud import FoundryRunner

        return FoundryRunner()
    return LocalRunner()


def _print_mode_banner(mode: str) -> None:
    """Print a prominent mode banner so operators know which mode is active."""
    click.echo()
    click.echo("=" * 60)
    if mode == "local":
        click.echo("  EVALUATION MODE: LOCAL")
        click.echo("  Evaluators run in-process (scaffold + Azure SDK + LLM judges)")
    else:
        click.echo("  EVALUATION MODE: CLOUD (Azure AI Foundry)")
        click.echo("  Evaluators run remotely via Azure AI Evaluation SDK")
    click.echo("=" * 60)
    click.echo()


@click.command("run")
@click.option(
    "--config",
    "config_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to the project YAML configuration file.",
)
@click.option(
    "--output",
    "output_dir",
    default=None,
    type=click.Path(),
    help="Override the output directory defined in the config.",
)
@click.option(
    "--mode",
    "mode_override",
    default=None,
    type=click.Choice(["local", "cloud"], case_sensitive=False),
    help="Override the execution mode (local or cloud).",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable debug-level logging.",
)
def main(
    config_path: str,
    output_dir: str | None,
    mode_override: str | None,
    verbose: bool,
) -> None:
    """Run a RAG evaluation using the specified project config."""
    _setup_logging(verbose)
    logger = logging.getLogger(__name__)

    # 1. Load config
    try:
        config = load_config(config_path)
    except ConfigLoadError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    if output_dir:
        config = config.model_copy(update={"output_dir": output_dir})
    if mode_override:
        config = config.model_copy(update={"mode": mode_override})

    mode = config.mode

    _print_mode_banner(mode)

    click.echo(f"Project : {config.project_name}")
    click.echo(f"Mode    : {config.mode_display}")
    click.echo(f"Dataset : {config.dataset_path}")
    click.echo(f"Evaluators: {', '.join(config.evaluators)}")
    click.echo()

    # 2. Run evaluation
    runner = _build_runner(mode)
    try:
        result = runner.run(config)
    except Exception as exc:
        logger.exception("Evaluation run failed")
        click.echo(f"ERROR: Evaluation failed — {exc}", err=True)
        sys.exit(2)

    # 3. Generate reports
    engine = ReportEngine()
    report_paths = engine.generate(config, result)

    # 4. Summary
    click.echo()
    click.echo("=" * 60)
    status = "PASSED" if result.passed else "FAILED"
    click.echo(f"Result: {status}")
    click.echo(f"Runner: {result.runner_type}")
    click.echo(f"Records: {result.total_records}")
    click.echo()

    # Evaluator table
    click.echo(f"  {'Evaluator':30s} {'Score':>8s}  {'Threshold':>9s}  Status")
    click.echo(f"  {'-' * 30} {'-' * 8}  {'-' * 9}  {'-' * 6}")
    for name, score in sorted(result.aggregate_scores.items()):
        thr = config.thresholds.get(name)
        if thr is not None:
            marker = "PASS" if score >= thr else "FAIL"
            click.echo(f"  {name:30s} {score:8.4f}  {thr:9.2f}  {marker}")
        else:
            click.echo(f"  {name:30s} {score:8.4f}  {'—':>9s}  —")

    if result.threshold_breaches:
        click.echo()
        click.echo("Threshold breaches:")
        for breach in result.threshold_breaches:
            click.echo(f"  {breach.evaluator}: {breach.actual:.4f} < {breach.threshold:.4f}")

    # Cloud run metadata
    cloud_run_id = result.run_metadata.get("cloud_run_id")
    if cloud_run_id:
        click.echo()
        click.echo(f"Cloud run ID: {cloud_run_id}")

    # Skipped record summary
    skipped_count = sum(
        1
        for rr in result.record_results
        for er in rr.evaluator_results.values()
        if er.status.value == "skipped"
    )
    if skipped_count:
        click.echo()
        click.echo(f"Skipped evaluator/record pairs: {skipped_count}")

    click.echo()
    click.echo("Reports:")
    for p in report_paths:
        click.echo(f"  {p}")

    if not result.passed:
        sys.exit(3)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


if __name__ == "__main__":
    main()
