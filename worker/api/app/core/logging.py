import logging
import sys

APPLICATION_HANDLER_MARKER = "_ai_job_automation_stdout_handler"
DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_application_logging(log_level: str) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(_resolve_log_level(log_level))

    application_handlers = [
        handler
        for handler in root_logger.handlers
        if getattr(handler, APPLICATION_HANDLER_MARKER, False)
    ]

    if not application_handlers:
        handler = logging.StreamHandler(sys.stdout)
        setattr(handler, APPLICATION_HANDLER_MARKER, True)
        handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
        root_logger.addHandler(handler)
        return

    primary_handler = application_handlers[0]
    primary_handler.setLevel(logging.NOTSET)
    primary_handler.setStream(sys.stdout)
    primary_handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))

    for duplicate_handler in application_handlers[1:]:
        root_logger.removeHandler(duplicate_handler)


def _resolve_log_level(log_level: str) -> int:
    normalized = log_level.strip().upper()
    level = logging.getLevelName(normalized)
    if isinstance(level, int):
        return level
    return logging.INFO
