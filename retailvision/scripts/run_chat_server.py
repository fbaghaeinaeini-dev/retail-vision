"""CLI to start the RetailVision Chat API server."""

import logging
import click
import uvicorn

from api.chat_server import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@click.command()
@click.option(
    "--report",
    default="dashboard/public/data/report.json",
    help="Path to report.json",
)
@click.option(
    "--openrouter-key",
    envvar="OPENROUTER_API_KEY",
    default="",
    help="OpenRouter API key",
)
@click.option(
    "--vlm-model",
    default="qwen/qwen3.5-9b",
    help="VLM model",
)
@click.option(
    "--static-dir",
    default="",
    help="Path to built dashboard (e.g. dashboard/dist)",
)
@click.option("--host", default="0.0.0.0", help="Host")
@click.option("--port", default=8100, type=int, help="Port")
def main(report, openrouter_key, vlm_model, static_dir, host, port):
    """Start the RetailVision Chat API server."""
    app = create_app(
        report_path=report,
        openrouter_api_key=openrouter_key,
        vlm_model=vlm_model,
        static_dir=static_dir,
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
