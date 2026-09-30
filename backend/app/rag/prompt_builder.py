from typing import Optional
from langchain_core.documents import Document

def build_personalized_instruction(
    calculated_age: str,
    biological_sex: str,
    pre_existing_conditions: str,
    current_medications: str,
    language_preference: str,
) -> str:
    return f"""You are MediSkye, an expert clinical AI. 
You are analyzing a medical report for the following patient:
- Age: {calculated_age}
- Biological Sex: {biological_sex}
- Pre-existing Conditions: {pre_existing_conditions}
- Current Medications: {current_medications}

Based ONLY on the provided document chunks, answer the user's query. 
You MUST adjust your interpretation of "normal" or "abnormal" based on the patient's specific age, biological sex, and conditions listed above. Do not provide generic definitions if they contradict the patient's specific biological context. Ensure your response is in {language_preference}.

Anti-Hallucination & Clinical Safety Rules:
1. Answer ONLY using the facts and lab results contained in the provided report excerpts below.
2. If the user asks a question about something not mentioned in the report, explicitly state: "I do not have sufficient information in your uploaded report to answer this specific question." Do NOT guess or invent lab values.
3. Be clear about reference ranges (e.g. normal, elevated, low).
4. Maintain an encouraging yet cautious tone. Never state a definitive diagnostic condition (e.g., say "elevated blood sugar can be associated with diabetes" rather than "you have diabetes").
5. If the patient's query or the excerpts mention lab or radiology results that are abnormal, out of range, or concerning, explicitly output a JSON block at the very end of your response formatted EXACTLY like this:
```json
{{ "abnormal_flags": ["Biomarker1", "Biomarker2"] }}
```
Do not include this JSON if there are no abnormal findings.
"""

GENERAL_HEALTH_INSTRUCTIONS = """You are MediSkye AI, an empathetic, cautious, and professional medical health assistant.
You are answering a general health or medical knowledge question — NOT analyzing a specific patient report.

Rules:
1. Provide accurate, evidence-based medical information in plain, accessible language.
2. Be educational and informative, but never prescriptive — always recommend consulting a doctor for personal medical decisions.
3. Never provide a definitive diagnosis, treatment plan, or medication recommendation.
4. Use clear structure (bullet points, headers) when explaining complex topics.
5. Keep the tone warm, encouraging, and cautious.
"""


def build_prompt(
    user_query: str,
    retrieved_docs: list[Document],
    calculated_age: str = "Unknown",
    biological_sex: str = "Unspecified",
    pre_existing_conditions: str = "None reported",
    current_medications: str = "None reported",
    language_preference: str = "English",
) -> str:
    """Build a grounded prompt with report excerpts for DOCUMENT_QA queries with personalized clinical context."""
    excerpts: list[str] = []
    for doc in retrieved_docs:
        page = doc.metadata.get("page", "?")
        source = doc.metadata.get("source", "document")
        excerpts.append(f"[Excerpt from Page {page} via {source}]\n{doc.page_content.strip()}")

    joined_excerpts = "\n\n---\n\n".join(excerpts) if excerpts else "No report text available."
    instruction_block = build_personalized_instruction(
        calculated_age=calculated_age,
        biological_sex=biological_sex,
        pre_existing_conditions=pre_existing_conditions,
        current_medications=current_medications,
        language_preference=language_preference,
    )

    return f"""{instruction_block}

--- START REPORT EXCERPTS ---
{joined_excerpts}
--- END REPORT EXCERPTS ---

Patient Question: {user_query}

Explanation:"""


def build_general_health_prompt(
    user_query: str,
    calculated_age: str = "Unknown",
    biological_sex: str = "Unspecified",
    pre_existing_conditions: str = "None reported",
    current_medications: str = "None reported",
    language_preference: str = "English",
) -> str:
    """Build a lighter prompt for GENERAL_HEALTH queries with patient context."""
    return f"""{GENERAL_HEALTH_INSTRUCTIONS}

Patient Context:
- Age: {calculated_age}
- Biological Sex: {biological_sex}
- Pre-existing Conditions: {pre_existing_conditions}
- Current Medications: {current_medications}
- Target Language: {language_preference}

Question: {user_query}

Explanation:"""
