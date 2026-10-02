"""
Manual evaluation script: runs a query against Gemini using the synthesis prompt builder,
and scores the response against the clinical communication rubric.

Usage:
    python scripts/run_prompt_eval.py [optional_pdf_path] [optional_query]
"""

import os
import sys
import asyncio
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from google import genai
from langchain_core.documents import Document
from app.core.config import settings
from app.rag.prompt_builder import build_prompt
from app.rag.loader import extract_text_from_file
from tests.eval.test_prompt_quality import evaluate_rubric


def run_evaluation():
    if not settings.GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY is not set.")
        return

    pdf_arg = sys.argv[1] if len(sys.argv) > 1 else None
    query_arg = sys.argv[2] if len(sys.argv) > 2 else "What are my abnormal values in this report?"

    if pdf_arg and os.path.exists(pdf_arg):
        filename = os.path.basename(pdf_arg)
        print(f"Loading and extracting PDF: {pdf_arg}...")
        extracted = asyncio.run(extract_text_from_file(pdf_arg, filename))
        sample_doc = Document(
            page_content="\n\n".join(d.page_content for d in extracted),
            metadata={"source": filename, "page": 1}
        )
    else:
        sample_doc = Document(
            page_content="""
Fasting Blood Glucose: 168 mg/dL (Reference Range: 70 - 100 mg/dL) [HIGH]
HbA1c: 8.4 % (Reference Range: 4.0 - 5.6 %) [HIGH]
Total Cholesterol: 240 mg/dL (Reference Range: < 200 mg/dL) [HIGH]
LDL Cholesterol: 155 mg/dL (Reference Range: < 100 mg/dL) [HIGH]
Triglycerides: 210 mg/dL (Reference Range: < 150 mg/dL) [HIGH]
HDL Cholesterol: 38 mg/dL (Reference Range: > 40 mg/dL) [LOW]
Serum Creatinine: 1.4 mg/dL (Reference Range: 0.7 - 1.2 mg/dL) [HIGH]
Blood Urea Nitrogen (BUN): 26 mg/dL (Reference Range: 7 - 20 mg/dL) [HIGH]
eGFR: 58 mL/min/1.73m2 (Reference Range: > 90 mL/min/1.73m2) [LOW]
Blood Pressure: 152/96 mmHg [STAGE 2 HYPERTENSION]
ALT (SGPT): 32 U/L (Reference Range: 7 - 56 U/L) [NORMAL]
AST (SGOT): 28 U/L (Reference Range: 10 - 40 U/L) [NORMAL]
""",
            metadata={"source": "testreport1.pdf", "page": 1}
        )

    query = query_arg
    print(f"Running evaluation for query: '{query}' against model {settings.GEMINI_MODEL}...\n")

    prompt = build_prompt(
        user_query=query,
        retrieved_docs=[sample_doc],
        calculated_age="54",
        biological_sex="Male",
        height_cm=175.0,
        diet_type="vegetarian",
        activity_level="moderate",
        occupation="Software Engineer",
    )

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )

    generated_text = response.text or ""
    print("=" * 60)
    print("GENERATED SYNTHESIZED CLINICAL RESPONSE:")
    print("=" * 60)
    print(generated_text)
    print("=" * 60)

    rubric = evaluate_rubric(generated_text, check_citation=True)
    print("\nEVALUATION RUBRIC RESULTS:")
    for metric, val in rubric.items():
        print(f"  {metric}: {val}")
    print("=" * 60)


if __name__ == "__main__":
    run_evaluation()
