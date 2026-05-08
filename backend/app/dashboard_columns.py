"""Проверка колонок и выражений для mart.mart_employment_flat."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def mart_has_column(session: AsyncSession, column_name: str) -> bool:
    r = (
        await session.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'mart'
                  AND table_name = 'mart_employment_flat'
                  AND column_name = :col
                LIMIT 1
                """
            ),
            {"col": column_name},
        )
    ).first()
    return r is not None


def employment_specialty_predicate(has_works_by_specialty: bool) -> str:
    """SQL boolean expression for «трудоустройство по специальности»."""
    if has_works_by_specialty:
        return "(m.is_employed AND COALESCE(m.works_by_specialty, false))"
    return "(m.is_employed)"


def mart_resolved_industry_sql_expr(m_alias: str = "m") -> str:
    """
    Подпись отрасли для диаграмм: значение из витрины; если пусто — грубая группа по коду
    направления (как в app.services.seed_dashboard._industry_for_program), чтобы не терять
    трудоустроенных с незаполненным industry_name.
    """
    tpc = f"TRIM(BOTH FROM {m_alias}.program_code)"
    return f"""(
        COALESCE(
            NULLIF(TRIM(BOTH FROM {m_alias}.industry_name), ''),
            CASE
                WHEN {tpc} LIKE '09.%' OR {tpc} LIKE '10.%' OR {tpc} LIKE '01.03%' THEN
                    'Информационные технологии'
                WHEN {tpc} LIKE '31.%' OR {tpc} LIKE '32.%' THEN
                    'Здравоохранение'
                WHEN {tpc} LIKE '38.%' OR {tpc} LIKE '27.%' THEN
                    'Финансы и страхование'
                WHEN NULLIF({tpc}, '') IS NOT NULL THEN
                    'Образование'
                ELSE 'Отрасль не указана'
            END
        )
    )"""


async def mart_university_join_condition(
    session: AsyncSession,
    *,
    m_alias: str = "m",
    u_alias: str = "u",
) -> str:
    """Связь строк витрины со справочником вузов (id, код или точное имя)."""
    parts: list[str] = []
    if await mart_has_column(session, "university_id"):
        parts.append(f"{m_alias}.university_id = {u_alias}.university_id")
    parts.append(f"TRIM(BOTH FROM {m_alias}.university_name) = TRIM(BOTH FROM {u_alias}.university_name)")
    if await mart_has_column(session, "university_code"):
        parts.append(
            f"({m_alias}.university_code IS NOT NULL AND TRIM(BOTH FROM {m_alias}.university_code) = "
            f"TRIM(BOTH FROM {u_alias}.university_code))"
        )
    return "(" + " OR ".join(parts) + ")"


async def mart_university_scope_and(
    session: AsyncSession,
    *,
    university_id: int,
    params: dict,
    param_key: str = "_mart_scope_uni_id",
    m_alias: str = "m",
) -> str:
    """Фрагмент AND … — все строки mart, относящиеся к вузу (как JOIN в профиле вуза)."""
    uni_join = await mart_university_join_condition(session, m_alias=m_alias, u_alias="u")
    params[param_key] = university_id
    return (
        f"AND EXISTS (SELECT 1 FROM dwh.dim_university u "
        f"WHERE u.university_id = :{param_key} AND {uni_join})"
    )
