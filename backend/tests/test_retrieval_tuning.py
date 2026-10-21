"""
Tests for dynamic retrieval breadth tuning (k and fetch_k scaling).
"""

from app.rag.retriever import (
    RETRIEVAL_K,
    RETRIEVAL_FETCH_K,
    dynamic_retrieval_k,
    dynamic_fetch_k,
    MAX_RETRIEVAL_K,
)


def test_short_question_gets_tight_k():
    assert dynamic_retrieval_k("Is my hemoglobin normal?") == 4
    assert dynamic_retrieval_k("What is my LDL?") == 4
    assert dynamic_retrieval_k("Explain HbA1c.") == 4


def test_medium_question_gets_default_range():
    assert dynamic_retrieval_k("What does my cholesterol panel say about my heart health overall?") == 6


def test_long_question_gets_wide_k():
    assert dynamic_retrieval_k(
        "Compare my liver enzymes across both reports and tell me whether the trend is improving or worsening."
    ) == 12


def test_multi_part_question_promoted_to_wide_k():
    q = "What are my abnormal values, and also what should I discuss with my doctor about them?"
    assert len(q.split()) >= 10
    assert dynamic_retrieval_k(q) == 12


def test_double_question_mark_promoted():
    q = "Is my thyroid normal? And what about my vitamin D? Do I need supplements?"
    assert dynamic_retrieval_k(q) == 12


def test_k_never_exceeds_cap():
    monster = " and ".join(["what about test number " + str(i) for i in range(40)])
    assert dynamic_retrieval_k(monster) <= MAX_RETRIEVAL_K


def test_empty_query_safe():
    assert dynamic_retrieval_k("") == 4
    assert dynamic_retrieval_k(None) == 4


def test_fetch_k_scales_with_k_and_stays_bounded():
    assert dynamic_fetch_k(4) == RETRIEVAL_FETCH_K          # floor at 24
    assert dynamic_fetch_k(8) == RETRIEVAL_FETCH_K          # default unchanged
    assert dynamic_fetch_k(12) == 36                        # 3x for wide sweeps
    assert dynamic_fetch_k(50) == 48                        # capped


def test_defaults_unchanged_for_backward_compat():
    assert RETRIEVAL_K == 8
    assert RETRIEVAL_FETCH_K == 24
