"""Azure Functions entry point for ingestion jobs."""

from __future__ import annotations

import logging

import azure.functions as func

from src.ingestion.crawler import AcceleratorsCatalogCrawler

LOGGER = logging.getLogger(__name__)
app = func.FunctionApp()
function_app = app


@app.timer_trigger(
    arg_name="timer",
    schedule="0 0 3 * * *",
    run_on_startup=False,
    use_monitor=True,
)
def scheduled_ingestion(timer: func.TimerRequest) -> None:
    """Run the daily accelerators.ms catalog crawl."""

    if timer.past_due:
        LOGGER.warning("The scheduled ingestion trigger is past due.")

    with AcceleratorsCatalogCrawler.from_environment() as crawler:
        result = crawler.crawl()

    LOGGER.info(
        "Catalog crawl completed with %s accelerators.",
        len(result.accelerators),
    )
