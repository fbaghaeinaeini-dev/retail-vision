"""CLI for Module B: Run the Zone Discovery Agent pipeline.

Usage:
    python -m scripts.run_pipeline --db data/synthetic.db --video-id synthetic_v1
    python -m scripts.run_pipeline --db data/retailvision.db --video-id abc123 --openrouter-key sk-...
"""

import json
import sys
from pathlib import Path

import click
from loguru import logger

from agent.config import PipelineConfig
from agent.orchestrator import ZoneDiscoveryAgent


@click.command()
@click.option("--db", required=True, type=click.Path(), help="SQLite database path")
@click.option("--video-id", required=True, help="Video ID to process")
@click.option("--output", default="output", help="Output directory")
@click.option("--openrouter-key", envvar="OPENROUTER_API_KEY", default="", help="OpenRouter API key")
@click.option("--replicate-token", envvar="REPLICATE_API_TOKEN", default="", help="Replicate API token")
@click.option("--vlm-model", default="qwen/qwen3.5-35b-a3b", help="Primary VLM model")
@click.option("--quality-threshold", default=0.40, type=float, help="Quality gate threshold")
@click.option("--no-vlm", is_flag=True, help="Skip all VLM/API calls (offline mode)")
@click.option("--no-depth", is_flag=True, help="Skip depth estimation")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(db, video_id, output, openrouter_key, replicate_token, vlm_model,
         quality_threshold, no_vlm, no_depth, verbose):
    """Run the 26-tool Zone Discovery Agent pipeline."""
    if not verbose:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    # Build config
    config = PipelineConfig(
        db_path=Path(db),
        video_id=video_id,
        output_dir=Path(output),
        openrouter_api_key="" if no_vlm else openrouter_key,
        replicate_api_token="" if no_depth else replicate_token,
        vlm_primary_model=vlm_model,
        quality_threshold=quality_threshold,
    )

    logger.info(f"Pipeline config: db={db}, video_id={video_id}, output={output}")
    logger.info(f"VLM: {'disabled' if no_vlm else vlm_model}")
    logger.info(f"Depth: {'disabled' if no_depth else 'enabled'}")

    # Run pipeline
    agent = ZoneDiscoveryAgent(config)
    try:
        state = agent.run()
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        report = agent.get_report()
        _save_report(report, Path(output))
        raise click.Abort() from e

    # Save report
    report = agent.get_report()
    _save_report(report, Path(output))

    # Print summary
    click.echo("\n" + "=" * 60)
    click.echo(f"  Pipeline Complete: {report['n_zones']} zones discovered")
    click.echo(f"  Scene type: {report['scene_type']}")
    click.echo(f"  Calibration: {report['calibration_method']}")
    click.echo(f"  Strategy: {report.get('strategy_profile', 'general')}")
    click.echo(f"  Quality: {'PASSED' if report['quality_passed'] else 'FAILED'}")
    if report['validation_metrics']:
        click.echo(f"  Score: {report['validation_metrics'].get('overall_score', 0):.2f}")
    click.echo(f"  Errors: {len(report['errors'])}")
    click.echo(f"  Output: {Path(output).resolve()}")
    click.echo("=" * 60)

    # Tool timing breakdown
    click.echo("\nTool Timing:")
    for entry in report["tool_history"]:
        status = "OK" if entry["success"] else "FAIL"
        prefix = "GATE" if entry.get("is_gate") else status
        click.echo(f"  [{prefix:4s}] {entry['tool']:35s} {entry['duration']:6.1f}s")


def _save_report(report: dict, output_dir: Path):
    """Save pipeline run report to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "pipeline_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Report saved: {report_path}")


if __name__ == "__main__":
    main()
