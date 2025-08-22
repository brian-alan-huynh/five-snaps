import os

import logging
import logging_loki
from dotenv import load_dotenv

load_dotenv()
env = os.getenv

class Logging:
    def __init__(self):
        self.loki_handler = logging_loki.LokiHandler(
            url=env("GRAFANA_LOKI_URL"),
            tags={ "application": "five-snaps" },
            auth=(env("GRAFANA_LOKI_USERNAME"), env("GRAFANA_LOKI_PASSWORD")),
            version="1",
        )

        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.ERROR,
        )

        self.logger = logging.getLogger("five_snaps_error_logger")
        self.logger.setLevel(logging.ERROR)
        self.logger.addHandler(self.loki_handler)

    def log_error(self, error_message: str) -> None:
        self.logger.error(error_message)
