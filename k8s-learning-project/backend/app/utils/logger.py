import logging

from pythonjsonlogger.json import JsonFormatter

from app.core.config import settings


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.service = "backend-api"
        record.environment = settings.ENVIRONMENT
        record.loki_labels = f'{{service="backend-api",env="{settings.ENVIRONMENT}"}}'
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    formatter = JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(service)s %(environment)s %(loki_labels)s"
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    root_logger.addHandler(handler)
    root_logger.addFilter(_ContextFilter())
