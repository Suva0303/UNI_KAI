import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboard_columns import (
    employment_specialty_predicate,
    mart_has_column,
    mart_resolved_industry_sql_expr,
    mart_university_join_condition,
    mart_university_scope_and,
)
from app.dashboard_filters import education_level_options_public, filter_where_sql
from app.config import settings
from app.database import get_db
from app.schemas.public import PublicStats
from app.services.seed_reference_universities import seed_reference_universities

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public"])

RATING_WEIGHT_EMPLOYED_COUNT = 0.35
RATING_WEIGHT_SPECIALTY_RATE = 0.35
RATING_WEIGHT_AVG_SALARY = 0.30


@router.get("/stats", response_model=PublicStats)
async def public_stats(db: AsyncSession = Depends(get_db)) -> PublicStats:
    stats = (
        await db.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM dwh.dim_university) AS universities_total,
                    COALESCE((SELECT AVG(salary) FROM dwh.fact_employment WHERE is_employed = true), 0) AS avg_salary,
                    COALESCE((
                        SELECT AVG(CASE WHEN is_employed THEN 100 ELSE 0 END)
                        FROM dwh.fact_employment
                    ), 0) AS employment_rate,
                    COALESCE((
                        SELECT COUNT(*) FROM dwh.dim_student
                        WHERE graduation_year = (SELECT MAX(graduation_year) FROM dwh.dim_student)
                    ), 0) AS graduates_last_year
                """
            )
        )
    ).mappings().first()
    top_universities = (
        await db.execute(
            text(
                """
                SELECT university_name, ROUND(AVG(salary)::numeric, 2) AS avg_salary
                FROM mart.mart_employment_flat
                WHERE is_employed = true AND salary IS NOT NULL
                GROUP BY university_name
                ORDER BY avg_salary DESC
                LIMIT 10
                """
            )
        )
    ).mappings().all()
    regions = (
        await db.execute(
            text(
                """
                SELECT region_name,
                       ROUND(AVG(CASE WHEN is_employed THEN 100 ELSE 0 END)::numeric, 2) AS employment_rate
                FROM mart.mart_employment_flat
                GROUP BY region_name
                ORDER BY employment_rate DESC
                LIMIT 10
                """
            )
        )
    ).mappings().all()
    return PublicStats(
        **dict(stats),
        top_universities_salary=[dict(x) for x in top_universities],
        regional_employment=[dict(x) for x in regions],
    )


@router.get("/universities-meta")
async def public_universities_meta(db: AsyncSession = Depends(get_db)) -> dict:
    """Справочник вузов (dim_university), число вузов в mart и год актуальности витрины."""
    try:
        catalog_total = int(
            (await db.execute(text("SELECT COUNT(*)::int FROM dwh.dim_university"))).scalar_one() or 0
        )
    except Exception:  # noqa: BLE001
        await db.rollback()
        catalog_total = 0
    try:
        uni_join = await mart_university_join_condition(db, m_alias="m", u_alias="u")
        with_mart = int(
            (
                await db.execute(
                    text(
                        f"""
                        SELECT COUNT(*)::int
                        FROM dwh.dim_university u
                        WHERE EXISTS (SELECT 1 FROM mart.mart_employment_flat m WHERE {uni_join})
                        """
                    )
                )
            ).scalar_one()
            or 0
        )
    except Exception:  # noqa: BLE001
        await db.rollback()
        with_mart = 0
    try:
        y = (await db.execute(text("SELECT COALESCE(MAX(graduation_year), EXTRACT(YEAR FROM CURRENT_DATE)::int) FROM mart.mart_employment_flat"))).scalar_one()
        data_year = int(y) if y is not None else 0
    except Exception:  # noqa: BLE001
        await db.rollback()
        data_year = 0
    return {
        "universities_total": catalog_total,
        "universities_with_mart": with_mart,
        "data_year": data_year,
        "education_levels": education_level_options_public(),
    }


async def universities_browse(
    db: AsyncSession,
    *,
    only_with_mart: bool,
    page: int,
    page_size: int,
    search: str | None,
    region_id: int | None,
    sort: str,
) -> dict:
    """
    Список вузов из dim_university + агрегаты mart (LEFT LATERAL).
    only_with_mart=True — как публичная витрина: только вузы с хотя бы одной строкой в mart.
    only_with_mart=False — полный справочник для админки.
    """
    uni_join_m = await mart_university_join_condition(db, m_alias="m", u_alias="u")
    uni_join_mx = await mart_university_join_condition(db, m_alias="mx", u_alias="u")
    has_wbs = await mart_has_column(db, "works_by_specialty")
    spec_pred = employment_specialty_predicate(has_wbs)
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    where_parts: list[str] = (
        [f"EXISTS (SELECT 1 FROM mart.mart_employment_flat m WHERE {uni_join_m})"]
        if only_with_mart
        else ["TRUE"]
    )
    if search and str(search).strip():
        where_parts.append(
            "(u.university_name ILIKE :search OR COALESCE(c.city_name, '') ILIKE :search OR COALESCE(r.region_name, '') ILIKE :search)"
        )
        params["search"] = f"%{search.strip()}%"
    if region_id is not None:
        where_parts.append(
            f"""
            EXISTS (
                SELECT 1 FROM mart.mart_employment_flat mx
                WHERE ({uni_join_mx})
                  AND mx.region_name = (
                      SELECT s.region_name FROM (
                          SELECT DISTINCT region_name,
                                 ROW_NUMBER() OVER (ORDER BY region_name)::int AS rid
                          FROM mart.mart_employment_flat
                          WHERE region_name IS NOT NULL AND TRIM(region_name) <> ''
                      ) s
                      WHERE s.rid = :region_filter_id
                  )
            )
            """.strip().replace("\n", " ")
        )
        params["region_filter_id"] = region_id
    where_sql = " AND ".join(where_parts)
    universities_body = f"""
        FROM dwh.dim_university u
        LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
        LEFT JOIN dwh.dim_region r ON r.region_id = c.region_id
        LEFT JOIN LATERAL (
            SELECT ROUND(AVG(m.salary) FILTER (WHERE m.is_employed = true AND m.salary IS NOT NULL)::numeric, 0)::float AS avg_sal,
                   ROUND(AVG(CASE WHEN m.is_employed THEN 100.0 ELSE 0.0 END)::numeric, 1)::float AS emp_rate,
                   COUNT(*) FILTER (WHERE m.is_employed)::int AS employed_count,
                   ROUND(AVG(CASE WHEN {spec_pred} THEN 100.0 ELSE 0.0 END)::numeric, 1)::float AS specialty_rate
            FROM mart.mart_employment_flat m
            WHERE {uni_join_m}
        ) ms ON true
        LEFT JOIN LATERAL (
            SELECT m.region_name AS top_region
            FROM mart.mart_employment_flat m
            WHERE {uni_join_m}
              AND m.region_name IS NOT NULL AND TRIM(m.region_name) <> ''
            GROUP BY m.region_name
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ) mr ON true
        WHERE {where_sql}
    """
    select_core = """
               u.university_id,
               u.university_name,
               u.rating,
               COALESCE(c.city_name, '') AS city_name,
               COALESCE(NULLIF(TRIM(mr.top_region), ''), r.region_name, '') AS region_name,
               COALESCE(ms.avg_sal, 0)::float AS avg_salary,
               COALESCE(ms.emp_rate, 0)::float AS employment_rate,
               COALESCE(ms.employed_count, 0)::int AS employed_count,
               COALESCE(ms.specialty_rate, 0)::float AS specialty_rate
    """.strip()

    if sort == "rating":
        query_params = {
            **params,
            "w_emp": RATING_WEIGHT_EMPLOYED_COUNT,
            "w_spec": RATING_WEIGHT_SPECIALTY_RATE,
            "w_sal": RATING_WEIGHT_AVG_SALARY,
        }
        sql = f"""
            WITH base AS (
                SELECT {select_core}
                {universities_body}
            ),
            bounds AS (
                SELECT COALESCE(MAX(employed_count)::float, 0) AS max_ec,
                       COALESCE(MAX(avg_salary)::float, 0) AS max_sal
                FROM base
            )
            SELECT b.*,
                (
                    :w_emp * COALESCE(b.employed_count::float / NULLIF(bounds.max_ec, 0), 0) +
                    :w_spec * LEAST(GREATEST(b.specialty_rate, 0.0), 100.0) / 100.0 +
                    :w_sal * COALESCE(b.avg_salary::float / NULLIF(bounds.max_sal, 0), 0)
                )::float AS composite_score
            FROM base b
            CROSS JOIN bounds
            ORDER BY composite_score DESC NULLS LAST, b.university_name
            LIMIT :limit OFFSET :offset
        """
    else:
        order_sql = {
            "salary": "avg_salary DESC NULLS LAST, u.university_name",
            "employment": "employment_rate DESC NULLS LAST, u.university_name",
        }[sort]
        query_params = params
        sql = f"""
            SELECT {select_core}
            {universities_body}
            ORDER BY {order_sql}
            LIMIT :limit OFFSET :offset
        """
    try:
        rows = (await db.execute(text(sql), query_params)).mappings().all()
    except Exception:  # noqa: BLE001
        await db.rollback()
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    count_sql = f"SELECT COUNT(*)::int FROM dwh.dim_university u LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id LEFT JOIN dwh.dim_region r ON r.region_id = c.region_id WHERE {where_sql}"
    try:
        total = int((await db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one() or 0)
    except Exception:  # noqa: BLE001
        await db.rollback()
        total = len(rows)
    return {"items": [dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/universities")
async def public_universities(
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=10000),
    search: str | None = None,
    region_id: int | None = None,
    sort: str = Query("rating", pattern="^(rating|salary|employment)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await universities_browse(
        db,
        only_with_mart=False,
        page=page,
        page_size=page_size,
        search=search,
        region_id=region_id,
        sort=sort,
    )


async def _universities_catalog_rows(db: AsyncSession, search: str | None) -> list[dict]:
    """Читает dim_university; несколько вариантов SQL под разные схемы (без rating / без dim_city)."""
    params: dict = {}
    if search:
        params["search"] = f"%{search}%"
    where_variants: list[str]
    if search:
        where_variants = [
            "WHERE u.university_name ILIKE :search OR u.university_code ILIKE :search",
            "WHERE u.university_name ILIKE :search",
        ]
    else:
        where_variants = [""]

    body_templates = [
        """
        SELECT u.university_id,
               u.university_code,
               u.university_name,
               u.rating,
               COALESCE(c.city_name, '') AS city_name
        FROM dwh.dim_university u
        LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
        {where}
        ORDER BY u.university_name
        """,
        """
        SELECT u.university_id,
               u.university_code,
               u.university_name,
               NULL::double precision AS rating,
               COALESCE(c.city_name, '') AS city_name
        FROM dwh.dim_university u
        LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
        {where}
        ORDER BY u.university_name
        """,
        """
        SELECT u.university_id,
               u.university_code,
               u.university_name,
               NULL::double precision AS rating,
               CAST('' AS text) AS city_name
        FROM dwh.dim_university u
        {where}
        ORDER BY u.university_name
        """,
    ]

    last_err: Exception | None = None
    for where in where_variants:
        for tpl in body_templates:
            try:
                sql = tpl.format(where=where)
                rows = (await db.execute(text(sql), params)).mappings().all()
                return [dict(r) for r in rows]
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                await db.rollback()
                continue
    if last_err is not None:
        logger.warning("universities-catalog: все варианты SQL не подошли: %s", last_err)
    return []


@router.get("/universities-catalog")
async def public_universities_catalog(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Полный список вузов из dwh.dim_university для фильтров дашборда и сравнения.
    Не обращается к mart — работает даже если витрина недоступна.
    """
    items = await _universities_catalog_rows(db, search)
    if items or (search and search.strip()):
        return {"items": items}

    try:
        cnt_row = await db.execute(text("SELECT COUNT(*)::bigint AS c FROM dwh.dim_university"))
        cnt = int((cnt_row.mappings().first() or {"c": 0})["c"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("universities-catalog: не удалось проверить dim_university: %s", exc)
        return {"items": []}

    if cnt > 0:
        return {"items": []}

    if not settings.auto_bootstrap_dashboard:
        return {"items": []}

    try:
        await seed_reference_universities(db)
        await db.commit()
    except Exception:  # noqa: BLE001
        await db.rollback()
        logger.exception("universities-catalog: не удалось загрузить справочник вузов при первом запросе")

    items = await _universities_catalog_rows(db, search)
    return {"items": items}


@router.get("/regions")
async def public_regions(db: AsyncSession = Depends(get_db)) -> list[dict]:
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT row_number() OVER (ORDER BY region_name)::int AS region_id,
                           region_name
                    FROM (
                        SELECT DISTINCT region_name
                        FROM mart.mart_employment_flat
                        WHERE region_name IS NOT NULL AND TRIM(region_name) <> ''
                    ) x
                    ORDER BY region_name
                    """
                )
            )
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001
        return []


@router.get("/programs")
async def public_programs(db: AsyncSession = Depends(get_db)) -> list[dict]:
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT DISTINCT program_code, program_name
                    FROM mart.mart_employment_flat
                    WHERE program_code IS NOT NULL AND TRIM(program_code) <> ''
                    ORDER BY program_code
                    """
                )
            )
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001
        return []


@router.get("/education-levels")
async def public_education_levels() -> list[dict]:
    """Уровни образования для фильтра дашборда (согласованы с mart.program_code / filter_where_sql)."""
    return education_level_options_public()


@router.get("/graduation-years")
async def public_graduation_years(db: AsyncSession = Depends(get_db)) -> list[int]:
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT DISTINCT graduation_year AS y
                    FROM mart.mart_employment_flat
                    WHERE graduation_year IS NOT NULL
                    ORDER BY graduation_year DESC
                    """
                )
            )
        ).all()
        return [int(r[0]) for r in rows]
    except Exception:  # noqa: BLE001
        return []


def _dash_params(
    level_id: int | None = None,
    region_id: int | None = None,
    university_id: int | None = None,
    program_code: str | None = None,
    graduation_year: int | None = None,
) -> tuple[str, dict]:
    p: dict = {}
    extra = filter_where_sql(
        level_id=level_id,
        region_id=region_id,
        university_id=university_id,
        program_code=program_code,
        graduation_year=graduation_year,
        params=p,
        alias="m",
    )
    return extra, p


@router.get("/dashboard/kpis")
async def dashboard_kpis(
    level_id: int | None = None,
    region_id: int | None = None,
    university_id: int | None = None,
    program_code: str | None = None,
    graduation_year: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    extra_where, params = _dash_params(level_id, region_id, university_id, program_code, graduation_year)
    row = (
        await db.execute(
            text(
                f"""
                SELECT
                    COALESCE(ROUND(AVG(m.salary) FILTER (WHERE m.is_employed = true AND m.salary IS NOT NULL)::numeric, 0), 0)::float AS avg_salary,
                    COALESCE(ROUND(AVG(CASE WHEN m.is_employed THEN 100.0 ELSE 0.0 END)::numeric, 1), 0)::float AS employment_rate,
                    COUNT(*)::int AS graduates_count,
                    (SELECT company_name FROM mart.mart_employment_flat m2
                     WHERE m2.is_employed = true
                       AND m2.company_name IS NOT NULL
                       AND TRIM(m2.company_name) <> ''
                       {extra_where.replace("m.", "m2.")}
                     GROUP BY m2.company_name
                     ORDER BY COUNT(*) DESC
                     LIMIT 1) AS top_employer
                FROM mart.mart_employment_flat m
                WHERE 1=1 {extra_where}
                """
            ),
            params,
        )
    ).mappings().first()
    r = dict(row) if row else {}
    return {
        "avg_salary": float(r.get("avg_salary") or 0),
        "employment_rate": float(r.get("employment_rate") or 0),
        "graduates_count": int(r.get("graduates_count") or 0),
        "top_employer": r.get("top_employer"),
    }


@router.get("/dashboard/salary-dynamics")
async def dashboard_salary_dynamics(
    level_id: int | None = None,
    region_id: int | None = None,
    university_id: int | None = None,
    program_code: str | None = None,
    graduation_year: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    extra_where, params = _dash_params(level_id, region_id, university_id, program_code, graduation_year)
    rows = (
        await db.execute(
            text(
                f"""
                SELECT m.graduation_year AS year,
                       ROUND(AVG(m.salary)::numeric, 0)::int AS avg_salary
                FROM mart.mart_employment_flat m
                WHERE m.is_employed = true
                  AND m.salary IS NOT NULL
                  {extra_where}
                GROUP BY m.graduation_year
                ORDER BY m.graduation_year
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(x) for x in rows]


@router.get("/dashboard/employment-rate-by-year")
async def dashboard_employment_by_year(
    level_id: int | None = None,
    region_id: int | None = None,
    university_id: int | None = None,
    program_code: str | None = None,
    graduation_year: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    extra_where, params = _dash_params(level_id, region_id, university_id, program_code, graduation_year)
    rows = (
        await db.execute(
            text(
                f"""
                SELECT m.graduation_year AS year,
                       ROUND(AVG(CASE WHEN m.is_employed THEN 100.0 ELSE 0.0 END)::numeric, 1)::float AS employed_percent,
                       ROUND(100.0 - AVG(CASE WHEN m.is_employed THEN 100.0 ELSE 0.0 END)::numeric, 1)::float AS unemployed_percent
                FROM mart.mart_employment_flat m
                WHERE 1=1 {extra_where}
                GROUP BY m.graduation_year
                ORDER BY m.graduation_year
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(x) for x in rows]


@router.get("/dashboard/industry-distribution")
async def dashboard_industry_distribution(
    level_id: int | None = None,
    region_id: int | None = None,
    university_id: int | None = None,
    program_code: str | None = None,
    graduation_year: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    extra_where, params = _dash_params(level_id, region_id, university_id, program_code, graduation_year)
    ind_expr = mart_resolved_industry_sql_expr("m")
    rows = (
        await db.execute(
            text(
                f"""
                SELECT bucket AS industry_name,
                       COUNT(*)::int AS count,
                       ROUND(
                           100.0 * COUNT(*)::numeric
                           / NULLIF(SUM(COUNT(*)) OVER ()::numeric, 0),
                           1
                       )::float AS percentage
                FROM (
                    SELECT {ind_expr} AS bucket
                    FROM mart.mart_employment_flat m
                    WHERE m.is_employed = true
                      {extra_where}
                ) sub
                GROUP BY bucket
                ORDER BY COUNT(*) DESC
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(x) for x in rows]


@router.get("/dashboard/university-comparison")
async def dashboard_university_comparison(
    university_ids: list[int] = Query(default=[]),
    level_id: int | None = None,
    region_id: int | None = None,
    program_code: str | None = None,
    graduation_year: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    if not university_ids:
        return []
    safe_ids = [int(x) for x in university_ids[:8]]
    id_list = ",".join(str(i) for i in safe_ids)
    extra_where, params = _dash_params(level_id, region_id, None, program_code, graduation_year)
    has_wbs = await mart_has_column(db, "works_by_specialty")
    spec_pred = employment_specialty_predicate(has_wbs)
    uni_join = await mart_university_join_condition(db)
    mart_fact = "m.university_name IS NOT NULL"
    rows = (
        await db.execute(
            text(
                f"""
                SELECT u.university_id,
                       u.university_name,
                       COALESCE(
                           ROUND(
                               (
                                   AVG(CASE WHEN m.is_employed THEN 100.0 ELSE 0.0 END)
                                   FILTER (WHERE {mart_fact})
                               )::numeric,
                               1
                           ),
                           0
                       )::float AS employment_total_percent,
                       COALESCE(
                           ROUND(
                               (
                                   AVG(CASE WHEN {spec_pred} THEN 100.0 ELSE 0.0 END)
                                   FILTER (WHERE {mart_fact})
                               )::numeric,
                               1
                           ),
                           0
                       )::float AS employment_specialty_percent,
                       COUNT(m.university_name)::int AS graduates_count,
                       COALESCE(
                           ROUND(
                               (
                                   AVG(m.salary) FILTER (WHERE m.is_employed = true AND m.salary IS NOT NULL)
                               )::numeric,
                               0
                           ),
                           0
                       )::int AS avg_salary
                FROM dwh.dim_university u
                LEFT JOIN mart.mart_employment_flat m
                  ON u.university_id IN ({id_list})
                  AND {uni_join}
                  {extra_where}
                WHERE u.university_id IN ({id_list})
                GROUP BY u.university_id, u.university_name
                ORDER BY u.university_name
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(x) for x in rows]


@router.get("/dashboard/geography")
async def dashboard_geography(
    level_id: int | None = None,
    region_id: int | None = None,
    university_id: int | None = None,
    program_code: str | None = None,
    graduation_year: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    extra_where, params = _dash_params(level_id, region_id, university_id, program_code, graduation_year)
    rows = (
        await db.execute(
            text(
                f"""
                SELECT m.region_name,
                       COUNT(*)::int AS graduates_count,
                       ROUND(AVG(CASE WHEN m.is_employed THEN 100.0 ELSE 0.0 END)::numeric, 1)::float AS employment_rate
                FROM mart.mart_employment_flat m
                WHERE m.region_name IS NOT NULL AND TRIM(m.region_name) <> ''
                {extra_where}
                GROUP BY m.region_name
                ORDER BY m.region_name
                """
            ),
            params,
        )
    ).mappings().all()
    return [
        {"region_name": r["region_name"], "graduates_count": r["graduates_count"], "employment_rate": r["employment_rate"]}
        for r in rows
    ]


async def _university_dim_row(db: AsyncSession, university_id: int) -> dict | None:
    """Справочник вуза; несколько вариантов SQL под разные схемы dwh (без website и т.д.)."""
    templates = [
        """
        SELECT u.university_id, u.university_code, u.university_name, u.foundation_year, u.rating,
               u.website, u.description, u.logo_url,
               COALESCE(c.city_name, '') AS city_name,
               COALESCE(r.region_name, '') AS region_name
        FROM dwh.dim_university u
        LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
        LEFT JOIN dwh.dim_region r ON r.region_id = c.region_id
        WHERE u.university_id = :id
        """,
        """
        SELECT u.university_id, u.university_code, u.university_name, u.foundation_year, u.rating,
               u.website, u.description,
               CAST(NULL AS text) AS logo_url,
               COALESCE(c.city_name, '') AS city_name,
               COALESCE(r.region_name, '') AS region_name
        FROM dwh.dim_university u
        LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
        LEFT JOIN dwh.dim_region r ON r.region_id = c.region_id
        WHERE u.university_id = :id
        """,
        """
        SELECT u.university_id, u.university_code, u.university_name, u.foundation_year, u.rating,
               CAST(NULL AS text) AS website, CAST(NULL AS text) AS description,
               CAST(NULL AS text) AS logo_url,
               COALESCE(c.city_name, '') AS city_name,
               COALESCE(r.region_name, '') AS region_name
        FROM dwh.dim_university u
        LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
        LEFT JOIN dwh.dim_region r ON r.region_id = c.region_id
        WHERE u.university_id = :id
        """,
        """
        SELECT u.university_id, u.university_code, u.university_name,
               CAST(NULL AS int) AS foundation_year, CAST(NULL AS double precision) AS rating,
               CAST(NULL AS text) AS website, CAST(NULL AS text) AS description,
               CAST(NULL AS text) AS logo_url,
               COALESCE(c.city_name, '') AS city_name,
               CAST('' AS text) AS region_name
        FROM dwh.dim_university u
        LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
        LEFT JOIN dwh.dim_region r ON r.region_id = c.region_id
        WHERE u.university_id = :id
        """,
        """
        SELECT u.university_id, u.university_code, u.university_name,
               CAST(NULL AS int) AS foundation_year, CAST(NULL AS double precision) AS rating,
               CAST(NULL AS text) AS website, CAST(NULL AS text) AS description,
               CAST(NULL AS text) AS logo_url,
               CAST('' AS text) AS city_name, CAST('' AS text) AS region_name
        FROM dwh.dim_university u
        WHERE u.university_id = :id
        """,
    ]
    last_err: Exception | None = None
    for tpl in templates:
        try:
            row = (await db.execute(text(tpl), {"id": university_id})).mappings().first()
            return dict(row) if row else None
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            await db.rollback()
            continue
    if last_err is not None:
        logger.warning("university dim: id=%s не прочитан из dwh.dim_university: %s", university_id, last_err)
    return None


async def _uni_mart_from_where(db: AsyncSession, university_id: int) -> tuple[str, dict]:
    """Тот же охват mart, что и в списке вузов: связь витрины со строкой dim по id/имени/коду."""
    uni_join = await mart_university_join_condition(db, m_alias="m", u_alias="u")
    return (
        "FROM mart.mart_employment_flat m "
        "INNER JOIN dwh.dim_university u ON u.university_id = :_pub_uni_id "
        f"WHERE ({uni_join})",
        {"_pub_uni_id": university_id},
    )


async def _university_has_mart_rows(db: AsyncSession, university_id: int) -> bool:
    fw, p = await _uni_mart_from_where(db, university_id)
    chk = (await db.execute(text(f"SELECT 1 AS x {fw} LIMIT 1"), p)).first()
    return chk is not None


async def _university_mart_filters_suffix(
    db: AsyncSession,
    university_id: int,
    *,
    program_code: str | None,
    graduation_year: int | None,
    level_id: int | None,
) -> tuple[str, dict]:
    """Фильтры витрины как на дашборде (направление, год выпуска, уровень ОКСО) + привязка к вузу."""
    params: dict = {}
    scope = await mart_university_scope_and(db, university_id=university_id, params=params)
    pc = str(program_code).strip() if program_code is not None and str(program_code).strip() else None
    extra = filter_where_sql(
        level_id=level_id,
        region_id=None,
        university_id=None,
        program_code=pc,
        graduation_year=graduation_year,
        params=params,
        alias="m",
    )
    return scope + extra, params


def _uni_mart_filters_on_join(
    base_params: dict,
    *,
    program_code: str | None,
    graduation_year: int | None,
    level_id: int | None = None,
) -> tuple[str, dict]:
    """AND … для запросов с {fw} FROM mart … JOIN dim_university (без EXISTS-охвата)."""
    p = dict(base_params)
    pc = str(program_code).strip() if program_code is not None and str(program_code).strip() else None
    extra = filter_where_sql(
        level_id=level_id,
        region_id=None,
        university_id=None,
        program_code=pc,
        graduation_year=graduation_year,
        params=p,
        alias="m",
    )
    return extra, p


@router.get("/universities/{university_id}/profile")
async def public_university_profile(
    university_id: int,
    program_code: str | None = Query(None),
    graduation_year: int | None = Query(None),
    level_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    urow = await _university_dim_row(db, university_id)
    if not urow:
        raise HTTPException(status_code=404, detail="Вуз не найден в справочнике dwh.dim_university.")
    if not await _university_has_mart_rows(db, university_id):
        raise HTTPException(
            status_code=404,
            detail="Для этого вуза нет строк в mart.mart_employment_flat (нет данных о выпускниках).",
        )
    fw, p = await _uni_mart_from_where(db, university_id)
    extra, filter_p = _uni_mart_filters_on_join(
        p,
        program_code=program_code,
        graduation_year=graduation_year,
        level_id=level_id,
    )
    has_wbs = await mart_has_column(db, "works_by_specialty")
    spec_pred = employment_specialty_predicate(has_wbs)
    mart = (
        await db.execute(
            text(
                f"""
                SELECT
                    COUNT(*)::int AS graduates_count,
                    COALESCE(ROUND(AVG(m.salary) FILTER (WHERE m.is_employed = true AND m.salary IS NOT NULL)::numeric, 0), 0)::float AS avg_salary,
                    COALESCE(ROUND(AVG(CASE WHEN m.is_employed THEN 100.0 ELSE 0.0 END)::numeric, 1), 0)::float AS employment_rate,
                    COALESCE(ROUND(AVG(CASE WHEN {spec_pred} THEN 100.0 ELSE 0.0 END)::numeric, 1), 0)::float AS specialty_rate
                {fw}{extra}
                """
            ),
            filter_p,
        )
    ).mappings().first()
    m = dict(mart) if mart else {}
    return {**urow, **m}


@router.get("/universities/{university_id}/salary-dynamics")
async def public_university_salary_dynamics(
    university_id: int,
    program_code: str | None = Query(None),
    graduation_year: int | None = Query(None),
    level_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    if not await _university_dim_row(db, university_id):
        raise HTTPException(status_code=404, detail="Вуз не найден в справочнике dwh.dim_university.")
    if not await _university_has_mart_rows(db, university_id):
        raise HTTPException(status_code=404, detail="Нет данных витрины для этого вуза.")
    suffix, p = await _university_mart_filters_suffix(
        db,
        university_id,
        program_code=program_code,
        graduation_year=graduation_year,
        level_id=level_id,
    )
    rows = (
        await db.execute(
            text(
                f"""
                SELECT m.graduation_year AS year,
                       ROUND(AVG(m.salary)::numeric, 0)::int AS avg_salary
                FROM mart.mart_employment_flat m
                WHERE m.is_employed = true
                  AND m.salary IS NOT NULL
                  {suffix}
                GROUP BY m.graduation_year
                ORDER BY m.graduation_year
                """
            ),
            p,
        )
    ).mappings().all()
    return [dict(x) for x in rows]


@router.get("/universities/{university_id}/industries")
async def public_university_industries(
    university_id: int,
    program_code: str | None = Query(None),
    graduation_year: int | None = Query(None),
    level_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    if not await _university_dim_row(db, university_id):
        raise HTTPException(status_code=404, detail="Вуз не найден в справочнике dwh.dim_university.")
    if not await _university_has_mart_rows(db, university_id):
        raise HTTPException(status_code=404, detail="Нет данных витрины для этого вуза.")
    suffix, p = await _university_mart_filters_suffix(
        db,
        university_id,
        program_code=program_code,
        graduation_year=graduation_year,
        level_id=level_id,
    )
    ind_expr = mart_resolved_industry_sql_expr("m")
    rows = (
        await db.execute(
            text(
                f"""
                SELECT bucket AS industry_name,
                       COUNT(*)::int AS count,
                       ROUND(
                           100.0 * COUNT(*)::numeric
                           / NULLIF(SUM(COUNT(*)) OVER ()::numeric, 0),
                           1
                       )::float AS percentage
                FROM (
                    SELECT {ind_expr} AS bucket
                    FROM mart.mart_employment_flat m
                    WHERE m.is_employed = true
                      {suffix}
                ) sub
                GROUP BY bucket
                ORDER BY COUNT(*) DESC
                """
            ),
            p,
        )
    ).mappings().all()
    return [dict(x) for x in rows]


@router.get("/universities/{university_id}/programs")
async def public_university_programs(university_id: int, db: AsyncSession = Depends(get_db)) -> list[dict]:
    if not await _university_dim_row(db, university_id):
        raise HTTPException(status_code=404, detail="Вуз не найден в справочнике dwh.dim_university.")
    if not await _university_has_mart_rows(db, university_id):
        raise HTTPException(status_code=404, detail="Нет данных витрины для этого вуза.")
    fw, p = await _uni_mart_from_where(db, university_id)
    rows = (
        await db.execute(
            text(
                f"""
                SELECT m.program_code,
                       MAX(COALESCE(NULLIF(TRIM(m.program_name), ''), m.program_code)) AS program_name
                {fw}
                  AND m.program_code IS NOT NULL AND TRIM(m.program_code) <> ''
                GROUP BY m.program_code
                ORDER BY m.program_code
                """
            ),
            p,
        )
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/universities/{university_id}/program-analytics")
async def public_university_program_analytics(
    university_id: int,
    program_code: list[str] = Query(default=[]),
    graduation_year: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    if not await _university_dim_row(db, university_id):
        raise HTTPException(status_code=404, detail="Вуз не найден в справочнике dwh.dim_university.")
    if not await _university_has_mart_rows(db, university_id):
        raise HTTPException(status_code=404, detail="Нет данных витрины для этого вуза.")
    has_wbs = await mart_has_column(db, "works_by_specialty")
    spec_pred = employment_specialty_predicate(has_wbs)
    codes = [str(c).strip() for c in program_code if c is not None and str(c).strip()][:6]
    out: list[dict] = []
    fw, base_p = await _uni_mart_from_where(db, university_id)
    for code in codes:
        pk = dict(base_p)
        pk["_pc"] = code
        kpi_where = f"{fw} AND m.program_code = :_pc"
        if graduation_year is not None:
            kpi_where += " AND m.graduation_year = :_gy"
            pk["_gy"] = graduation_year
        krow = (
            await db.execute(
                text(
                    f"""
                    SELECT MAX(COALESCE(NULLIF(TRIM(m.program_name), ''), m.program_code)) AS program_name,
                           COALESCE(ROUND(AVG(m.salary) FILTER (WHERE m.is_employed = true AND m.salary IS NOT NULL)::numeric, 0), 0)::float AS avg_salary,
                           COALESCE(ROUND(AVG(CASE WHEN m.is_employed THEN 100.0 ELSE 0.0 END)::numeric, 1), 0)::float AS employment_rate,
                           COALESCE(ROUND(AVG(CASE WHEN {spec_pred} THEN 100.0 ELSE 0.0 END)::numeric, 1), 0)::float AS specialty_rate
                    {kpi_where}
                    """
                ),
                pk,
            )
        ).mappings().first()
        ps = dict(base_p)
        ps["_pc"] = code
        series_where = f"{fw} AND m.program_code = :_pc AND m.is_employed = true AND m.salary IS NOT NULL"
        if graduation_year is not None:
            series_where += " AND m.graduation_year = :_gy_series"
            ps["_gy_series"] = graduation_year
        series_rows = (
            await db.execute(
                text(
                    f"""
                    SELECT m.graduation_year AS year,
                           ROUND(AVG(m.salary)::numeric, 0)::int AS avg_salary
                    {series_where}
                    GROUP BY m.graduation_year
                    ORDER BY m.graduation_year
                    """
                ),
                ps,
            )
        ).mappings().all()
        kd = dict(krow) if krow else {}
        out.append(
            {
                "program_code": code,
                "program_name": str(kd.get("program_name") or code),
                "avg_salary": float(kd.get("avg_salary") or 0),
                "employment_rate": float(kd.get("employment_rate") or 0),
                "specialty_rate": float(kd.get("specialty_rate") or 0),
                "salary_by_year": [{"year": int(r["year"]), "avg_salary": int(r["avg_salary"])} for r in series_rows],
            }
        )
    return out


@router.get("/universities/{university_id}/employers")
async def public_university_employers(
    university_id: int,
    program_code: str | None = Query(None),
    graduation_year: int | None = Query(None),
    level_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    if not await _university_dim_row(db, university_id):
        raise HTTPException(status_code=404, detail="Вуз не найден в справочнике dwh.dim_university.")
    if not await _university_has_mart_rows(db, university_id):
        raise HTTPException(status_code=404, detail="Нет данных витрины для этого вуза.")
    suffix, p = await _university_mart_filters_suffix(
        db,
        university_id,
        program_code=program_code,
        graduation_year=graduation_year,
        level_id=level_id,
    )
    rows = (
        await db.execute(
            text(
                f"""
                SELECT m.company_name,
                       COUNT(*)::int AS graduates_count
                FROM mart.mart_employment_flat m
                WHERE m.is_employed = true
                  AND m.company_name IS NOT NULL
                  AND TRIM(m.company_name) <> ''
                  {suffix}
                GROUP BY m.company_name
                ORDER BY COUNT(*) DESC
                LIMIT 20
                """
            ),
            p,
        )
    ).mappings().all()
    return [{"company_name": str(r["company_name"]), "graduates_count": int(r["graduates_count"])} for r in rows]


@router.get("/articles")
async def public_articles(db: AsyncSession = Depends(get_db)) -> list[dict]:
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT id, title, excerpt, category, image_url, created_at
                    FROM public.articles
                    ORDER BY created_at DESC NULLS LAST, id DESC
                    """
                )
            )
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001
        await db.rollback()
        return []


@router.get("/articles/{article_id}")
async def public_article_detail(article_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        row = (
            await db.execute(
                text(
                    "SELECT id, title, excerpt, content, category, image_url, created_at FROM public.articles WHERE id = :id"
                ),
                {"id": article_id},
            )
        ).mappings().first()
    except Exception:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена.") from None
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена.")
    return dict(row)
