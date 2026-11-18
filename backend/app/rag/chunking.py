"""
Medical-aware text splitting.

RecursiveCharacterTextSplitter with the default separator ladder
(["\\n\\n", "\\n", ". ", ...]) slices Markdown table rows apart (each row is
its own line) and scatters bullet lists across chunks.  For lab reports —
where Gemini Vision produces Markdown tables and bulleted findings — a value
like "Hemoglobin | 14.2 | g/dL" can end up separated from its row header.

`MedicalTextSplitter` fixes this by "atomizing" sensitive blocks before
splitting and restoring them afterwards:

  1. Contiguous Markdown table rows (two or more lines that start with "|")
     are collapsed into an opaque token, so the splitter can never cut them.
  2. Runs of two or more bullet/numbered list lines are protected the same
     way, keeping a finding list (and its units/notes) together.

The protected token contains no separator characters, so the standard
recursive splitter treats the whole block as a single indivisible unit.
A table that is longer than chunk_size simply becomes its own (oversized)
chunk — keeping the table intact is the correct tradeoff for medical data.
"""

from __future__ import annotations

import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Two or more consecutive Markdown table rows (header + separator, header +
# body, or body + body).  Vision extraction emits "| ... |" rows with an
# optional "|---|---|" delimiter row.
TABLE_BLOCK_RE = re.compile(
    r"(?:^[ \t]*\|.*\|[ \t]*$\n?){2,}",
    re.MULTILINE,
)

# Runs of two or more bulleted/numbered list lines (Markdown "-", "*", "•",
# or "1." / "1)" style numbering).
BULLET_RUN_RE = re.compile(
    r"(?:^[ \t]*(?:[-*•]|\d{1,2}[.)])\s+\S[^\n]*(?:\n|$)){2,}",
    re.MULTILINE,
)

TABLE_ROW_RE = re.compile(r"^[ \t]*\|.*\|[ \t]*$")
TABLE_SEP_RE = re.compile(r"^[ \t]*\|(?:\s*:?-+:?\s*\|)+[ \t]*$")


def _count_table_columns(line: str) -> int:
    s = line.strip()
    s = s.removeprefix("|")
    if s.endswith("|") and not s.endswith(r"\|"):
        s = s[:-1]
    return len(re.split(r"(?<!\\)\|", s))


def _propagate_table_headers(page_docs: list[Document]) -> list[Document]:
    """
    Carries over Markdown table headers across page boundaries when a table
    continues onto page N+1 without repeating the column header row.
    """
    updated_docs: list[Document] = []
    last_header: tuple[str, str, int] | None = None

    for doc in page_docs:
        content = doc.page_content or ""
        lines = content.split("\n")
        new_lines: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            is_table_row = bool(TABLE_ROW_RE.match(line))
            prev_is_table_row = bool(i > 0 and TABLE_ROW_RE.match(lines[i - 1]))

            if is_table_row and not prev_is_table_row:
                next_line = lines[i + 1] if i + 1 < len(lines) else ""
                if TABLE_SEP_RE.match(next_line):
                    last_header = (line, next_line, _count_table_columns(line))
                    new_lines.append(line)
                    new_lines.append(next_line)
                    i += 2
                    continue
                elif last_header is not None and _count_table_columns(line) == last_header[2]:
                    new_lines.append(last_header[0])
                    new_lines.append(last_header[1])
                    new_lines.append(line)
                    i += 1
                    continue

            new_lines.append(line)
            i += 1

        new_content = "\n".join(new_lines)
        if new_content != content:
            updated_docs.append(Document(page_content=new_content, metadata=dict(doc.metadata)))
        else:
            updated_docs.append(doc)

    return updated_docs

# Opaque, separator-free placeholder used while splitting.  Contains no
# newlines/spaces/punctuation, so RecursiveCharacterTextSplitter can never
# split inside it.
_BLOCK_TOKEN_TEMPLATE = "\u0000MEDBLOCK{idx}\u0000"
_BLOCK_TOKEN_RE = re.compile(r"\u0000MEDBLOCK(\d+)\u0000")


class MedicalTextSplitter(RecursiveCharacterTextSplitter):
    """
    RecursiveCharacterTextSplitter that keeps Markdown tables and bullet
    runs intact across chunk boundaries.
    """

    def __init__(
        self,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
        separators=None,
        **kwargs,
    ):
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators or ["\n\n", "\n", ". ", "; ", ", ", " ", ""],
            **kwargs,
        )

    # ── Block protection ──────────────────────────────────────────────
    def _protect_blocks(self, text: str) -> tuple[str, list[str]]:
        """Replace table blocks and bullet runs with opaque tokens."""
        protected: list[str] = []

        def _store(match: re.Match) -> str:
            token = _BLOCK_TOKEN_TEMPLATE.format(idx=len(protected))
            protected.append(match.group(0))
            return token

        text = TABLE_BLOCK_RE.sub(_store, text)
        text = BULLET_RUN_RE.sub(_store, text)
        return text, protected

    @staticmethod
    def _restore_blocks(text: str, protected: list[str]) -> str:
        """Restore protected blocks after splitting."""
        if not protected:
            return text
        return _BLOCK_TOKEN_RE.sub(
            lambda m: protected[int(m.group(1))],
            text,
        )

    def split_text(self, text: str) -> list[str]:
        protected_text, protected = self._protect_blocks(text)
        if not protected:
            return super().split_text(text)
        chunks = super().split_text(protected_text)
        return [self._restore_blocks(c, protected) for c in chunks]


def split_medical_documents(
    page_docs: list[Document],
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> list[Document]:
    """Split documents with table/bullet-aware chunking (CPU-bound)."""
    propagated_docs = _propagate_table_headers(page_docs)
    splitter = MedicalTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    raw_chunks = splitter.split_documents(propagated_docs)
    return [c for c in raw_chunks if c.page_content and c.page_content.strip()]
