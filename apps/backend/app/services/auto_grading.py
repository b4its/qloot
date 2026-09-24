"""Deterministic scoring for the non-essay question types.

All functions are pure and offline-safe (no AI). They return a credit *ratio*
in [0, 1] which the grader multiplies by the question's max_score_bp.

Partial-credit rules (monotonic, tested at the boundaries):
  * multiple_choice / true_false : 1.0 if exactly right else 0.0.
  * multi_select                 : (correct chosen − incorrect chosen) / |correct|,
                                   clamped to [0, 1]. Selecting every option does
                                   NOT beat selecting exactly the right ones.
  * numeric                      : 1.0 within tolerance, else 0.0.
  * fill_blank                   : 1.0 if the normalised answer is accepted.
  * ordering                     : fraction of items in the correct position
                                   (Kendall-style position credit).
  * matching                     : fraction of pairs matched correctly.
"""

from __future__ import annotations

import json
from typing import Any

from app.models.exam import Question


def _answer_obj(answer_text: str | None) -> Any:
    """Parse a structured answer payload (JSON) or fall back to the raw string."""
    if answer_text is None:
        return None
    s = answer_text.strip()
    if s.startswith("{") or s.startswith("["):
        try:
            return json.loads(s)
        except (ValueError, TypeError):
            return s
    return s


def _labels(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip().upper() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [p.strip().upper() for p in value.split(",") if p.strip()]
    return []


def _norm(text: str, *, case_sensitive: bool, trim: bool) -> str:
    out = text
    if trim:
        out = " ".join(out.split())
    if not case_sensitive:
        out = out.casefold()
    return out


def score_auto_answer(question: Question, answer_text: str | None) -> float:
    """Return the credit ratio in [0, 1] for one answer."""
    qtype = question.qtype
    key = question.answer_json or {}

    if qtype in ("multiple_choice", "true_false"):
        chosen = (answer_text or "").strip().upper()
        if qtype == "true_false":
            chosen = (answer_text or "").strip().lower()
            correct = (question.correct_answer or "").strip().lower()
        else:
            correct = (question.correct_answer or "").strip().upper()
        return 1.0 if chosen and chosen == correct else 0.0

    if qtype == "multi_select":
        correct_set = {str(c).strip().upper() for c in (key.get("correct") or [])}
        chosen_set = set(_labels(_answer_obj(answer_text)))
        if not correct_set:
            return 0.0
        hits = len(chosen_set & correct_set)
        wrong = len(chosen_set - correct_set)
        return max(0.0, min(1.0, (hits - wrong) / len(correct_set)))

    if qtype == "numeric":
        raw = _answer_obj(answer_text)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.0
        target = key.get("value")
        if target is None:
            return 0.0
        tol = float(key.get("tolerance") or 0.0)
        return 1.0 if abs(value - float(target)) <= tol else 0.0

    if qtype == "fill_blank":
        case_sensitive = bool(key.get("case_sensitive", False))
        trim = bool(key.get("trim", True))
        answer = _norm(
            str(_answer_obj(answer_text) or ""), case_sensitive=case_sensitive, trim=trim
        )
        accepted = {
            _norm(str(a), case_sensitive=case_sensitive, trim=trim)
            for a in (key.get("accepted") or [])
        }
        return 1.0 if answer and answer in accepted else 0.0

    if qtype == "ordering":
        correct_order = [str(x).strip().upper() for x in (key.get("order") or [])]
        chosen_order = _labels(_answer_obj(answer_text))
        n = len(correct_order)
        if n == 0:
            return 0.0
        in_place = sum(
            1 for i, item in enumerate(chosen_order[:n]) if item == correct_order[i]
        )
        return in_place / n

    if qtype == "matching":
        pairs = {str(k): str(v) for k, v in (key.get("pairs") or {}).items()}
        chosen_pairs = _answer_obj(answer_text)
        if not isinstance(chosen_pairs, dict) or not pairs:
            return 0.0
        hits = sum(1 for k, v in pairs.items() if str(chosen_pairs.get(k, "")) == v)
        return hits / len(pairs)

    # Unknown/unsupported type: no credit rather than a crash.
    return 0.0


def auto_feedback(question: Question, answer_text: str | None, ratio: float) -> str:
    if ratio >= 1.0:
        return "Benar"
    if ratio <= 0.0:
        return "Salah"
    return f"Sebagian benar ({int(round(ratio * 100))}%)"
