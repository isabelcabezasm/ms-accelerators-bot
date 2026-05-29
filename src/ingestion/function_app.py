"""Azure Functions entry point for ingestion jobs."""

import logging

import azure.functions as func

LOGGER = logging.getLogger(__name__)
function_app = func.FunctionApp()


@function_app.timer_trigger(
    arg_name="timer",
    schedule="0 0 0 * * *",
    run_on_startup=False,
    use_monitor=True,
)
def scheduled_ingestion(timer: func.TimerRequest) -> None:
    """Log a placeholder ingestion run until the real pipeline lands."""

    if timer.past_due:
        LOGGER.warning("The scheduled ingestion trigger is past due.")

    LOGGER.info("Ingestion scaffold invoked.")
