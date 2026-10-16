import pytest
from app.rag.prompt_builder import build_general_health_prompt


def test_build_general_health_prompt_returns_non_empty_string():
    query_text = "What are the common symptoms of seasonal allergies?"
    system_instruction, user_content = build_general_health_prompt(
        user_query=query_text,
        calculated_age="30",
        biological_sex="Female",
        pre_existing_conditions="None reported",
        current_medications="None reported",
        language_preference="English",
    )
    assert isinstance(system_instruction, str) and len(system_instruction.strip()) > 0
    assert isinstance(user_content, str) and len(user_content.strip()) > 0
    assert query_text in user_content
