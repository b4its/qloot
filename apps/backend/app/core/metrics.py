"""In-process metrics registry (Prometheus-compatible text exposition).

Deliberately dependency-free: counters/gauges/histograms rendered in the
Prometheus text format. Enough for the blueprint's metric names without
pulling prometheus_client into the worker images.
"""

from __future__ import annotations

import threading
from collections import defaultdict

_lock = threading.Lock()
_counters: dict[str, float] = defaultdict(float)
_gauges: dict[str, float] = {}
_histograms: dict[str, list[float]] = defaultdict(list)

_HELP = {
    "http_requests_total": "Total HTTP requests",
    "http_request_duration_seconds": "HTTP request duration in seconds",
    "ai_jobs_total": "AI jobs processed",
    "grading_failures_total": "Grading failures",
    "blockchain_transactions_total": "Blockchain transactions submitted",
    "blockchain_failed_transactions_total": "Blockchain transactions failed",
    "reward_allocations_total": "Reward allocations created",
    "ledger_reconciliation_errors_total": "Ledger reconciliation mismatches",
}


def incr(name: str, value: float = 1.0, **labels: str) -> None:
    key = _label(name, labels)
    with _lock:
        _counters[key] += value


def gauge(name: str, value: float, **labels: str) -> None:
    key = _label(name, labels)
    with _lock:
        _gauges[key] = value


def observe(name: str, value: float, **labels: str) -> None:
    key = _label(name, labels)
    with _lock:
        _histograms[key].append(value)
        if len(_histograms[key]) > 1000:
            _histograms[key] = _histograms[key][-1000:]


def _label(name: str, labels: dict[str, str]) -> str:
    if not labels:
        return name
    parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{parts}}}"


def render() -> str:
    lines: list[str] = []
    with _lock:
        for key, value in sorted(_counters.items()):
            base = key.split("{")[0]
            if base in _HELP:
                lines.append(f"# HELP {base} {_HELP[base]}")
                lines.append(f"# TYPE {base} counter")
            lines.append(f"{key} {value}")
        for key, value in sorted(_gauges.items()):
            base = key.split("{")[0]
            lines.append(f"# TYPE {base} gauge")
            lines.append(f"{key} {value}")
        for key, values in sorted(_histograms.items()):
            if not values:
                continue
            base = key.split("{")[0]
            total = sum(values)
            lines.append(f"# TYPE {base} summary")
            lines.append(f"{key}_count {len(values)}")
            lines.append(f"{key}_sum {total}")
    return "\n".join(lines) + "\n"
