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
                lines.append(f"- Diet: {escape_xml_content(str(profile.diet_type))}")
            if getattr(profile, "activity_level", None):
                lines.append(f"- Activity: {escape_xml_content(str(profile.activity_level))}")
            if getattr(profile, "height_cm", None) is not None:
                lines.append(f"- Height: {profile.height_cm} cm")
            if getattr(profile, "occupation", None):
                lines.append(f"- Occupation: {escape_xml_content(str(profile.occupation))}")

        for f in facts:
            if isinstance(f, dict):
                text = f.get("text") or f.get("fact_text") or ""
                timing = f.get("last_seen_at") or f.get("first_seen_at")
                doc_name = f.get("source_doc_name") or f.get("document_name")
            else:
                text = getattr(f, "fact_text", "")
                timing = getattr(f, "last_seen_at", None) or getattr(f, "first_seen_at", None)
                doc_name = getattr(f, "source_doc_name", None)

            if not text:
                continue

            if doc_name and "[Source Report:" not in text:
                text = f"{text} [Source Report: {doc_name}]"

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
            profile_lines.append(f"- Diet: {escape_xml_content(str(profile.diet_type))}")
        if getattr(profile, "activity_level", None):
            profile_lines.append(f"- Activity: {escape_xml_content(str(profile.activity_level))}")
        if getattr(profile, "height_cm", None) is not None:
            profile_lines.append(f"- Height: {profile.height_cm} cm")
        if getattr(profile, "occupation", None):
            profile_lines.append(f"- Occupation: {escape_xml_content(str(profile.occupation))}")
        if profile_lines:
            sections.append("Lifestyle:\n" + "\n".join(profile_lines))

    return "\n\n".join(sections)


def format_past_chats_for_prompt(chunks: List[Any]) -> str:
    """
    Format semantic chat chunks for injection into <relevant_past_conversations>.
    Attaches exact source report name if linked to a document:
      (From prior report: "{doc.filename}" / {doc_date})
    Or conversation title if standalone:
      (From prior conversation: "{session_title}" on {chat_date})
    """
    if not chunks:
        return ""

    formatted = []
    for c in chunks:
        if isinstance(c, dict):
            created_at = c.get("created_at")
            text = c.get("text") or c.get("chunk_text") or ""
            doc_name = c.get("doc_name") or c.get("document_name") or c.get("source_doc_name")
            doc_date = c.get("doc_date") or c.get("document_date") or created_at
            session_title = c.get("session_title") or c.get("source_session_title")
        else:
            c_dict = getattr(c, "__dict__", {}) or {}
            created_at = c_dict.get("created_at") or getattr(c, "created_at", None)
            text = c_dict.get("chunk_text") or getattr(c, "chunk_text", "")
            doc_name = getattr(c, "source_doc_name", None)
            doc_date = getattr(c, "source_doc_date", None) or created_at
            session_title = getattr(c, "source_session_title", None)

            # Fallback to chat / document attributes ONLY if already loaded in __dict__
            chat_obj = c_dict.get("chat") if "chat" in c_dict else None
            if not doc_name and chat_obj is not None:
                chat_dict = getattr(chat_obj, "__dict__", {}) or {}
                doc_obj = chat_dict.get("document") if "document" in chat_dict else None
                if doc_obj is not None:
                    doc_dict = getattr(doc_obj, "__dict__", {}) or {}
                    doc_name = doc_dict.get("filename") or doc_dict.get("title")
                    doc_date = doc_dict.get("created_at") or doc_date
                if not session_title:
                    session_title = chat_dict.get("session_title")
                if not created_at:
                    created_at = chat_dict.get("created_at")

        clean_text = escape_xml_content(text.strip())
        if not clean_text:
            continue

        if doc_name:
            d_str = ""
            if doc_date and hasattr(doc_date, "strftime"):
                d_str = doc_date.strftime("%Y-%m-%d")
            elif doc_date:
                d_str = str(doc_date)[:10]
            date_part = f" / {d_str}" if d_str else ""
            prefix = f'(From prior report: "{escape_xml_content(str(doc_name))}"{date_part})\n'
        elif session_title:
            d_str = ""
            if created_at and hasattr(created_at, "strftime"):
                d_str = created_at.strftime("%Y-%m-%d")
            elif created_at:
                d_str = str(created_at)[:10]
            date_part = f" on {d_str}" if d_str else ""
            prefix = f'(From prior conversation: "{escape_xml_content(str(session_title))}"{date_part})\n'
        elif created_at:
            d_str = created_at.strftime("%Y-%m-%d") if hasattr(created_at, "strftime") else str(created_at)[:10]
            prefix = f"[{d_str}] "
        else:
            prefix = ""

        formatted.append(f"{prefix}{clean_text}")

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
