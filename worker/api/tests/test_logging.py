import logging

from app.core.config import get_settings
from app.core.logging import APPLICATION_HANDLER_MARKER, configure_application_logging


def test_settings_default_log_level_is_info(monkeypatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    get_settings.cache_clear()

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.log_level == "INFO"


def test_configure_application_logging_adds_single_stdout_handler(capsys) -> None:
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level
    root_logger.handlers = []

    try:
        configure_application_logging("INFO")
        configure_application_logging("INFO")

        application_handlers = [
            handler
            for handler in root_logger.handlers
            if getattr(handler, APPLICATION_HANDLER_MARKER, False)
        ]
        assert len(application_handlers) == 1
        assert root_logger.level == logging.INFO

        logging.getLogger("app.services.hh_vacancy").info("hh_vacancy_details_completed test_event=true")

        captured = capsys.readouterr()
        assert "hh_vacancy_details_completed test_event=true" in captured.out
    finally:
        root_logger.handlers = original_handlers
        root_logger.setLevel(original_level)


def test_configure_application_logging_keeps_httpx_and_httpcore_at_warning_or_higher() -> None:
    httpx_logger = logging.getLogger("httpx")
    httpcore_logger = logging.getLogger("httpcore")
    original_httpx_level = httpx_logger.level
    original_httpcore_level = httpcore_logger.level

    try:
        configure_application_logging("INFO")

        assert httpx_logger.getEffectiveLevel() >= logging.WARNING
        assert httpcore_logger.getEffectiveLevel() >= logging.WARNING
    finally:
        httpx_logger.setLevel(original_httpx_level)
        httpcore_logger.setLevel(original_httpcore_level)


def test_application_loggers_keep_propagation_without_own_handlers() -> None:
    logger = logging.getLogger("app.services.hh_vacancy")

    assert logger.handlers == []
    assert logger.propagate is True
