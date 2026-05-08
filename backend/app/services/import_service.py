import csv
import hashlib
import io
import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine as sqlalchemy_async_engine
from app.services.staging_bootstrap_sql import (
    run_create_extensions_autocommit,
    staging_migration_extension_and_rest,
)
from app.services.staging_row_validation import collect_staging_row_issues, row_is_effectively_blank


EXPECTED_COLUMNS = [
    "local_student_id",
    "university_code",
    "program_code",
    "program_name",
    "specialization_edu_code",
    "specialization_edu_name",
    "birth_year",
    "graduation_year",
    "gender",
    "is_employed",
    "company_name",
    "inn",
    "industry_name",
    "position",
    "salary",
    "specialization_work_code",
    "specialization_work_name",
    "hire_date",
    "works_by_specialty",
]

ALLOWED_IGNORED_UPLOAD_COLUMNS = frozenset({"task_id"})


def _detect_csv_delimiter(first_line: str) -> str:
    """Выбор ',' или ';' по первой строке (обычно заголовки)."""
    line = first_line.lstrip("\ufeff")
    if not line.strip():
        return ","
    semicolons = line.count(";")
    commas = line.count(",")
    if semicolons > commas:
        return ";"
    return ","


def parse_csv_content(raw_content: str) -> list[dict]:
    if not raw_content or not raw_content.strip():
        raise ValueError("CSV headers are missing")

    sniff = raw_content.lstrip("\ufeff")
    first_nl = sniff.find("\n")
    header_line = sniff if first_nl == -1 else sniff[:first_nl]
    delimiter = _detect_csv_delimiter(header_line)

    reader = csv.DictReader(io.StringIO(raw_content), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV headers are missing")
    names = []
    for n in reader.fieldnames:
        if n is None:
            continue
        s = str(n).strip().lstrip("\ufeff")
        if s != "":
            names.append(s)
    reader.fieldnames = names
    header_set = set(names)
    missing = [col for col in EXPECTED_COLUMNS if col not in header_set]
    if missing:
        raise ValueError(f"CSV missing columns: {', '.join(missing)}")
    unknown = sorted(header_set.difference(set(EXPECTED_COLUMNS)).difference(ALLOWED_IGNORED_UPLOAD_COLUMNS))
    if unknown:
        raise ValueError(f"CSV has unexpected columns (remove or rename): {', '.join(unknown)}")
    return [{str(k).strip().lstrip("\ufeff"): v for k, v in row.items()} for row in reader]


def build_student_hash(local_student_id: str, university_code: str) -> str:
    """Референсная реализация student_hash (должна совпадать с триггером staging.stg_graduates_set_student_hash в БД).

    Канонический алгоритм:
    - S — строка ``local_student_id`` после удаления пробелов по краям;
    - U — строка ``university_code`` после удаления пробелов по краям;
    - B — последовательность байтов UTF-8(S), затем UTF-8(U), склеенные подряд без разделителя;
    - ``student_hash = hex_lower(SHA-256(B))`` — шестнадцатеричная запись дайджеста из 64 символов.

    В PostgreSQL триггер на ``staging.stg_graduates`` пересчитывает поле перед INSERT и при изменении
    ``local_student_id`` / ``university_code``. Загрузка CSV не должна передавать ``student_hash`` и
    ``load_timestamp``: их задаёт СУБД (штатно — DEFAULT и триггер; нужно расширение ``pgcrypto``).
    См. файл ``migrations/staging_stg_graduates_student_hash_trigger.sql``.
    """
    sid = str(local_student_id).strip()
    uc = str(university_code).strip()
    return hashlib.sha256(f"{sid}{uc}".encode("utf-8")).hexdigest()


def _empty(val: object | None) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _parse_int(val: object | None) -> int | None:
    if _empty(val):
        return None
    s = str(val).strip().replace(" ", "").replace(",", ".")
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return None


def _parse_bool(val: object | None) -> bool:
    if _empty(val):
        return False
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "да", "д"}:
        return True
    if s in {"0", "false", "f", "no", "n", "нет", "н"}:
        return False
    return False


def _parse_salary(val: object | None) -> Decimal | None:
    if _empty(val):
        return None
    s = str(val).strip().replace(" ", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_hire_date(val: object | None) -> date | None:
    if _empty(val):
        return None
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def normalize_graduate_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Приводит значения строки CSV к типам столбцов staging.stg_graduates."""
    sid = raw.get("local_student_id")
    ucode = raw.get("university_code")
    if sid is None or str(sid).strip() == "" or ucode is None or str(ucode).strip() == "":
        raise ValueError("local_student_id и university_code обязательны")

    return {
        "local_student_id": str(sid).strip(),
        "university_code": str(ucode).strip(),
        "program_code": (None if _empty(raw.get("program_code")) else str(raw["program_code"]).strip()),
        "program_name": (None if _empty(raw.get("program_name")) else str(raw["program_name"]).strip()),
        "specialization_edu_code": (
            None if _empty(raw.get("specialization_edu_code")) else str(raw["specialization_edu_code"]).strip()
        ),
        "specialization_edu_name": (
            None if _empty(raw.get("specialization_edu_name")) else str(raw["specialization_edu_name"]).strip()
        ),
        "birth_year": _parse_int(raw.get("birth_year")),
        "graduation_year": _parse_int(raw.get("graduation_year")),
        "gender": (None if _empty(raw.get("gender")) else str(raw["gender"]).strip()),
        "is_employed": _parse_bool(raw.get("is_employed")),
        "company_name": (None if _empty(raw.get("company_name")) else str(raw["company_name"]).strip()),
        "inn": (None if _empty(raw.get("inn")) else str(raw["inn"]).strip()),
        "industry_name": (None if _empty(raw.get("industry_name")) else str(raw["industry_name"]).strip()),
        "position": (None if _empty(raw.get("position")) else str(raw["position"]).strip()),
        "salary": _parse_salary(raw.get("salary")),
        "specialization_work_code": (
            None if _empty(raw.get("specialization_work_code")) else str(raw["specialization_work_code"]).strip()
        ),
        "specialization_work_name": (
            None if _empty(raw.get("specialization_work_name")) else str(raw["specialization_work_name"]).strip()
        ),
        "hire_date": _parse_hire_date(raw.get("hire_date")),
        "works_by_specialty": _parse_bool(raw.get("works_by_specialty")),
    }


async def _ensure_staging_graduates_auto_pipeline(session: AsyncSession) -> None:
    """Таблица staging.stg_graduates: синхронизация DDL из миграции; расширение pgcrypto — при необходимости в AUTOCOMMIT."""

    await session.execute(text("SET SESSION search_path TO staging, extensions, public, pg_catalog"))

    await session.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
    await session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    await session.execute(text("CREATE SCHEMA IF NOT EXISTS extensions"))
    await session.commit()

    ext_stmts, rest_stmts = staging_migration_extension_and_rest()

    from sqlalchemy.exc import DBAPIError

    if ext_stmts:
        try:
            for stmt in ext_stmts:
                await session.execute(text(stmt))
        except DBAPIError:
            await session.rollback()
            try:
                await run_create_extensions_autocommit(sqlalchemy_async_engine, ext_stmts)
            except DBAPIError as exc:
                pg = getattr(getattr(exc, "orig", None), "pgerror", None) or str(exc)
                raise RuntimeError(
                    "Не удалось активировать расширение PostgreSQL «pgcrypto» (нужно для триггера student_hash).\n"
                    "Выполните под суперпользователем или через панель хостинга (пример для psql, база UNI):\n"
                    "  CREATE SCHEMA IF NOT EXISTS extensions;\n"
                    "  CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;\n"
                    f"Ответ базы: {pg}"
                ) from None
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "Не удалось выполнить CREATE EXTENSION через отдельное соединение (AUTOCOMMIT).\n"
                    f"{type(exc).__name__}: {exc}\n"
                    "Под суперпользователем (пример для psql, база UNI):\n"
                    "  CREATE SCHEMA IF NOT EXISTS extensions;\n"
                    "  CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;"
                ) from exc

    for stmt in rest_stmts:
        try:
            await session.execute(text(stmt))
        except DBAPIError as exc:
            await session.rollback()
            pg = getattr(getattr(exc, "orig", None), "pgerror", None) or str(exc)
            short = stmt.replace("\n", " ").strip()[:280]
            raise RuntimeError(
                "Не удалось применить настройку таблицы staging.stg_graduates.\n"
                f"Фрагмент SQL: «{short}…»\n"
                f"Ответ PostgreSQL: {pg}\n"
                "Проверьте права пользователя или примените файл migrations/staging_stg_graduates_student_hash_trigger.sql "
                "вручную."
            ) from None


async def import_rows_to_staging(session: AsyncSession, rows: list[dict[str, Any]]) -> dict[str, Any]:
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    errors: list[str] = []
    inserted = 0

    await _ensure_staging_graduates_auto_pipeline(session)

    query = text(
        """
        INSERT INTO staging.stg_graduates (
            local_student_id, university_code, program_code, program_name,
            specialization_edu_code, specialization_edu_name, birth_year, graduation_year,
            gender, is_employed, company_name, inn, industry_name, "position", salary,
            specialization_work_code, specialization_work_name, hire_date, works_by_specialty,
            task_id
        ) VALUES (
            :local_student_id, :university_code, :program_code, :program_name,
            :specialization_edu_code, :specialization_edu_name, :birth_year, :graduation_year,
            :gender, :is_employed, :company_name, :inn, :industry_name, :position, :salary,
            :specialization_work_code, :specialization_work_name, :hire_date, :works_by_specialty,
            :task_id
        )
        """
    )

    for idx, raw in enumerate(rows, start=1):
        raw = {str(k).strip().lstrip("\ufeff"): v for k, v in raw.items()}
        raw_row = {col: raw.get(col) for col in EXPECTED_COLUMNS}
        try:
            if row_is_effectively_blank(raw_row, EXPECTED_COLUMNS):
                continue
            row_issues = collect_staging_row_issues(raw_row, idx)
            if row_issues:
                errors.extend(row_issues)
                continue
            row = normalize_graduate_row(raw_row)
            gy = row["graduation_year"]
            if gy is None:
                errors.append(
                    f"Строка {idx}, колонка «graduation_year»: обязательное поле после нормализации пустое"
                )
                continue
            payload = {
                **row,
                "task_id": task_id,
            }
            await session.execute(query, payload)
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Строка {idx}: ошибка БД при записи — {exc}")

    await session.commit()
    return {"task_id": task_id, "inserted": inserted, "errors": errors}


async def _ensure_mart_etl_column(session: AsyncSession) -> None:
    await session.execute(
        text("ALTER TABLE mart.mart_employment_flat ADD COLUMN IF NOT EXISTS etl_updated_at TIMESTAMPTZ")
    )


async def run_etl_for_task(session: AsyncSession, task_id: str) -> dict[str, int]:
    """Staging → DWH (dim_student, fact_employment) → mart для загрузки с указанным task_id."""
    cnt = (
        await session.execute(
            text("SELECT COUNT(*)::int FROM staging.stg_graduates WHERE task_id = :t"),
            {"t": task_id},
        )
    ).scalar_one()
    if int(cnt or 0) == 0:
        raise ValueError(f"Нет строк в staging для task_id={task_id}")

    try:
        await _ensure_mart_etl_column(session)

        dim_sql_upsert = text(
            """
            INSERT INTO dwh.dim_student (student_hash, birth_year, gender, graduation_year)
            SELECT DISTINCT ON (s.student_hash)
                   s.student_hash,
                   s.birth_year,
                   NULLIF(TRIM(s.gender), ''),
                   s.graduation_year
            FROM staging.stg_graduates s
            WHERE s.task_id = :task_id
            ORDER BY s.student_hash, s.load_timestamp DESC NULLS LAST
            ON CONFLICT (student_hash) DO UPDATE SET
                birth_year = EXCLUDED.birth_year,
                gender = EXCLUDED.gender,
                graduation_year = EXCLUDED.graduation_year
            """
        )
        dim_sql_insert_only = text(
            """
            INSERT INTO dwh.dim_student (student_hash, birth_year, gender, graduation_year)
            SELECT DISTINCT ON (s.student_hash)
                   s.student_hash,
                   s.birth_year,
                   NULLIF(TRIM(s.gender), ''),
                   s.graduation_year
            FROM staging.stg_graduates s
            WHERE s.task_id = :task_id
              AND NOT EXISTS (SELECT 1 FROM dwh.dim_student d WHERE d.student_hash = s.student_hash)
            ORDER BY s.student_hash, s.load_timestamp DESC NULLS LAST
            """
        )
        try:
            await session.execute(dim_sql_upsert, {"task_id": task_id})
        except Exception:  # noqa: BLE001
            await session.rollback()
            await session.execute(dim_sql_insert_only, {"task_id": task_id})

        await session.execute(
            text(
                """
                DELETE FROM dwh.fact_employment fe
                WHERE fe.student_hash IN (
                    SELECT student_hash FROM staging.stg_graduates WHERE task_id = :task_id
                )
                """
            ),
            {"task_id": task_id},
        )

        ins_fact = text(
            """
            INSERT INTO dwh.fact_employment (
                student_hash, is_employed, salary, company_name, industry_name, works_by_specialty
            )
            SELECT s.student_hash,
                   COALESCE(s.is_employed, false),
                   s.salary,
                   NULLIF(TRIM(s.company_name), ''),
                   NULLIF(TRIM(s.industry_name), ''),
                   COALESCE(s.works_by_specialty, false)
            FROM staging.stg_graduates s
            WHERE s.task_id = :task_id
            """
        )
        r_fe = await session.execute(ins_fact, {"task_id": task_id})
        fact_n = r_fe.rowcount if r_fe.rowcount is not None else int(cnt or 0)

        await session.execute(
            text(
                """
                DELETE FROM mart.mart_employment_flat m
                WHERE m.student_hash IN (
                    SELECT student_hash FROM staging.stg_graduates WHERE task_id = :task_id
                )
                """
            ),
            {"task_id": task_id},
        )

        ins_mart = text(
            """
            INSERT INTO mart.mart_employment_flat (
                student_hash,
                graduation_year,
                university_name,
                university_id,
                university_code,
                region_name,
                program_code,
                program_name,
                is_employed,
                salary,
                industry_name,
                company_name,
                works_by_specialty,
                gender,
                birth_year,
                etl_updated_at
            )
            SELECT DISTINCT ON (s.student_hash)
                s.student_hash,
                s.graduation_year,
                COALESCE(NULLIF(TRIM(u.university_name), ''), TRIM(s.university_code)),
                u.university_id,
                TRIM(BOTH FROM COALESCE(u.university_code, s.university_code)),
                COALESCE(NULLIF(TRIM(BOTH FROM r.region_name), ''), '—'),
                COALESCE(NULLIF(TRIM(s.program_code), ''), ''),
                NULLIF(TRIM(s.program_name), ''),
                COALESCE(s.is_employed, false),
                s.salary,
                NULLIF(TRIM(s.industry_name), ''),
                NULLIF(TRIM(s.company_name), ''),
                COALESCE(s.works_by_specialty, false),
                NULLIF(TRIM(s.gender), ''),
                s.birth_year,
                timezone('utc', now())
            FROM staging.stg_graduates s
            LEFT JOIN dwh.dim_university u ON TRIM(BOTH FROM UPPER(COALESCE(u.university_code, ''))) =
                TRIM(BOTH FROM UPPER(COALESCE(s.university_code, '')))
            LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
            LEFT JOIN dwh.dim_region r ON r.region_id = c.region_id
            WHERE s.task_id = :task_id
            ORDER BY s.student_hash, s.load_timestamp DESC NULLS LAST
            """
        )
        r_mart = await session.execute(ins_mart, {"task_id": task_id})
        mart_n = r_mart.rowcount if r_mart.rowcount is not None else int(cnt or 0)

        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return {"staging_rows": int(cnt or 0), "fact_rows": int(fact_n or 0), "mart_rows": int(mart_n or 0)}


async def transfer_staging_to_dwh(session: AsyncSession, task_id: str | None = None) -> dict[str, int]:
    """ETL последней загрузки из staging или конкретного task_id."""
    if task_id is None:
        tid = (
            await session.execute(
                text(
                    """
                    SELECT task_id FROM staging.stg_graduates
                    ORDER BY load_timestamp DESC NULLS LAST, student_hash LIMIT 1
                    """
                )
            )
        ).scalar_one_or_none()
        task_id = str(tid) if tid else ""
    else:
        task_id = task_id.strip()
    if not task_id:
        raise ValueError("В staging нет данных для переноса.")
    return await run_etl_for_task(session, task_id)
