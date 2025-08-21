import os
from multiprocessing import Queue

import logging
import logging.handlers
import logging_loki
from dotenv import load_dotenv

load_dotenv()
env = os.getenv

class Logging:
    def __init__(self):
        log_queue = Queue(-1)
        self.queue_handler = logging.handlers.QueueHandler(log_queue)

        loki_handler = logging_loki.LokiHandler(
            url=env("GRAFANA_LOKI_URL"),
            tags={ "application": "five-snaps" },
            auth=(env("GRAFANA_LOKI_USERNAME"), env("GRAFANA_LOKI_PASSWORD")),
            version="1",
        )

        self.listener = logging.handlers.QueueListener(log_queue, loki_handler)
        self.listener.start()
        
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.ERROR,
        )

        self.logger = logging.getLogger("five_snaps_error_logger")
        self.logger.setLevel(logging.ERROR)
        self.logger.addHandler(self.queue_handler)

    def log_error(self, error_message: str) -> None:
        self.logger.error(error_message)

    def terminate_logging(self) -> None:
        self.listener.stop()
        self.listener.join()
        logging.shutdown()
        self.logger.removeHandler(self.queue_handler)
