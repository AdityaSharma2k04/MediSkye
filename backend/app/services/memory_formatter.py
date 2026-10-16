import logging
from typing import List, Dict, Any, Optional

from app.core.security import escape_xml_content

logger = logging.getLogger(__name__)

TYPE_HEADINGS = {
    "condition": "Known conditions:",
    "medication": "Current medications:",
    "allergy": "Allergies:",
    "family_history": "Family history:",
    "symptom": "Ongoing symptoms:",
    "lifestyle": "Lifestyle:",
    "measurement": "Recent measurements:",
    "weight": "Weight history:",
    "sport_hobby": "Sports & Activities:",
    "procedure": "Past procedures:",
}


def format_facts_for_prompt(
    facts_by_type: Dict[str, List[Any]],
    profile: Optional[Any] = None,
) -> str:
    """
    Format grouped patient facts and static profile fields into clean clinical sections for prompt injection.
    """
    sections: List[str] = []

    # Priority order of sections
    type_order = [
        "condition",
        "medication",
        "allergy",
        "family_history",
        "symptom",
        "lifestyle",
        "measurement",
        "weight",
        "sport_hobby",
        "procedure",
    ]

    # Include any additional types present in facts_by_type
    for k in facts_by_type.keys():
        if k not in type_order:
            type_order.append(k)

    for f_type in type_order:
        facts = facts_by_type.get(f_type, [])
        lines = []

        # If f_type is lifestyle and profile has static fields, blend them in
        if f_type == "lifestyle" and profile:
            if getattr(profile, "diet_type", None):
                lines.append(f"- Diet: {profile.diet_type}")
            if getattr(profile, "activity_level", None):
                lines.append(f"- Activity: {profile.activity_level}")
            if getattr(profile, "height_cm", None) is not None:
                lines.append(f"- Height: {profile.height_cm} cm")
            if getattr(profile, "occupation", None):
                lines.append(f"- Occupation: {profile.occupation}")

        for f in facts:
            if isinstance(f, dict):
                text = f.get("text") or f.get("fact_text") or ""
                timing = f.get("last_seen_at") or f.get("first_seen_at")
            else:
                text = getattr(f, "fact_text", "")
                timing = getattr(f, "last_seen_at", None) or getattr(f, "first_seen_at", None)

            if not text:
                continue

            # Format timing tag if not already part of text
            date_str = ""
            if timing and hasattr(timing, "strftime") and str(timing.year) not in text:
                date_str = f" (reported {timing.strftime('%Y-%m-%d')})"

            lines.append(f"- {escape_xml_content(text.strip())}{date_str}")

        if lines:
            header = TYPE_HEADINGS.get(f_type, f"{f_type.capitalize()}:")
            sections.append(f"{header}\n" + "\n".join(lines))

    # If lifestyle was not in facts_by_type but profile has lifestyle fields
    if "lifestyle" not in facts_by_type and profile:
        profile_lines = []
        if getattr(profile, "diet_type", None):
            profile_lines.append(f"- Diet: {profile.diet_type}")
        if getattr(profile, "activity_level", None):
            profile_lines.append(f"- Activity: {profile.activity_level}")
        if getattr(profile, "height_cm", None) is not None:
            profile_lines.append(f"- Height: {profile.height_cm} cm")
        if getattr(profile, "occupation", None):
            profile_lines.append(f"- Occupation: {profile.occupation}")
        if profile_lines:
            sections.append("Lifestyle:\n" + "\n".join(profile_lines))

    return "\n\n".join(sections)


def format_past_chats_for_prompt(chunks: List[Any]) -> str:
    """
    Format semantic chat chunks for injection into <relevant_past_conversations>.
    """
    if not chunks:
        return ""

    formatted = []
    for c in chunks:
        if isinstance(c, dict):
            created_at = c.get("created_at")
            text = c.get("text") or c.get("chunk_text") or ""
        else:
            created_at = getattr(c, "created_at", None)
            text = getattr(c, "chunk_text", "")

        date_prefix = ""
        if created_at and hasattr(created_at, "strftime"):
            date_prefix = f"[{created_at.strftime('%Y-%m-%d')}] "
        elif created_at:
            date_prefix = f"[{str(created_at)[:10]}] "

        clean_text = escape_xml_content(text.strip())
        if clean_text:
            formatted.append(f"{date_prefix}{clean_text}")

    return "\n\n".join(formatted)


def format_multi_doc_context(chunks_with_source: List[Any]) -> str:
    """
    Format multi-document chunks with XML tags indicating document filename.
    """
    if not chunks_with_source:
        return ""

    blocks = []
    for item in chunks_with_source:
        if isinstance(item, dict):
            name = item.get("name") or item.get("filename") or item.get("source") or "document.pdf"
            excerpt = item.get("excerpt") or item.get("text") or item.get("content") or ""
        elif hasattr(item, "metadata") and hasattr(item, "page_content"):
            name = item.metadata.get("source") or item.metadata.get("filename") or "document.pdf"
            excerpt = item.page_content
        else:
            name = getattr(item, "filename", "document.pdf")
            excerpt = getattr(item, "text", str(item))

        blocks.append(f'<document name="{escape_xml_content(name)}">\n  <excerpt>{escape_xml_content(excerpt.strip())}</excerpt>\n</document>')

    return "\n".join(blocks)
