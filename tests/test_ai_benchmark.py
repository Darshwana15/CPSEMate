"""
Unit and integration tests for AI retrieval benchmark harness (Phase 2B).
"""

import pytest

from app.services.ai.benchmark import (
    calculate_recall_at_k,
    STANDARD_BENCHMARK_CASES,
)


def test_calculate_recall_at_k():
    relevant = ["C1", "C2", "C3"]
    retrieved = ["C1", "C4", "C2", "C5"]

    assert calculate_recall_at_k(retrieved, relevant, k=1) == pytest.approx(1 / 3, 0.01)
    assert calculate_recall_at_k(retrieved, relevant, k=3) == pytest.approx(2 / 3, 0.01)
    assert calculate_recall_at_k(retrieved, relevant, k=5) == pytest.approx(2 / 3, 0.01)
    assert calculate_recall_at_k([], relevant, k=5) == 0.0
    assert calculate_recall_at_k(retrieved, [], k=5) == 1.0


def test_benchmark_cases_structure():
    assert len(STANDARD_BENCHMARK_CASES) >= 5
    for case in STANDARD_BENCHMARK_CASES:
        assert case.case_id
        assert case.source_desc
        assert len(case.candidates) > 0

