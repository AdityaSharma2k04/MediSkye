import uuid
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, Chat, ChatChunk
from app.core.auth import get_password_hash
from app.services.chat_indexer import index_chat_message


@pytest.mark.asyncio
async def test_chat_indexer_skips_short_message_and_greeting():
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"idx_user_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        chat = Chat(user_id=user.id, role="user", message="Hello!")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        # 1. Short message (< 50 chars)
        res_short = await index_chat_message(
            chat_id=chat.id,
            message_id=None,
            text="Too short",
            user_id=user.id,
            dependent_id=None,
            session=session,
        )
        assert res_short == []

        # 2. Greeting message
        res_greeting = await index_chat_message(
            chat_id=chat.id,
            message_id=None,
            text="Hello there, good morning!",
            user_id=user.id,
            dependent_id=None,
            session=session,
        )
        assert res_greeting == []


@pytest.mark.asyncio
async def test_chat_indexer_substantive_message_creates_chunk():
    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.1, 0.2, 0.3, 0.4]

    async with AsyncSessionLocal() as session:
        user = User(
            email=f"idx_sub_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        chat = Chat(
            user_id=user.id,
            role="user",
            message="I would like to understand if my fasting blood glucose of 140 mg/dL requires immediate medical attention."
        )
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        substantive_text = (
            "I have been feeling quite fatigued lately and noticed my fasting blood glucose was 140 mg/dL yesterday morning. "
            "Could this be linked to my current diet or medication adjustments?"
        )

        with patch("app.services.chat_indexer.get_embedder", return_value=mock_embedder):
            created = await index_chat_message(
                chat_id=chat.id,
                message_id=None,
                text=substantive_text,
                user_id=user.id,
                dependent_id=None,
                session=session,
            )

            assert len(created) >= 1
            assert created[0].chunk_text == substantive_text
            assert created[0].embedding == [0.1, 0.2, 0.3, 0.4]

            # Verify in DB
            q = select(ChatChunk).filter(ChatChunk.chat_id == chat.id)
            res = await session.execute(q)
            db_chunks = res.scalars().all()
            assert len(db_chunks) >= 1
            assert db_chunks[0].chunk_text == substantive_text
