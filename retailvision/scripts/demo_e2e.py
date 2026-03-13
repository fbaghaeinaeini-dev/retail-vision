"""End-to-end demo: synthetic data → agent pipeline → dashboard bundle.

Runs the full RetailVision stack with zero external dependencies:
1. Generate synthetic food court tracking data (Module A substitute)
2. Run the 26-tool Zone Discovery Agent pipeline (Module B)
3. Export report.json for the dashboard (Module C input)

Usage:
    python -m scripts.demo_e2e
    python -m scripts.demo_e2e --n-tracks 200 --openrouter-key sk-...
"""

import json
import shutil
import sys
from pathlib import Path

import click
from loguru import logger

from agent.config import PipelineConfig
from agent.orchestrator import ZoneDiscoveryAgent
from scripts.generate_synthetic import generate_synthetic_dataset, GROUND_TRUTH_ZONES


@click.command()
@click.option("--n-tracks", default=200, type=int, help="Number of synthetic tracks")
@click.option("--duration", default=30, type=float, help="Simulated video duration (minutes)")
@click.option("--output", default="output/demo", help="Output directory")
@click.option("--openrouter-key", envvar="OPENROUTER_API_KEY", default="", help="OpenRouter API key")
@click.option("--replicate-token", envvar="REPLICATE_API_TOKEN", default="", help="Replicate API token")
@click.option("--clean", is_flag=True, help="Delete output dir before running")
@click.option("--seed", default=42, type=int, help="Random seed for reproducibility")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(n_tracks, duration, output, openrouter_key, replicate_token, clean, seed, verbose):
    """Run the full RetailVision pipeline on synthetic data."""
    if not verbose:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    output_dir = Path(output)
    db_path = output_dir / "demo.db"

    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
        logger.info(f"Cleaned output directory: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Generate synthetic data ──
    click.echo("\n[1/3] Generating synthetic tracking data...")
    synth_result = generate_synthetic_dataset(
        db_path=str(db_path),
        n_tracks=n_tracks,
        duration_min=duration,
        seed=seed,
    )
    click.echo(
        f"  Generated {synth_result['n_tracks']} tracks, "
        f"{synth_result['n_detections']} detections"
    )
    click.echo(f"  Ground truth zones: {', '.join(synth_result['ground_truth_zones'])}")

    # ── Step 2: Run agent pipeline ──
    click.echo("\n[2/3] Running Zone Discovery Agent pipeline...")
    config = PipelineConfig(
        db_path=db_path,
        video_id=synth_result["video_id"],
        output_dir=output_dir,
        openrouter_api_key=openrouter_key,
        replicate_api_token=replicate_token,
        quality_threshold=0.30,  # Lower threshold for synthetic data
    )

    agent = ZoneDiscoveryAgent(config)
    try:
        state = agent.run()
    except Exception as e:
        logger.error(f"Pipeline failed at step '{agent.state.current_step}': {e}")
        _save_report(agent.get_report(), output_dir)
        click.echo(f"\n  Pipeline failed: {e}")
        click.echo(f"  Partial report saved to {output_dir / 'pipeline_report.json'}")
        sys.exit(1)

    report = agent.get_report()
    _save_report(report, output_dir)

    # ── Step 3: Evaluate against ground truth ──
    click.echo("\n[3/3] Evaluating results...")
    evaluation = _evaluate_against_ground_truth(state.zone_registry)

    eval_path = output_dir / "evaluation.json"
    with open(eval_path, "w") as f:
        json.dump(evaluation, f, indent=2, default=str)

    # ── Summary ──
    click.echo("\n" + "=" * 60)
    click.echo("  DEMO COMPLETE")
    click.echo("=" * 60)
    click.echo(f"  Zones discovered:    {report['n_zones']}")
    click.echo(f"  Ground truth zones:  {len(GROUND_TRUTH_ZONES)}")
    click.echo(f"  Scene type:          {report['scene_type']}")
    click.echo(f"  Calibration:         {report['calibration_method']}")
    click.echo(f"  Quality passed:      {report['quality_passed']}")
    if report['validation_metrics']:
        click.echo(f"  Validation score:    {report['validation_metrics'].get('overall_score', 0):.2f}")
    click.echo(f"  GT match rate:       {evaluation['match_rate']:.0%}")
    click.echo(f"  Pipeline errors:     {len(report['errors'])}")
    click.echo(f"\n  Output directory:    {output_dir.resolve()}")
    click.echo(f"  Report:              report.json")
    click.echo(f"  Pipeline report:     pipeline_report.json")
    click.echo(f"  Evaluation:          evaluation.json")
    click.echo(f"  Debug artifacts:     debug/")
    click.echo("=" * 60)

    # Tool timing
    total_time = sum(e["duration"] for e in report["tool_history"])
    click.echo(f"\nTotal pipeline time: {total_time:.1f}s")
    click.echo("\nSlowest tools:")
    sorted_tools = sorted(report["tool_history"], key=lambda x: x["duration"], reverse=True)
    for entry in sorted_tools[:5]:
        click.echo(f"  {entry['tool']:35s} {entry['duration']:6.1f}s")


def _evaluate_against_ground_truth(zone_registry: dict) -> dict:
    """Compare discovered zones against known ground truth."""
    gt_types = {name: z["type"] for name, z in GROUND_TRUTH_ZONES.items()}
    discovered_types = [z.get("zone_type", "unknown") for z in zone_registry.values()]

    # Check which GT zone types were found
    matched = set()
    for gt_name, gt_type in gt_types.items():
        if gt_type in discovered_types:
            matched.add(gt_name)

    return {
        "ground_truth_count": len(gt_types),
        "discovered_count": len(zone_registry),
        "gt_types": gt_types,
        "discovered_types": discovered_types,
        "matched_gt_zones": list(matched),
        "unmatched_gt_zones": [n for n in gt_types if n not in matched],
        "match_rate": len(matched) / max(len(gt_types), 1),
    }


def _save_report(report: dict, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "pipeline_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)


if __name__ == "__main__":
    main()
