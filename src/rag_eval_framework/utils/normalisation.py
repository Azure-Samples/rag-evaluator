"""Shared score normalisation helpers."""

from __future__ import annotations


def normalise_1_5(value: float) -> float:
    """Map a 1-5 score (as returned by Azure AI Evaluation SDK) to 0.0-1.0.

    Values outside the [1, 5] range are clamped.

    Examples
    --------
    >>> normalise_1_5(1)
    0.0
    >>> normalise_1_5(5)
    1.0
    >>> normalise_1_5(3)
    0.5
    """
    return round(max(0.0, min(1.0, (value - 1.0) / 4.0)), 4)
