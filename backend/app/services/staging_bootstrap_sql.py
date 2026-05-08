"""Загрузка и разбор DDL миграции staging (триггер student_hash, значения по умолчанию)."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import asyncpg
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

_SCHEMAS_BEFORE_EXTENSION_SQL: tuple[str, ...] = (
    "CREATE SCHEMA IF NOT EXISTS staging",
    "CREATE SCHEMA IF NOT EXISTS public",
    "CREATE SCHEMA IF NOT EXISTS extensions",
)


def postgres_statements_for_staging_migration() -> list[str]:
    """
    Возвращает отдельные SQL-выражения из migrations/staging_stg_graduates_student_hash_trigger.sql
    (учёт доллар-кавычек $$ для plpgsql и обычных '...').
    """
    mig = Path(__file__).resolve().parents[2] / "migrations" / "staging_stg_graduates_student_hash_trigger.sql"
    try:
        raw = mig.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Не найден файл миграции staging для авто-бутстрапа. "
            "Проверьте, что в деплое присутствует каталог backend/migrations и файл "
            f"staging_stg_graduates_student_hash_trigger.sql по пути: {mig}"
        ) from exc
    raw = re.sub(r"^\s*--[^\n]*\n?", "", raw, flags=re.MULTILINE)
    stmts: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(raw)
    dollar_tag: str | None = None
    while i < n:
        ch = raw[i]
        if dollar_tag is not None:
            if raw.startswith(dollar_tag, i):
                buf.append(raw[i : i + len(dollar_tag)])
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(ch)
            i += 1
            continue
        if ch == "'":
            buf.append(ch)
            i += 1
            while i < n:
                c = raw[i]
                if c != "'":
                    buf.append(c)
                    i += 1
                    continue
                if i + 1 < n and raw[i + 1] == "'":
                    buf.append("''")
                    i += 2
                    continue
                buf.append("'")
                i += 1
                break
            continue
        if ch == "$":
            j = i + 1
            while j < n and raw[j] != "$":
                j += 1
            if j >= n:
                buf.append(ch)
                i += 1
                continue
            opening = raw[i : j + 1]
            buf.append(opening)
            dollar_tag = opening
            i = j + 1
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            buf.clear()
            if stmt:
                stmts.append(stmt)
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def staging_migration_extension_and_rest() -> tuple[list[str], list[str]]:
    """CREATE EXTENSION — отдельно (удобнее в AUTOCOMMIT); остальное — в обычной транзакции сессии."""
    stmts = postgres_statements_for_staging_migration()
    ext = [s for s in stmts if s.upper().startswith("CREATE EXTENSION")]
    rest = [s for s in stmts if not s.upper().startswith("CREATE EXTENSION")]
    return ext, rest


def _run_create_extension_sync_autocommit(engine: Engine, stmt: str) -> None:
    """Синхронное соединение: для bind от AsyncSession.get_bind() это обычный Engine."""
    with engine.connect() as conn:
        ac = conn.execution_options(isolation_level="AUTOCOMMIT")
        ac.execute(text("SET SESSION search_path TO staging, extensions, public, pg_catalog"))
        for s in _SCHEMAS_BEFORE_EXTENSION_SQL:
            ac.execute(text(s))
        ac.execute(text(stmt))


async def _ensure_schemas_asyncpg(conn: asyncpg.Connection) -> None:
    for s in _SCHEMAS_BEFORE_EXTENSION_SQL:
        await conn.execute(s)


async def _create_extension_asyncpg(engine: AsyncEngine, stmt: str) -> None:
    """DDL расширения напрямую через asyncpg (обходит нюансы AsyncConnection/SQLAlchemy)."""
    if engine.url.drivername != "postgresql+asyncpg":
        raise ValueError(f"Ожидался postgresql+asyncpg, указано «{engine.url.drivername}»")
    dsn = engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    conn = await asyncpg.connect(
        dsn,
        server_settings={"search_path": "staging,extensions,public,pg_catalog"},
    )
    try:
        await _ensure_schemas_asyncpg(conn)
        await conn.execute(stmt)
    finally:
        await conn.close()


async def run_create_extensions_autocommit(bind: Engine | AsyncEngine, stmts: list[str]) -> None:
    """CREATE EXTENSION вне транзакции приложения: async — AsyncEngine/asyncpg или SQLAlchemy; sync — Engine в thread."""
    for stmt in stmts:
        if isinstance(bind, AsyncEngine):
            if bind.url.drivername == "postgresql+asyncpg":
                await _create_extension_asyncpg(bind, stmt)
                continue
            async with bind.connect() as conn:
                ac = await conn.execution_options(isolation_level="AUTOCOMMIT")
                await ac.execute(text("SET SESSION search_path TO staging, extensions, public, pg_catalog"))
                for s in _SCHEMAS_BEFORE_EXTENSION_SQL:
                    await ac.execute(text(s))
                await ac.execute(text(stmt))
        elif isinstance(bind, Engine):
            await asyncio.to_thread(_run_create_extension_sync_autocommit, bind, stmt)
        else:
            raise TypeError(
                f"run_create_extensions_autocommit: ожидался Engine или AsyncEngine, получено {type(bind)!r}"
            )
