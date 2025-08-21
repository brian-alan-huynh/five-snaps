import os
from multiprocessing import Queue

import logging
import logging.handlers
import logging_loki
from dotenv import load_dotenv

load_dotenv()
env = os.getenv

log_queue = Queue(-1)
queue_handler = logging.handlers.QueueHandler(log_queue)

loki_handler = logging_loki.LokiHandler(
    url=env("GRAFANA_LOKI_URL"),
    tags={ "application": "five-snaps" },
    auth=(env("GRAFANA_LOKI_USERNAME"), env("GRAFANA_LOKI_PASSWORD")),
    version="1",
)

listener = logging.handlers.QueueListener(log_queue, loki_handler)
listener.start()

logger = logging.getLogger("five_snaps_error_logger")
logger.setLevel(logging.ERROR)
logger.addHandler(queue_handler)

def log_error(error_message: str) -> None:
    logger.error(error_message)

def terminate_logging() -> None:
    listener.stop()
    logging.shutdown()
    logger.removeHandler(queue_handler)
