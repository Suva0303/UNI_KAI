"""История загрузок CSV/staging: метаданные, логи и ошибки (public API — admin)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

_LOGGER = logging.getLogger(__name__)

SEED_DEMO_TASK_ID = "task-seed-demo"


def demo_mart_filter_sql(alias: str = "m") -> str:
    """Фильтр демо-строк mart (как в delete_demo_mart_rows)."""
    return (
        f"({alias}.university_code LIKE 'DEMO%%' OR {alias}.university_code IN ('MGU', 'SPbGU', 'MIPT', 'ITMO'))"
    )


IMPORT_BATCH_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS staging.import_batch_audit (
    task_id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL,
    filename TEXT,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', NOW()),
    rows_inserted INTEGER NOT NULL DEFAULT 0,
    etl_fact_rows INTEGER,
    etl_mart_rows INTEGER,
    etl_json JSONB,
    errors_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    logs_json JSONB NOT NULL DEFAULT '[]'::jsonb
);
"""


async def ensure_import_audit_table(session: AsyncSession) -> None:
    await session.execute(text(IMPORT_BATCH_AUDIT_DDL))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def persist_import_batch_audit(
    session: AsyncSession,
    *,
    task_id: str,
    source_kind: str,
    filename: str | None,
    rows_inserted: int,
    errors: list[str],
    logs: list[dict[str, Any]],
    etl_fact_rows: int | None,
    etl_mart_rows: int | None,
    etl_full: dict[str, Any] | None,
) -> None:
    await ensure_import_audit_table(session)
    etl_blob = dict(etl_full) if etl_full else {}
    await session.execute(
        text(
            """
            INSERT INTO staging.import_batch_audit (
                task_id, source_kind, filename, logged_at, rows_inserted,
                etl_fact_rows, etl_mart_rows, etl_json, errors_json, logs_json
            ) VALUES (
                :task_id, :source_kind, :filename, timezone('utc', NOW()), :rows_inserted,
                :etl_fact_rows, :etl_mart_rows, CAST(:etl_json AS jsonb),
                CAST(:errors_json AS jsonb), CAST(:logs_json AS jsonb)
            )
            ON CONFLICT (task_id) DO UPDATE SET
                source_kind = EXCLUDED.source_kind,
                filename = COALESCE(EXCLUDED.filename, staging.import_batch_audit.filename),
                logged_at = EXCLUDED.logged_at,
                rows_inserted = EXCLUDED.rows_inserted,
                etl_fact_rows = EXCLUDED.etl_fact_rows,
                etl_mart_rows = EXCLUDED.etl_mart_rows,
                etl_json = EXCLUDED.etl_json,
                errors_json = EXCLUDED.errors_json,
                logs_json = EXCLUDED.logs_json
            """
        ),
        {
            "task_id": task_id,
            "source_kind": source_kind,
            "filename": (filename.strip()[:500] if filename and str(filename).strip() else None),
            "rows_inserted": int(rows_inserted),
            "etl_fact_rows": etl_fact_rows,
            "etl_mart_rows": etl_mart_rows,
            "etl_json": json.dumps(etl_blob, ensure_ascii=False),
            "errors_json": json.dumps(errors, ensure_ascii=False),
            "logs_json": json.dumps(logs, ensure_ascii=False),
        },
    )


async def demo_mart_row_count(session: AsyncSession) -> int:
    filt = demo_mart_filter_sql("m")
    try:
        n = (
            await session.execute(
                text(f"SELECT COUNT(*)::bigint FROM mart.mart_employment_flat m WHERE {filt}"),
            )
        ).scalar_one()
        return int(n or 0)
    except Exception:
        await session.rollback()
        return 0


async def ensure_seed_demo_audit_if_mart_nonempty(session: AsyncSession) -> None:
    """Бэкомпат: в mart уже есть демо-строки, но раньше они не заносились в import_batch_audit."""
    await ensure_import_audit_table(session)
    cnt = await demo_mart_row_count(session)
    if cnt <= 0:
        return
    existing = (
        await session.execute(
            text("SELECT 1 FROM staging.import_batch_audit WHERE task_id = :t LIMIT 1"),
            {"t": SEED_DEMO_TASK_ID},
        )
    ).first()
    if existing:
        return
    demo_logs = [
        {
            "at": utc_now_iso(),
            "level": "info",
            "msg": (
                "Демонстрационные строки уже есть в mart; создана синтетическая запись журнала. "
                "Просмотр «как в staging» подставляет те же строки из mart по демон-критерию."
            ),
        },
    ]
    try:
        await persist_import_batch_audit(
            session,
            task_id=SEED_DEMO_TASK_ID,
            source_kind="demo-seed",
            filename=None,
            rows_inserted=cnt,
            errors=[],
            logs=demo_logs,
            etl_fact_rows=None,
            etl_mart_rows=cnt,
            etl_full={"kind": "backfill_audit_from_existing_mart"},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        _LOGGER.warning("Не удалось создать журнал demo-seed (import_batch_audit)", exc_info=True)


async def count_import_batches(session: AsyncSession) -> int:
    """Число уникальных task_id по staging ∪ аудит-журналу."""
    await ensure_import_audit_table(session)
    try:
        n = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint FROM (
                        SELECT DISTINCT task_id FROM staging.stg_graduates
                        UNION
                        SELECT task_id FROM staging.import_batch_audit
                    ) x
                    """
                )
            )
        ).scalar_one()
        return int(n or 0)
    except Exception:
        await session.rollback()
        try:
            n2 = (
                await session.execute(
                    text("SELECT COUNT(*)::bigint FROM staging.import_batch_audit")
                )
            ).scalar_one()
            return int(n2 or 0)
        except Exception:
            await session.rollback()
            return 0


async def list_import_batches(
    session: AsyncSession,
    *,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    await ensure_import_audit_table(session)
    try:
        rows = (
            await session.execute(
                text(
                    """
                    WITH all_tasks AS (
                        SELECT DISTINCT task_id AS task_id FROM staging.stg_graduates
                        UNION
                        SELECT a.task_id FROM staging.import_batch_audit a
                    ),
                    agg AS (
                        SELECT s.task_id,
                               COUNT(*)::bigint AS rows_in_staging,
                               MIN(s.load_timestamp) AS first_load_at,
                               MAX(s.load_timestamp) AS last_load_at
                        FROM staging.stg_graduates s
                        GROUP BY s.task_id
                    )
                    SELECT ut.task_id,
                           COALESCE(agg.rows_in_staging, 0)::bigint AS rows_in_staging,
                           agg.first_load_at,
                           agg.last_load_at,
                           a.source_kind AS audit_source_kind,
                           a.filename AS audit_filename,
                           a.logged_at AS audit_logged_at,
                           a.rows_inserted AS audit_rows_inserted,
                           a.etl_fact_rows AS audit_etl_fact,
                           a.etl_mart_rows AS audit_etl_mart,
                           CASE WHEN a.task_id IS NOT NULL
                               THEN jsonb_array_length(COALESCE(a.errors_json, '[]'::jsonb))
                               ELSE 0 END AS audit_error_lines,
                           CASE WHEN a.task_id IS NOT NULL
                               THEN jsonb_array_length(COALESCE(a.logs_json, '[]'::jsonb))
                               ELSE 0 END AS audit_log_lines
                    FROM all_tasks ut
                    LEFT JOIN agg ON agg.task_id = ut.task_id
                    LEFT JOIN staging.import_batch_audit a ON a.task_id = ut.task_id
                    ORDER BY COALESCE(agg.last_load_at, a.logged_at) DESC NULLS LAST, ut.task_id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset},
            )
        ).mappings().all()
        return [dict(r) for r in rows]
    except SQLAlchemyError:
        await session.rollback()
        rows_audit = (
            await session.execute(
                text(
                    """
                    SELECT a.task_id AS task_id,
                           0::bigint AS rows_in_staging,
                           NULL::timestamptz AS first_load_at,
                           a.logged_at AS last_load_at,
                           a.source_kind AS audit_source_kind,
                           a.filename AS audit_filename,
                           a.logged_at AS audit_logged_at,
                           a.rows_inserted AS audit_rows_inserted,
                           a.etl_fact_rows AS audit_etl_fact,
                           a.etl_mart_rows AS audit_etl_mart,
                           jsonb_array_length(COALESCE(a.errors_json, '[]'::jsonb)) AS audit_error_lines,
                           jsonb_array_length(COALESCE(a.logs_json, '[]'::jsonb)) AS audit_log_lines
                    FROM staging.import_batch_audit a
                    ORDER BY a.logged_at DESC NULLS LAST, a.task_id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset},
            )
        ).mappings().all()
        return [dict(r) for r in rows_audit]


async def get_import_batch_audit_row(session: AsyncSession, task_id: str) -> dict[str, Any] | None:
    await ensure_import_audit_table(session)
    row = (
        await session.execute(
            text(
                """
                SELECT task_id, source_kind, filename, logged_at, rows_inserted,
                       etl_fact_rows, etl_mart_rows, etl_json, errors_json, logs_json
                FROM staging.import_batch_audit
                WHERE task_id = :t
                """
            ),
            {"t": task_id.strip()},
        )
    ).mappings().first()
    if not row:
        return None
    d = dict(row)
    for key in ("errors_json", "logs_json", "etl_json"):
        v = d.get(key)
        if isinstance(v, memoryview):
            d[key] = v.tobytes().decode()
    return d


def jsonb_decode_list(val: Any) -> list[Any]:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        return [val]
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            return []
    return []


async def get_batch_staging_aggregate(session: AsyncSession, task_id: str) -> dict[str, Any] | None:
    tid = task_id.strip()
    if tid == SEED_DEMO_TASK_ID:
        filt = demo_mart_filter_sql("m")
        try:
            row = (
                await session.execute(
                    text(
                        f"""
                        SELECT :tid AS task_id,
                               COUNT(*)::bigint AS rows_in_staging,
                               MIN(m.etl_updated_at) AS first_load_at,
                               MAX(m.etl_updated_at) AS last_load_at
                        FROM mart.mart_employment_flat m
                        WHERE {filt}
                        """
                    ),
                    {"tid": SEED_DEMO_TASK_ID},
                )
            ).mappings().first()
        except SQLAlchemyError:
            await session.rollback()
            return None
        if not row or int(row.get("rows_in_staging") or 0) <= 0:
            return None
        return dict(row)
    row = (
        await session.execute(
            text(
                """
                SELECT task_id,
                       COUNT(*)::bigint AS rows_in_staging,
                       MIN(load_timestamp) AS first_load_at,
                       MAX(load_timestamp) AS last_load_at
                FROM staging.stg_graduates
                WHERE task_id = :t
                GROUP BY task_id
                """
            ),
            {"t": tid},
        )
    ).mappings().first()
    return dict(row) if row else None


async def list_seed_demo_rows_from_mart(
    session: AsyncSession,
    *,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    filt = demo_mart_filter_sql("m")
    try:
        total_q = (
            await session.execute(
                text(f"SELECT COUNT(*)::bigint FROM mart.mart_employment_flat m WHERE {filt}"),
            )
        ).scalar_one()
        total = int(total_q or 0)
        if total == 0:
            return [], 0
        rows_raw = (
            await session.execute(
                text(
                    f"""
                    SELECT m.student_hash, m.university_code, m.program_code, m.program_name,
                           m.birth_year, m.graduation_year, m.gender, m.is_employed, m.company_name,
                           m.industry_name, m.salary, m.works_by_specialty, m.etl_updated_at
                    FROM mart.mart_employment_flat m
                    WHERE {filt}
                    ORDER BY m.student_hash
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset},
            )
        ).mappings().all()
    except SQLAlchemyError:
        await session.rollback()
        return [], 0

    out: list[dict[str, Any]] = []
    for i, raw in enumerate(rows_raw):
        r = dict(raw)
        sh = str(r.get("student_hash") or "")
        out.append(
            {
                "id": offset + i + 1,
                "task_id": SEED_DEMO_TASK_ID,
                "local_student_id": (sh[:40] if sh else ""),
                "university_code": r.get("university_code"),
                "program_code": r.get("program_code"),
                "program_name": r.get("program_name"),
                "specialization_edu_code": None,
                "specialization_edu_name": None,
                "birth_year": r.get("birth_year"),
                "graduation_year": r.get("graduation_year"),
                "gender": r.get("gender"),
                "is_employed": r.get("is_employed"),
                "company_name": r.get("company_name"),
                "inn": None,
                "industry_name": r.get("industry_name"),
                "position": None,
                "salary": r.get("salary"),
                "specialization_work_code": None,
                "specialization_work_name": None,
                "hire_date": None,
                "works_by_specialty": r.get("works_by_specialty"),
                "student_hash": sh,
                "load_timestamp": r.get("etl_updated_at"),
            }
        )
    return out, total


async def list_staging_rows_for_task(
    session: AsyncSession,
    task_id: str,
    *,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    tid = task_id.strip()
    if tid == SEED_DEMO_TASK_ID:
        return await list_seed_demo_rows_from_mart(session, offset=offset, limit=limit)

    total_q = (
        await session.execute(
            text("SELECT COUNT(*)::bigint FROM staging.stg_graduates WHERE task_id = :t"),
            {"t": tid},
        )
    ).scalar_one()
    total = int(total_q or 0)
    if total == 0:
        return [], 0
    rows = (
        await session.execute(
            text(
                """
                SELECT id, task_id, local_student_id, university_code, program_code, program_name,
                       specialization_edu_code, specialization_edu_name, birth_year, graduation_year,
                       gender, is_employed, company_name, inn, industry_name, "position", salary,
                       specialization_work_code, specialization_work_name, hire_date, works_by_specialty,
                       student_hash, load_timestamp
                FROM staging.stg_graduates
                WHERE task_id = :t
                ORDER BY id ASC NULLS LAST
                LIMIT :limit OFFSET :offset
                """
            ),
            {"t": tid, "limit": limit, "offset": offset},
        )
    ).mappings().all()
    return [dict(r) for r in rows], total


