"""Structured logging configuration (structlog)."""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import settings

_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "session_id",
    "session_token",
    "authorization",
    "cookie",
    "private_key",
    "blockchain_private_key",
    "api_key",
    "gemini_api_key",
    "secret",
    "student_answer",
    "answer_text",
}


def _redact(_logger: object, _name: str, event_dict: dict) -> dict:
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***redacted***"
    return event_dict


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact,
    ]
    if settings.log_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = settings.service_name) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
