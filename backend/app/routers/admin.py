import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_admin
from app.schemas.admin import (
    ArticleCreate,
    ArticleOut,
    DashboardStats,
    EtlSummary,
    GraduateManualRow,
    ImportPayload,
    ImportResult,
    LoginRequest,
    PaginatedUniversities,
    SeedDashboardDemoResponse,
    StudentListResponse,
    TokenResponse,
    UniversityCreate,
    UniversityOut,
    UniversityUpdate,
)
from app.routers.public import universities_browse
from app.services.import_service import (
    EXPECTED_COLUMNS,
    import_rows_to_staging,
    parse_csv_content,
    transfer_staging_to_dwh,
)
from app.services.seed_dashboard import run_dashboard_seed
from app.services.seed_reference_universities import seed_reference_universities
from app.services import import_audit

router = APIRouter(prefix="/api/admin", tags=["admin"])

logger = logging.getLogger(__name__)


async def _db_rollback_safe(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception:  # noqa: BLE001
        pass


async def _import_rows_raise_clear_errors(db: AsyncSession, rows: list[dict]) -> dict[str, Any]:
    """Staging-импорт: RuntimeError из bootstrap → 422; ошибки PostgreSQL без «голого» 500."""
    try:
        return await import_rows_to_staging(db, rows)
    except RuntimeError as exc:
        await _db_rollback_safe(db)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None
    except SQLAlchemyError as exc:
        await _db_rollback_safe(db)
        orig = getattr(exc, "orig", None)
        pg_msg = getattr(orig, "pgerror", None) if orig else None
        fallback = pg_msg or (str(orig).strip() if orig else "") or str(exc).strip()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"База данных отклонила операцию импорта (staging/ETL). {fallback}".strip(),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        await _db_rollback_safe(db)
        logger.exception("import_rows unexpected error")
        msg = str(exc).strip() or type(exc).__name__
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Импорт не выполнен ({type(exc).__name__}). {msg}"[:2500],
        ) from exc


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    if payload.login != settings.admin_login or payload.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(token=create_access_token("admin"))


@router.get("/dashboard/stats", response_model=DashboardStats, dependencies=[Depends(get_current_admin)])
async def dashboard_stats(db: AsyncSession = Depends(get_db)) -> DashboardStats:
    empty_stats = DashboardStats(
        universities_total=0,
        graduates_total=0,
        companies_total=0,
        employments_total=0,
        last_csv_load=None,
        last_events=[],
    )
    try:
        counts_sql = """
            SELECT
                (SELECT COUNT(*) FROM dwh.dim_university) AS universities_total,
                (SELECT COUNT(*) FROM dwh.dim_student) AS graduates_total,
                (SELECT COUNT(*) FROM dwh.dim_company) AS companies_total,
                (SELECT COUNT(*) FROM dwh.fact_employment) AS employments_total,
                (SELECT MAX(load_timestamp) FROM staging.stg_graduates) AS last_csv_load
        """
        row = (await db.execute(text(counts_sql))).mappings().first()
        events = (
            await db.execute(
                text(
                    """
                    SELECT task_id, MAX(load_timestamp) AS load_timestamp, COUNT(*) AS row_count
                    FROM staging.stg_graduates
                    GROUP BY task_id
                    ORDER BY MAX(load_timestamp) DESC
                    LIMIT 10
                    """
                )
            )
        ).mappings().all()
        if not row:
            return empty_stats
        return DashboardStats(**row, last_events=[dict(x) for x in events])
    except SQLAlchemyError as exc:
        await _db_rollback_safe(db)
        logger.warning("dashboard_stats: DB unavailable, returning zeros: %s", exc)
        return empty_stats
    except Exception as exc:  # noqa: BLE001
        await _db_rollback_safe(db)
        logger.exception("dashboard_stats failed")
        return empty_stats


@router.get("/universities", response_model=PaginatedUniversities, dependencies=[Depends(get_current_admin)])
async def list_universities(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> PaginatedUniversities:
    offset = (page - 1) * page_size
    where = "WHERE u.university_name ILIKE :search" if search else ""
    params = {"limit": page_size, "offset": offset}
    if search:
        params["search"] = f"%{search}%"
    rows = (
        await db.execute(
            text(
                f"""
                SELECT u.university_id, u.university_code, u.university_name, u.city_id, c.city_name,
                       u.foundation_year, u.rating, u.website, u.description, u.logo_url
                FROM dwh.dim_university u
                JOIN dwh.dim_city c ON c.city_id = u.city_id
                {where}
                ORDER BY u.university_name
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()
    count = (
        await db.execute(text(f"SELECT COUNT(*) FROM dwh.dim_university u {where}"), params if search else {})
    ).scalar_one()
    return PaginatedUniversities(
        items=[UniversityOut(**dict(r)) for r in rows],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get("/cities", dependencies=[Depends(get_current_admin)])
async def admin_cities(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Города для формы вуза (с регионом, если есть связь в схеме)."""
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT c.city_id, c.city_name, COALESCE(r.region_name, '') AS region_name
                    FROM dwh.dim_city c
                    LEFT JOIN dwh.dim_region r ON r.region_id = c.region_id
                    ORDER BY r.region_name NULLS LAST, c.city_name
                    """
                )
            )
        ).mappings().all()
    except Exception:  # noqa: BLE001
        await db.rollback()
        rows = (
            await db.execute(
                text(
                    """
                    SELECT c.city_id, c.city_name, CAST('' AS text) AS region_name
                    FROM dwh.dim_city c
                    ORDER BY c.city_name
                    """
                )
            )
        ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/dim-universities", dependencies=[Depends(get_current_admin)])
async def admin_dim_universities(
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=10000),
    search: str | None = None,
    region_name: str | None = None,
    sort: str = Query("rating", pattern="^(rating|salary|employment)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Справочник вузов напрямую из **dwh.dim_university** (PostgreSQL: схема `dwh`, таблица `dim_university`).
    Без витрины mart — устойчиво к 404/ошибкам сложного browse и к отсутствию mart.
    Метрики ЗП/трудоустройства в ответе нули (их можно смотреть на публичной витрине).
    """
    offset = (page - 1) * page_size
    params: dict = {"limit": page_size, "offset": offset}
    where_parts: list[str] = ["TRUE"]
    if search and str(search).strip():
        where_parts.append(
            "(u.university_name ILIKE :search OR COALESCE(c.city_name, '') ILIKE :search "
            "OR COALESCE(r.region_name, '') ILIKE :search)"
        )
        params["search"] = f"%{search.strip()}%"
    if region_name and str(region_name).strip():
        where_parts.append("TRIM(BOTH FROM COALESCE(r.region_name, '')) = :region_exact")
        params["region_exact"] = region_name.strip()
    where_sql = " AND ".join(where_parts)
    order_sql = {
        "rating": "u.rating DESC NULLS LAST, u.university_name",
        "salary": "u.university_name",
        "employment": "u.university_name",
    }[sort]
    sql_items = f"""
        SELECT u.university_id,
               u.university_name,
               u.rating,
               COALESCE(c.city_name, '') AS city_name,
               COALESCE(NULLIF(TRIM(BOTH FROM r.region_name), ''), '') AS region_name,
               0::double precision AS avg_salary,
               0::double precision AS employment_rate,
               0::int AS employed_count,
               0::double precision AS specialty_rate
        FROM dwh.dim_university u
        LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
        LEFT JOIN dwh.dim_region r ON r.region_id = c.region_id
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT :limit OFFSET :offset
    """
    sql_count = f"""
        SELECT COUNT(*)::int
        FROM dwh.dim_university u
        LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
        LEFT JOIN dwh.dim_region r ON r.region_id = c.region_id
        WHERE {where_sql}
    """
    try:
        rows = (await db.execute(text(sql_items), params)).mappings().all()
        count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
        total = int((await db.execute(text(sql_count), count_params)).scalar_one() or 0)
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось прочитать dwh.dim_university (проверьте схему dwh и таблицу dim_university).",
        ) from exc
    try:
        dim_total = int((await db.execute(text("SELECT COUNT(*)::int FROM dwh.dim_university"))).scalar_one() or 0)
    except Exception:  # noqa: BLE001
        await db.rollback()
        dim_total = total
    return {
        "items": [dict(x) for x in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "dim_catalog_total": dim_total,
    }


@router.get("/universities-browser", dependencies=[Depends(get_current_admin)])
async def admin_universities_browser(
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=10000),
    search: str | None = None,
    region_id: int | None = None,
    sort: str = Query("rating", pattern="^(rating|salary|employment)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Все вузы из dwh.dim_university + метрики mart (0, если витрины нет). Для админ-панели."""
    out = await universities_browse(
        db,
        only_with_mart=False,
        page=page,
        page_size=page_size,
        search=search,
        region_id=region_id,
        sort=sort,
    )
    try:
        dim_total = int((await db.execute(text("SELECT COUNT(*)::int FROM dwh.dim_university"))).scalar_one() or 0)
    except Exception:  # noqa: BLE001
        await db.rollback()
        dim_total = 0
    out["dim_catalog_total"] = dim_total
    return out


@router.get("/universities/{university_id}", response_model=UniversityOut, dependencies=[Depends(get_current_admin)])
async def get_university(university_id: int, db: AsyncSession = Depends(get_db)) -> UniversityOut:
    row = (
        await db.execute(
            text(
                """
                SELECT u.university_id,
                       TRIM(BOTH FROM COALESCE(u.university_code, '')) AS university_code,
                       TRIM(BOTH FROM COALESCE(u.university_name, '')) AS university_name,
                       u.city_id,
                       NULLIF(TRIM(BOTH FROM COALESCE(c.city_name, '')), '') AS city_name,
                       u.foundation_year, u.rating, u.website, u.description, u.logo_url
                FROM dwh.dim_university u
                LEFT JOIN dwh.dim_city c ON c.city_id = u.city_id
                WHERE u.university_id = :id
                """
            ),
            {"id": university_id},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Вуз не найден в справочнике.")
    return UniversityOut.model_validate(dict(row))


@router.post("/universities", response_model=UniversityOut, dependencies=[Depends(get_current_admin)])
async def create_university(payload: UniversityCreate, db: AsyncSession = Depends(get_db)) -> UniversityOut:
    try:
        result = await db.execute(
            text(
                """
                INSERT INTO dwh.dim_university (
                    university_code, university_name, city_id, foundation_year, rating, website, description, logo_url
                ) VALUES (
                    :university_code, :university_name, :city_id, :foundation_year, :rating, :website, :description, :logo_url
                )
                RETURNING university_id, university_code, university_name, city_id, foundation_year, rating, website, description, logo_url
                """
            ),
            payload.model_dump(),
        )
        row = result.mappings().first()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось создать вуз: такой код уже есть или нарушено ограничение БД (город, уникальность).",
        )
    city_name = (
        await db.execute(text("SELECT city_name FROM dwh.dim_city WHERE city_id = :id"), {"id": row["city_id"]})
    ).scalar_one_or_none()
    return UniversityOut(**dict(row), city_name=city_name)


@router.put("/universities/{university_id}", response_model=UniversityOut, dependencies=[Depends(get_current_admin)])
async def update_university(
    university_id: int,
    payload: UniversityUpdate,
    db: AsyncSession = Depends(get_db),
) -> UniversityOut:
    try:
        result = await db.execute(
            text(
                """
                UPDATE dwh.dim_university
                SET university_code=:university_code,
                    university_name=:university_name,
                    city_id=:city_id,
                    foundation_year=:foundation_year,
                    rating=:rating,
                    website=:website,
                    description=:description,
                    logo_url=:logo_url
                WHERE university_id=:university_id
                RETURNING university_id, university_code, university_name, city_id, foundation_year, rating, website, description, logo_url
                """
            ),
            {**payload.model_dump(), "university_id": university_id},
        )
        row = result.mappings().first()
        if not row:
            await db.rollback()
            raise HTTPException(status_code=404, detail="Вуз не найден.")
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось сохранить: код вуза занят другой записью или нарушено ограничение БД.",
        )
    city_name = (
        await db.execute(text("SELECT city_name FROM dwh.dim_city WHERE city_id = :id"), {"id": row["city_id"]})
    ).scalar_one_or_none()
    return UniversityOut(**dict(row), city_name=city_name)


@router.delete("/universities/{university_id}", dependencies=[Depends(get_current_admin)])
async def delete_university(university_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    exists = (
        await db.execute(
            text("SELECT 1 FROM dwh.dim_university WHERE university_id = :id LIMIT 1"),
            {"id": university_id},
        )
    ).first()
    if exists is None:
        raise HTTPException(status_code=404, detail="Вуз не найден.")
    try:
        await db.execute(text("DELETE FROM dwh.dim_university WHERE university_id = :id"), {"id": university_id})
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Невозможно удалить вуз: в базе есть связанные данные "
                "(например, витрина mart, факты трудоустройства). Сначала удалите или обновите их."
            ),
        )
    return {"status": "ok"}


async def _import_with_etl_and_audit(
    db: AsyncSession,
    rows: list[dict],
    *,
    source_kind: str,
    filename: str | None,
) -> ImportResult:
    """Staging + ETL + запись журнала import_batch_audit (ошибки/логи)."""
    logs: list[dict[str, Any]] = [
        {"at": import_audit.utc_now_iso(), "level": "info", "msg": f"Начало импорта: {source_kind}"},
    ]

    result = await _import_rows_raise_clear_errors(db, rows)
    task_id = str(result["task_id"])
    inserted = int(result["inserted"])
    err = list(result["errors"])
    etl: EtlSummary | None = None
    stats: dict[str, Any] | None = None

    logs.append(
        {
            "at": import_audit.utc_now_iso(),
            "level": "info",
            "msg": (
                f"Запись в staging завершена: принято строк {inserted}; "
                f"сообщений валидации/ошибок по строкам: {len(err)}."
            ),
        }
    )

    if inserted > 0:
        logs.append({"at": import_audit.utc_now_iso(), "level": "info", "msg": "Запуск ETL staging → dwh → mart"})
        try:
            stats_raw = await transfer_staging_to_dwh(db, task_id=task_id)
            stats = dict(stats_raw)
            etl = EtlSummary(**stats_raw)
            logs.append(
                {
                    "at": import_audit.utc_now_iso(),
                    "level": "info",
                    "msg": (
                        f"ETL успешно: staging_rows={stats.get('staging_rows')}, "
                        f"fact_rows={stats.get('fact_rows')}, mart_rows={stats.get('mart_rows')}"
                    ),
                },
            )
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            err.append(f"ETL: {exc}")
            logs.append({"at": import_audit.utc_now_iso(), "level": "error", "msg": f"Ошибка ETL: {exc}"})

    try:
        await import_audit.persist_import_batch_audit(
            db,
            task_id=task_id,
            source_kind=source_kind,
            filename=filename,
            rows_inserted=inserted,
            errors=err,
            logs=logs,
            etl_fact_rows=int(stats["fact_rows"]) if stats else None,
            etl_mart_rows=int(stats["mart_rows"]) if stats else None,
            etl_full=dict(stats) if stats else None,
        )
        await db.commit()
    except Exception:
        logger.exception("Не удалось сохранить журнал импортов (staging.import_batch_audit)")
        await _db_rollback_safe(db)

    return ImportResult(task_id=task_id, inserted=inserted, errors=err, etl=etl)


@router.get("/import/batches", dependencies=[Depends(get_current_admin)])
async def list_import_batches_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """История загрузок: distinct task_id по staging с метаданными аудита."""
    await import_audit.ensure_seed_demo_audit_if_mart_nonempty(db)
    total = await import_audit.count_import_batches(db)
    offset = (page - 1) * page_size
    items = await import_audit.list_import_batches(db, offset=offset, limit=page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/import/batches/{task_id}/staging-rows", dependencies=[Depends(get_current_admin)])
async def list_import_batch_staging_rows(
    task_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Строки staging.stg_graduates для одной загрузки (просмотр «какие данные грузили»)."""
    await import_audit.ensure_seed_demo_audit_if_mart_nonempty(db)
    offset = (page - 1) * page_size
    items, total = await import_audit.list_staging_rows_for_task(db, task_id.strip(), offset=offset, limit=page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/import/batches/{task_id}", dependencies=[Depends(get_current_admin)])
async def get_import_batch_detail_endpoint(task_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    await import_audit.ensure_seed_demo_audit_if_mart_nonempty(db)
    agg = await import_audit.get_batch_staging_aggregate(db, task_id)
    audit = await import_audit.get_import_batch_audit_row(db, task_id)
    if agg is None and audit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Загрузка с таким task_id не найдена.",
        )

    errors_raw: list[Any] = []
    logs_raw: list[Any] = []
    audit_meta: dict[str, Any] | None = None
    if audit:
        errors_raw = import_audit.jsonb_decode_list(audit.get("errors_json"))
        logs_raw = import_audit.jsonb_decode_list(audit.get("logs_json"))
        audit_meta = {
            "task_id": audit.get("task_id"),
            "source_kind": audit.get("source_kind"),
            "filename": audit.get("filename"),
            "logged_at": audit.get("logged_at"),
            "rows_inserted": audit.get("rows_inserted"),
            "etl_fact_rows": audit.get("etl_fact_rows"),
            "etl_mart_rows": audit.get("etl_mart_rows"),
            "etl_json": audit.get("etl_json"),
        }
        if isinstance(audit_meta.get("etl_json"), (bytes, memoryview)):
            audit_meta.pop("etl_json", None)

    if agg:
        aggregate: dict[str, Any] = {
            "rows_in_staging": agg.get("rows_in_staging"),
            "first_load_at": agg.get("first_load_at"),
            "last_load_at": agg.get("last_load_at"),
        }
    else:
        la = audit_meta.get("logged_at") if audit_meta else None
        aggregate = {
            "rows_in_staging": 0,
            "first_load_at": la,
            "last_load_at": la,
        }

    journal_parts: list[str] = []
    if not audit_meta:
        journal_parts.append(
            "Сохранённый журнал отсутствует (загрузка до введения аудита или не удалась запись в import_batch_audit).",
        )
    if agg is None and audit_meta is not None:
        journal_parts.append(
            "В staging сейчас нет строк для этого batch — возможно, они были перезаписаны или очищены; доступны сохранённые лог и ошибки импорта.",
        )

    return {
        "task_id": task_id.strip(),
        "aggregate": aggregate,
        "audit": audit_meta,
        "errors": [(e if isinstance(e, str) else str(e)) for e in errors_raw],
        "logs": logs_raw if isinstance(logs_raw, list) else [],
        "journal_note": " ".join(journal_parts).strip(),
    }


@router.post("/import/manual-row", response_model=ImportResult, dependencies=[Depends(get_current_admin)])
async def import_manual_row(payload: GraduateManualRow, db: AsyncSession = Depends(get_db)) -> ImportResult:
    d = payload.model_dump()
    row = {col: d.get(col) for col in EXPECTED_COLUMNS}
    return await _import_with_etl_and_audit(db, [row], source_kind="manual", filename=None)


@router.post("/import/csv", response_model=ImportResult, dependencies=[Depends(get_current_admin)])
async def import_csv(payload: ImportPayload, db: AsyncSession = Depends(get_db)) -> ImportResult:
    return await _import_with_etl_and_audit(db, payload.rows, source_kind="csv", filename=None)


@router.post("/import/csv-file", response_model=ImportResult, dependencies=[Depends(get_current_admin)])
async def import_csv_upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ImportResult:
    if not file.filename or not str(file.filename).lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужен файл с расширением .csv")
    raw = await file.read()
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл не больше 50 МБ")
    try:
        text_raw = raw.decode("utf-8-sig")
        rows = parse_csv_content(text_raw)
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Кодировка файла должна быть UTF-8.") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return await _import_with_etl_and_audit(db, rows, source_kind="csv-file", filename=file.filename or None)


@router.post("/import/transfer", dependencies=[Depends(get_current_admin)])
async def transfer_to_dwh(
    task_id: str | None = Query(None, description="ID загрузки (если не указан — последняя по времени из staging)"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stats = await transfer_staging_to_dwh(db, task_id=task_id)
    return {"status": "ok", **stats}
@router.post(
    "/seed/dashboard-demo",
    response_model=SeedDashboardDemoResponse,
    dependencies=[Depends(get_current_admin)],
)
async def seed_dashboard_demo(
    recreate_mart_as_table: bool = Query(
        False,
        description="Если mart — VIEW или несовместимая таблица: удалить и создать таблицу-витрину (только dev).",
    ),
    db: AsyncSession = Depends(get_db),
) -> SeedDashboardDemoResponse:
    """Загрузка демо-данных для графиков дашборда (витрина mart + синхронизация фактов)."""
    ref = await seed_reference_universities(db)
    result = await run_dashboard_seed(db, recreate_mart_as_table=recreate_mart_as_table)
    if not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Ошибка сидирования"),
        )
    notes = list(result.get("notes") or [])
    notes.insert(0, f"Справочник вузов: обновлено {ref.get('universities_upserted')} записей.")
    return SeedDashboardDemoResponse(
        ok=True,
        inserted_mart_rows=result.get("inserted_mart_rows"),
        universities=result.get("universities"),
        notes=notes,
    )


@router.get("/students", response_model=StudentListResponse, dependencies=[Depends(get_current_admin)])
async def list_students(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=500),
    sort: str = Query(
        "recent",
        pattern="^(recent|graduation)$",
        description="recent — по времени обновления в витрине mart (etl_updated_at); graduation — по году выпуска",
    ),
    graduation_year: int | None = None,
    university_name: str | None = None,
    is_employed: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> StudentListResponse:
    filters = []
    params: dict[str, Any] = {"limit": page_size, "offset": (page - 1) * page_size}
    if graduation_year is not None:
        filters.append("m.graduation_year = :graduation_year")
        params["graduation_year"] = graduation_year
    if university_name:
        filters.append("m.university_name ILIKE :university_name")
        params["university_name"] = f"%{university_name}%"
    if is_employed is not None:
        filters.append("m.is_employed = :is_employed")
        params["is_employed"] = is_employed
    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""

    if sort == "recent":
        order_sql = "m.etl_updated_at DESC NULLS LAST, m.graduation_year DESC NULLS LAST, m.student_hash"
    else:
        order_sql = "m.graduation_year DESC NULLS LAST, m.student_hash"

    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}

    async def _query_mart(order_clause: str) -> tuple[int, list[Any]]:
        total_n = (
            await db.execute(
                text(f"SELECT COUNT(*)::bigint FROM mart.mart_employment_flat m {where_sql}"),
                count_params,
            )
        ).scalar_one()
        row_maps = (
            await db.execute(
                text(
                    f"""
                    SELECT m.*
                    FROM mart.mart_employment_flat m
                    {where_sql}
                    ORDER BY {order_clause}
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            )
        ).mappings().all()
        return int(total_n or 0), [dict(r) for r in row_maps]

    try:
        total, items = await _query_mart(order_sql)
        return StudentListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except SQLAlchemyError as exc:
        await _db_rollback_safe(db)
        if sort == "recent" and "etl_updated_at" in str(exc).lower():
            try:
                total, items = await _query_mart("m.graduation_year DESC NULLS LAST, m.student_hash")
                return StudentListResponse(
                    items=items,
                    total=total,
                    page=page,
                    page_size=page_size,
                )
            except SQLAlchemyError as exc2:
                await _db_rollback_safe(db)
                logger.warning("list_students: mart fallback failed: %s", exc2)
        else:
            logger.warning("list_students: mart unavailable, empty list: %s", exc)
        return StudentListResponse(items=[], total=0, page=page, page_size=page_size)
    except Exception as exc:  # noqa: BLE001
        await _db_rollback_safe(db)
        logger.exception("list_students failed")
        return StudentListResponse(items=[], total=0, page=page, page_size=page_size)


@router.delete("/students/{student_hash}", dependencies=[Depends(get_current_admin)])
async def delete_student(student_hash: str, db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("DELETE FROM mart.mart_employment_flat WHERE student_hash = :student_hash"), {"student_hash": student_hash})
    await db.execute(text("DELETE FROM dwh.fact_employment WHERE student_hash = :student_hash"), {"student_hash": student_hash})
    await db.execute(text("DELETE FROM dwh.dim_student WHERE student_hash = :student_hash"), {"student_hash": student_hash})
    await db.commit()
    return {"status": "ok"}


@router.get("/articles", response_model=list[ArticleOut], dependencies=[Depends(get_current_admin)])
async def list_articles(db: AsyncSession = Depends(get_db)) -> list[ArticleOut]:
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT id, title, excerpt, content, category, image_url, created_at
                    FROM public.articles
                    ORDER BY created_at DESC NULLS LAST, id DESC
                    """
                )
            )
        ).mappings().all()
        return [ArticleOut.model_validate(dict(r)) for r in rows]
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось загрузить статьи из БД UNI (проверьте таблицу public.articles и права доступа).",
        ) from exc


@router.post("/articles", response_model=ArticleOut, dependencies=[Depends(get_current_admin)])
async def create_article(payload: ArticleCreate, db: AsyncSession = Depends(get_db)) -> ArticleOut:
    try:
        row = (
            await db.execute(
                text(
                    """
                    INSERT INTO public.articles (title, excerpt, content, category, image_url)
                    VALUES (:title, :excerpt, :content, :category, :image_url)
                    RETURNING id, title, excerpt, content, category, image_url, created_at
                    """
                ),
                payload.model_dump(),
            )
        ).mappings().first()
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось сохранить статью в БД UNI.",
        ) from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Пустой ответ INSERT.")
    return ArticleOut.model_validate(dict(row))
