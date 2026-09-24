"""In-process metrics registry (Prometheus-compatible text exposition).

Deliberately dependency-free: counters/gauges/histograms rendered in the
Prometheus text format. Enough for the blueprint's metric names without
pulling prometheus_client into the worker images.
"""

from __future__ import annotations

import bisect
import threading
from collections import defaultdict

# Fixed histogram buckets (seconds). Cumulative: a sample of 0.3s falls into
# every bucket whose upper bound is >= 0.3. The final +Inf bucket always holds
# the total count, matching the Prometheus histogram convention.
_HISTOGRAM_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

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
    "blockchain_terminal_failures_total": "Blockchain transactions in a terminal failed state",
    "blockchain_resubmitted_total": "Blockchain transactions resubmitted with a fee bump",
    "reward_allocations_total": "Reward allocations created",
    "reward_cap_rejections_total": "Reward allocations rejected for exceeding the per-tx cap",
    "ledger_reconciliation_errors_total": "Ledger reconciliation mismatches",
    "ledger_negative_balance_total": "Ledger mutations that drove a balance negative",
    "rate_limited_total": "Requests rejected by the rate limiter",
    "auth_logins_total": "Successful logins",
    "auth_login_failures_total": "Failed login attempts",
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
            label_prefix = _label_prefix(key)
            if base in _HELP:
                lines.append(f"# HELP {base} {_HELP[base]}")
            lines.append(f"# TYPE {base} histogram")
            # Buckets are cumulative: count every sample <= upper bound.
            ordered = sorted(values)
            for bound in _HISTOGRAM_BUCKETS:
                cumulative = bisect.bisect_right(ordered, bound)
                lines.append(f'{base}_bucket{label_prefix(le=_fmt_bound(bound))} {cumulative}')
            lines.append(f'{base}_bucket{label_prefix(le="+Inf")} {len(values)}')
            lines.append(f"{base}_count{label_prefix()} {len(values)}")
            lines.append(f"{base}_sum{label_prefix()} {sum(values)}")
    return "\n".join(lines) + "\n"


def _fmt_bound(bound: float) -> str:
    """Render a bucket upper bound the way Prometheus does (e.g. ``1.0``)."""
    return f"{bound:g}"


def _label_prefix(key: str):
    """Return a callable that builds the ``{...}`` suffix for a series key.

    Histogram buckets need an extra ``le`` label appended to whatever labels
    the observed series already carries.
    """
    if "{" in key:
        existing = key[key.index("{") + 1 : key.rindex("}")]
    else:
        existing = ""

    def _build(**extra: str) -> str:
        parts = []
        if existing:
            parts.append(existing)
        parts.extend(f'{k}="{v}"' for k, v in sorted(extra.items()))
        return "{" + ",".join(parts) + "}" if parts else ""

    return _build
