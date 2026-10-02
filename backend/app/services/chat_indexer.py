import uuid
import re
import logging
from datetime import datetime, UTC
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ChatChunk
from app.rag.embedder import get_embedder

logger = logging.getLogger(__name__)

GREETING_REGEX = re.compile(
    r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening)|howdy)\b",
    re.IGNORECASE,
)


def is_greeting_or_trivial(text: str) -> bool:
    """Check if the text is a greeting or brief pleasantry."""
    clean = text.strip()
    if len(clean) < 15 and GREETING_REGEX.match(clean):
        return True
    # If the whole message is just a greeting + punctuation
    if re.fullmatch(r"^(hi|hello|hey|good\s+(morning|afternoon|evening))[\s!.,?]*$", clean, re.IGNORECASE):
        return True
    return False


def chunk_text_sliding_window(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """Splits text into chunks of specified size and overlap."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start += (chunk_size - overlap)
    return chunks


async def index_chat_message(
    chat_id: Any,
    message_id: Optional[Any],
    text: str,
    user_id: Any,
    dependent_id: Optional[Any],
    session: AsyncSession,
) -> List[ChatChunk]:
    """
    Chunk, embed, and index a chat message into ChatChunk rows.
    - Skips if text < 50 characters or is a greeting.
    - Chunks with 1200 chars / 200 overlap.
    - Embeds using standard embedder and persists with encrypted chunk_text.
    """
    if not text or len(text.strip()) < 50:
        return []

    if is_greeting_or_trivial(text):
        return []

    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    d_id = uuid.UUID(str(dependent_id)) if (dependent_id and isinstance(dependent_id, str)) else dependent_id
    c_id = uuid.UUID(str(chat_id)) if isinstance(chat_id, str) else chat_id

    chunks = chunk_text_sliding_window(text.strip(), chunk_size=1200, overlap=200)
    created_chunks = []

    embedder = None
    try:
        embedder = get_embedder()
    except Exception as e:
        logger.warning("Could not initialize embedder for chat indexing: %s", e)

    now = datetime.now(UTC)
    for idx, c_text in enumerate(chunks):
        embedding_vec = None
        if embedder:
            try:
                embedding_vec = embedder.embed_query(c_text)
            except Exception as e:
                logger.warning("Embedding generation failed for chat chunk: %s", e)

        chunk_obj = ChatChunk(
            user_id=u_id,
            dependent_id=d_id,
            chat_id=c_id,
            chunk_text=c_text,
            chunk_index=idx,
            embedding=embedding_vec,
            created_at=now,
        )
        session.add(chunk_obj)
        created_chunks.append(chunk_obj)

    await session.commit()
    return created_chunks
