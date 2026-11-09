"""Encrypt (or revert) legacy plaintext PHI columns. Never logs values; logs counts and row ids only."""
import json
import logging
from dataclasses import dataclass
from typing import Any, List, Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.encryption import fernet
from app.db.models import Chat, DependentProfile, Document, User

logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "gAAAA"


@dataclass(frozen=True)
class Target:
    model: Any
    column: str
    kind: str  # "json" | "text"

    @property
    def label(self) -> str:
        return f"{self.model.__tablename__}.{self.column}"


TARGETS = [
    Target(Document, "cached_metrics", "json"),
    Target(Document, "cached_summary", "text"),
    Target(User, "full_name", "text"),
    Target(DependentProfile, "full_name", "text"),
]


@dataclass
class Stats:
    label: str
    total: int = 0
    null: int = 0
    encrypted: int = 0
    plaintext: int = 0
    undecryptable: int = 0   # Fernet-looking but not decryptable with this key: NEVER modified
    updated: int = 0


def _decrypt(raw: str) -> Optional[str]:
    try:
        return fernet.decrypt(raw.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def _raw_col(target: Target):
    """The column read WITHOUT the encrypting TypeDecorator."""
    col = target.model.__table__.c[target.column]
    return sa.type_coerce(col, sa.JSON() if target.kind == "json" else sa.Text())


async def preflight_column_limits(session: AsyncSession, dialect_name: str) -> List[str]:
    """Postgres only: abort if any target column has a length limit (tokens are longer than plaintext)."""
    if dialect_name != "postgresql":
        return []
    rows = (await session.execute(sa.text(
        "SELECT table_name, column_name, character_maximum_length FROM information_schema.columns "
        "WHERE (table_name, column_name) IN (('documents','cached_metrics'),('documents','cached_summary'),"
        "('users','full_name'),('dependent_profiles','full_name'))"
    ))).all()
    return [f"{t}.{c} has a length limit of {n}; widen it before encrypting" for t, c, n in rows if n is not None]


async def preflight_key_matches(session: AsyncSession) -> Optional[str]:
    """Refuse to run if FERNET_KEY cannot decrypt already-encrypted production data (wrong key)."""
    raw = sa.type_coerce(Chat.__table__.c.message, sa.Text())
    rows = (await session.execute(
        sa.select(raw).where(Chat.__table__.c.message.is_not(None)).limit(20)
    )).scalars().all()
    tokens = [r for r in rows if isinstance(r, str) and r.startswith(_TOKEN_PREFIX)]
    if tokens and not any(_decrypt(t) is not None for t in tokens):
        return "FERNET_KEY does not decrypt any sampled encrypted chat message; refusing to run."
    return None


async def _write_and_verify(session, target: Target, pk, pending, mode: str) -> None:
    table = target.model.__table__
    sql_type = sa.JSON() if target.kind == "json" else sa.Text()
    for pk_value, value in pending:
        new_value = value if mode == "encrypt" else sa.literal(value, type_=sql_type)  # revert bypasses the type
        await session.execute(sa.update(table).where(pk == pk_value).values({target.column: new_value}))
    await session.flush()

    expected = dict(pending)
    check = (await session.execute(
        sa.select(pk, _raw_col(target)).where(pk.in_(list(expected)))
    )).all()
    for pk_value, raw_value in check:
        if mode == "encrypt":
            plain = _decrypt(raw_value) if isinstance(raw_value, str) else None
            got = None if plain is None else (json.loads(plain) if target.kind == "json" else plain)
            ok = got is not None and got == expected[pk_value]
        else:
            ok = (not (isinstance(raw_value, str) and _decrypt(raw_value) is not None)) and raw_value == expected[pk_value]
        if not ok:
            await session.rollback()
            raise RuntimeError(f"Verification failed for {target.label} row {pk_value}; batch rolled back")


async def _process_target(session, target: Target, *, mode: str, apply: bool, batch_size: int) -> Stats:
    table = target.model.__table__
    pk = list(table.primary_key.columns)[0]
    raw = _raw_col(target)
    stats = Stats(target.label)
    last_pk = None
    while True:
        stmt = sa.select(pk, raw).order_by(pk).limit(batch_size)
        if last_pk is not None:
            stmt = stmt.where(pk > last_pk)
        if apply:
            stmt = stmt.with_for_update()  # serialize with live app writes (ignored by SQLite)
        rows = (await session.execute(stmt)).all()
        if not rows:
            break
        pending = []
        for pk_value, raw_value in rows:
            stats.total += 1
            last_pk = pk_value
            if raw_value is None:
                stats.null += 1
                continue
            is_token_like = isinstance(raw_value, str) and raw_value.startswith(_TOKEN_PREFIX)
            decrypted = _decrypt(raw_value) if isinstance(raw_value, str) else None
            if decrypted is not None:
                stats.encrypted += 1
                if mode == "revert":
                    pending.append((pk_value, json.loads(decrypted) if target.kind == "json" else decrypted))
            elif is_token_like:
                stats.undecryptable += 1
                logger.error("Undecryptable Fernet-looking value in %s id=%s; skipped", target.label, pk_value)
            else:
                stats.plaintext += 1
                if mode == "encrypt":
                    pending.append((pk_value, raw_value))
        if apply and pending:
            await _write_and_verify(session, target, pk, pending, mode)
            stats.updated += len(pending)
        if apply:
            await session.commit()  # releases the batch's row locks
    if not apply:
        await session.rollback()
    return stats


async def run_backfill(session: AsyncSession, *, mode: str = "encrypt", apply: bool = False, batch_size: int = 100) -> List[Stats]:
    if mode not in ("encrypt", "revert"):
        raise ValueError("mode must be 'encrypt' or 'revert'")
    results = []
    for target in TARGETS:
        stats = await _process_target(session, target, mode=mode, apply=apply, batch_size=batch_size)
        logger.info("%s: total=%d null=%d encrypted=%d plaintext=%d undecryptable=%d updated=%d",
                    stats.label, stats.total, stats.null, stats.encrypted, stats.plaintext, stats.undecryptable, stats.updated)
        results.append(stats)
    return results

