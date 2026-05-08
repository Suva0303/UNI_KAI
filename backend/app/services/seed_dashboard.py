"""Демо-данные для витрины mart и связанных сущностей DWH."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.import_audit import SEED_DEMO_TASK_ID, persist_import_batch_audit, utc_now_iso


def _hash_id(i: int, suffix: str = "") -> str:
    return hashlib.sha256(f"uni-demo-{i}-{suffix}".encode()).hexdigest()


DEMO_MART_UNIVERSITY_CODES: tuple[str, ...] = ("MGU", "SPbGU", "MIPT", "ITMO")


def _industry_for_program(program_code: str) -> tuple[str, list[tuple[str, str]]]:
    """ОКСО/код программы → отрасль и пул работодателей."""
    pc = program_code.replace(" ", "")
    if pc.startswith("09.") or pc.startswith("10.") or pc.startswith("01.03"):
        return (
            "Информационные технологии",
            [
                ("ООО «Яндекс»", True),
                ("ООО «ВК»", True),
                ("ПАО «Сбербанк», блок IT", True),
                ("ООО «Тинькофф»", False),
            ],
        )
    if pc.startswith("31.") or pc.startswith("32."):
        return (
            "Здравоохранение",
            [
                ("ГКБ им. Бурденко", True),
                ("Поликлиника №5", True),
                ("НИИ онкологии", True),
                ("Частная клиника «Медси»", False),
            ],
        )
    if pc.startswith("38.") or pc.startswith("27."):
        return (
            "Финансы и страхование",
            [
                ("ПАО «Сбербанк»", False),
                ("Банк ВТБ (ПАО)", False),
                ("АО «Альфа-Банк»", False),
            ],
        )
    return (
        "Образование",
        [
            ("АНО «Демо-школа»", False),
            ("ООО «Учебный центр»", True),
        ],
    )


async def _relkind(session: AsyncSession, schema: str, name: str) -> str | None:
    row = (
        await session.execute(
            text(
                """
                SELECT c.relkind::text
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema AND c.relname = :name
                """
            ),
            {"schema": schema, "name": name},
        )
    ).first()
    return row[0] if row else None


async def _get_city_id(session: AsyncSession, city_name: str) -> int:
    r = (await session.execute(text("SELECT city_id FROM dwh.dim_city WHERE city_name = :n LIMIT 1"), {"n": city_name})).first()
    if r:
        return int(r[0])
    ins = await session.execute(
        text("INSERT INTO dwh.dim_city (city_name) VALUES (:n) RETURNING city_id"),
        {"n": city_name},
    )
    return int(ins.scalar_one())


async def _ensure_university(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    city_id: int,
    foundation_year: int,
    rating: float,
) -> int:
    r = (
        await session.execute(
            text("SELECT university_id FROM dwh.dim_university WHERE university_code = :c LIMIT 1"),
            {"c": code},
        )
    ).first()
    if r:
        return int(r[0])
    ins = await session.execute(
        text(
            """
            INSERT INTO dwh.dim_university (
                university_code, university_name, city_id, foundation_year, rating, website, description
            ) VALUES (
                :code, :name, :city_id, :fy, :rating, NULL, 'Демо-данные для дашборда'
            )
            RETURNING university_id
            """
        ),
        {"code": code, "name": name, "city_id": city_id, "fy": foundation_year, "rating": rating},
    )
    return int(ins.scalar_one())


def _build_mart_rows(
    universities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    idx = 0
    for uni in universities:
        for program_code, program_name in uni["programs"]:
            industry_base, employers = _industry_for_program(program_code)
            for year in range(2018, 2025):
                n_grad = 6
                for g in range(n_grad):
                    idx += 1
                    employed = (idx % 10) != 0
                    emp = employers[(idx + year + g) % len(employers)]
                    company_name, works_spec = emp[0], emp[1]
                    salary = None
                    if employed:
                        base = 55000 if "09." in program_code or "10." in program_code else 48000
                        if "31." in program_code or "32." in program_code:
                            base = 62000
                        if "38." in program_code:
                            base = 58000
                        salary = float(base + (year - 2018) * 3500 + (idx % 7) * 1200)
                    rows.append(
                        {
                            "student_hash": _hash_id(idx, uni["code"]),
                            "graduation_year": year,
                            "university_name": uni["name"],
                            "university_id": uni["id"],
                            "university_code": uni["code"],
                            "region_name": uni["region"],
                            "program_code": program_code,
                            "program_name": program_name,
                            "is_employed": employed,
                            "salary": salary,
                            "industry_name": industry_base if employed else None,
                            "company_name": company_name if employed else None,
                            "works_by_specialty": works_spec if employed else False,
                            "gender": "М" if idx % 2 == 0 else "Ж",
                            "birth_year": year - 22 - (g % 3),
                        }
                    )
    return rows


async def recreate_mart_as_table(session: AsyncSession) -> None:
    await session.execute(text("CREATE SCHEMA IF NOT EXISTS mart"))
    await session.execute(text("DROP VIEW IF EXISTS mart.mart_employment_flat CASCADE"))
    await session.execute(text("DROP TABLE IF EXISTS mart.mart_employment_flat CASCADE"))
    await session.execute(
        text(
            """
            CREATE TABLE mart.mart_employment_flat (
                student_hash VARCHAR(64) NOT NULL,
                graduation_year INTEGER NOT NULL,
                university_name TEXT NOT NULL,
                university_id INTEGER,
                university_code TEXT,
                region_name TEXT NOT NULL,
                program_code TEXT NOT NULL,
                program_name TEXT,
                is_employed BOOLEAN NOT NULL DEFAULT false,
                salary NUMERIC(14, 2),
                industry_name TEXT,
                company_name TEXT,
                works_by_specialty BOOLEAN DEFAULT false,
                gender TEXT,
                birth_year INTEGER,
                etl_updated_at TIMESTAMPTZ,
                PRIMARY KEY (student_hash)
            )
            """
        )
    )


async def delete_demo_mart_rows(session: AsyncSession) -> int:
    in_list = ",".join(f"'{c}'" for c in DEMO_MART_UNIVERSITY_CODES)
    r = await session.execute(
        text(
            f"""
            DELETE FROM mart.mart_employment_flat
            WHERE university_code LIKE 'DEMO%'
               OR university_code IN ({in_list})
            RETURNING student_hash
            """
        ),
    )
    return len(r.fetchall())


async def insert_mart_batch(session: AsyncSession, batch: list[dict[str, Any]]) -> int:
    if not batch:
        return 0
    q = text(
        """
        INSERT INTO mart.mart_employment_flat (
            student_hash, graduation_year, university_name, university_id, university_code,
            region_name, program_code, program_name, is_employed, salary,
            industry_name, company_name, works_by_specialty, gender, birth_year
        ) VALUES (
            :student_hash, :graduation_year, :university_name, :university_id, :university_code,
            :region_name, :program_code, :program_name, :is_employed, :salary,
            :industry_name, :company_name, :works_by_specialty, :gender, :birth_year
        )
        """
    )
    for row in batch:
        await session.execute(q, row)
    return len(batch)


async def sync_dim_student_and_fact(session: AsyncSession, batch: list[dict[str, Any]]) -> tuple[int, int]:
    """Дублирует строки mart в dim_student и fact_employment (для /stats)."""
    st_ok, fe_ok = 0, 0
    for row in batch:
        ex = (
            await session.execute(
                text("SELECT 1 FROM dwh.dim_student WHERE student_hash = :h LIMIT 1"),
                {"h": row["student_hash"]},
            )
        ).first()
        if not ex:
            try:
                await session.execute(
                    text(
                        """
                        INSERT INTO dwh.dim_student (student_hash, birth_year, gender, graduation_year)
                        VALUES (:h, :by, :g, :gy)
                        """
                    ),
                    {
                        "h": row["student_hash"],
                        "by": row["birth_year"],
                        "g": row["gender"],
                        "gy": row["graduation_year"],
                    },
                )
                st_ok += 1
            except Exception:
                pass
        else:
            st_ok += 1

        try:
            await session.execute(text("DELETE FROM dwh.fact_employment WHERE student_hash = :h"), {"h": row["student_hash"]})
            await session.execute(
                text(
                    """
                    INSERT INTO dwh.fact_employment (
                        student_hash, is_employed, salary, company_name, industry_name, works_by_specialty
                    ) VALUES (
                        :h, :ie, :sal, :cn, :ind, :wbs
                    )
                    """
                ),
                {
                    "h": row["student_hash"],
                    "ie": row["is_employed"],
                    "sal": row["salary"],
                    "cn": row["company_name"],
                    "ind": row["industry_name"],
                    "wbs": row["works_by_specialty"],
                },
            )
            fe_ok += 1
        except Exception:
            try:
                await session.execute(text("DELETE FROM dwh.fact_employment WHERE student_hash = :h"), {"h": row["student_hash"]})
                await session.execute(
                    text(
                        """
                        INSERT INTO dwh.fact_employment (student_hash, is_employed, salary)
                        VALUES (:h, :ie, :sal)
                        """
                    ),
                    {"h": row["student_hash"], "ie": row["is_employed"], "sal": row["salary"]},
                )
                fe_ok += 1
            except Exception:
                pass

    return st_ok, fe_ok


async def run_dashboard_seed(session: AsyncSession, *, recreate_mart_as_table: bool = False) -> dict[str, Any]:
    notes: list[str] = []
    try:
        return await _run_dashboard_seed_impl(session, recreate_mart_as_table=recreate_mart_as_table, notes=notes)
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return {"ok": False, "error": f"Ошибка БД при сидировании: {exc}"}


async def _run_dashboard_seed_impl(
    session: AsyncSession, *, recreate_mart_as_table: bool, notes: list[str]
) -> dict[str, Any]:
    kind = await _relkind(session, "mart", "mart_employment_flat")

    if kind == "v" and not recreate_mart_as_table:
        return {
            "ok": False,
            "error": (
                "mart.mart_employment_flat — это представление (VIEW). "
                "Повторите запрос с recreate_mart_as_table=true (удалит VIEW и создаст таблицу) "
                "или наполните витрину своим ETL."
            ),
        }

    if recreate_mart_as_table or kind is None:
        await recreate_mart_as_table(session)
        notes.append("Витрина пересоздана как таблица mart.mart_employment_flat.")
    elif kind != "r":
        return {"ok": False, "error": f"Неожиданный тип объекта mart.mart_employment_flat: {kind}"}
    else:
        try:
            await session.execute(text("SELECT university_code FROM mart.mart_employment_flat LIMIT 1"))
        except Exception:
            return {
                "ok": False,
                "error": (
                    "В таблице mart.mart_employment_flat нет столбца university_code. "
                    "Запустите с recreate_mart_as_table=true, чтобы пересоздать витрину."
                ),
            }

    deleted = await delete_demo_mart_rows(session)
    if deleted:
        notes.append(f"Удалены предыдущие демо-строки: {deleted}.")

    msk = await _get_city_id(session, "Москва")
    spb = await _get_city_id(session, "Санкт-Петербург")

    u_specs = [
        {
            "code": "MGU",
            "name": "Московский государственный университет имени М. В. Ломоносова",
            "city_id": msk,
            "region": "г. Москва",
            "foundation_year": 1755,
            "rating": 9.8,
            "programs": [
                ("09.03.01", "Информатика и вычислительная техника"),
                ("38.03.01", "Экономика"),
            ],
        },
        {
            "code": "SPbGU",
            "name": "Санкт-Петербургский государственный университет",
            "city_id": spb,
            "region": "г. Санкт-Петербург",
            "foundation_year": 1724,
            "rating": 9.6,
            "programs": [
                ("31.05.01", "Лечебное дело"),
                ("01.03.02", "Прикладная математика и информатика"),
            ],
        },
        {
            "code": "MIPT",
            "name": "Московский физико-технический институт (национальный исследовательский университет)",
            "city_id": msk,
            "region": "г. Москва",
            "foundation_year": 1946,
            "rating": 9.5,
            "programs": [
                ("09.03.01", "Информатика и вычислительная техника"),
                ("09.04.01", "Информатика и вычислительная техника"),
            ],
        },
        {
            "code": "ITMO",
            "name": "Национальный исследовательский университет ИТМО",
            "city_id": spb,
            "region": "г. Санкт-Петербург",
            "foundation_year": 1900,
            "rating": 9.3,
            "programs": [
                ("09.03.01", "Информатика и вычислительная техника"),
                ("38.03.02", "Менеджмент"),
            ],
        },
    ]

    universities: list[dict[str, Any]] = []
    for spec in u_specs:
        uid = await _ensure_university(
            session,
            code=spec["code"],
            name=spec["name"],
            city_id=spec["city_id"],
            foundation_year=spec["foundation_year"],
            rating=spec["rating"],
        )
        universities.append(
            {
                "id": uid,
                "code": spec["code"],
                "name": spec["name"],
                "region": spec["region"],
                "programs": spec["programs"],
            }
        )

    mart_rows = _build_mart_rows(universities)
    inserted = await insert_mart_batch(session, mart_rows)
    notes.append(f"В mart загружено строк: {inserted}.")

    st_n, fe_n = await sync_dim_student_and_fact(session, mart_rows)
    notes.append(f"Синхронизация dim_student / fact_employment (попыток): {st_n} / {fe_n}.")

    demo_logs = [
        {
            "at": utc_now_iso(),
            "level": "info",
            "msg": (
                "Демонстрационные строки записаны напрямую в mart (+ dim_student / fact_employment без staging). "
                "В «История загрузок»: task_id="
                + SEED_DEMO_TASK_ID
                + "; блок «staging» транслирует те же строки из mart для демо-набора "
                "(критерии как при очистке демо: DEMO% или коды "
                + ", ".join(DEMO_MART_UNIVERSITY_CODES)
                + ")."
            ),
        },
    ]
    await persist_import_batch_audit(
        session,
        task_id=SEED_DEMO_TASK_ID,
        source_kind="demo-seed",
        filename=None,
        rows_inserted=inserted,
        errors=[],
        logs=demo_logs,
        etl_fact_rows=fe_n,
        etl_mart_rows=inserted,
        etl_full={
            "mode": "dashboard_seed",
            "universities_seeded": len(universities),
        },
    )

    await session.commit()

    return {
        "ok": True,
        "inserted_mart_rows": inserted,
        "universities": len(universities),
        "notes": notes,
    }

