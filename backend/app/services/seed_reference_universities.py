"""Справочник реальных вузов (dim_city + dim_university), идемпотентная загрузка."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Ограничения dwh.dim_university (PostgreSQL)
_MAX_CODE_LEN = 20
_MAX_NAME_LEN = 255
_MAX_WEB_LEN = 255


def _clip(value: str, max_len: int) -> str:
    if not value:
        return value
    return value.strip()[:max_len]

# (university_code, university_name, city_name, foundation_year, rating, website, description)
REFERENCE_UNIVERSITIES: list[tuple[str, str, str, int, float, str, str]] = [
    (
        "MGU",
        "Московский государственный университет имени М. В. Ломоносова",
        "Москва",
        1755,
        9.8,
        "https://msu.ru",
        "Крупнейший классический университет России. Лидер в области фундаментальной науки и подготовки кадров высшей квалификации. Входит в топ-100 мировых рейтингов.",
    ),
    (
        "SPbGU",
        "Санкт-Петербургский государственный университет",
        "Санкт-Петербург",
        1724,
        9.6,
        "https://spbu.ru",
        "Один из старейших и ведущих университетов страны. Сильные школы в математике, физике, филологии и юриспруденции. Расположен в историческом центре Петербурга.",
    ),
    (
        "MIPT",
        "Московский физико-технический институт (национальный исследовательский университет)",
        "Москва",
        1946,
        9.5,
        "https://mipt.ru",
        "Элитарный вуз физтеховской системы. Готовит инженеров и учёных мирового уровня в области физики, математики, компьютерных наук. Тесная связь с базовыми кафедрами РАН и высокотехнологичными компаниями.",
    ),
    (
        "HSE",
        "Национальный исследовательский университет «Высшая школа экономики»",
        "Москва",
        1992,
        9.4,
        "https://hse.ru",
        "Ведущий экономический и социально-гуманитарный университет. Известен сильными программами по экономике, социологии, менеджменту и компьютерным наукам. Активно внедряет проектное обучение.",
    ),
    (
        "ITMO",
        "Национальный исследовательский университет ИТМО",
        "Санкт-Петербург",
        1900,
        9.3,
        "https://itmo.ru",
        "Победитель чемпионатов мира по программированию. Специализируется на информационных технологиях, фотонике и инженерии. Входит в топ-100 по Computer Science.",
    ),
    (
        "Bauman",
        "Московский государственный технический университет имени Н. Э. Баумана",
        "Москва",
        1830,
        9.2,
        "https://bmstu.ru",
        "Флагман российского инженерного образования. Готовит специалистов в области машиностроения, робототехники, аэрокосмической техники. Обладает мощной лабораторной базой.",
    ),
    (
        "TomskSU",
        "Томский государственный университет",
        "Томск",
        1878,
        9.0,
        "https://tsu.ru",
        "Первый университет в Сибири. Крупный исследовательский центр в области физики, химии, биологии и гуманитарных наук. Входит в Проект 5-100.",
    ),
    (
        "NSU",
        "Новосибирский национальный исследовательский государственный университет",
        "Новосибирск",
        1959,
        9.1,
        "https://nsu.ru",
        "Создан на базе Сибирского отделения РАН. Выпускники работают в ведущих научных центрах мира. Сильные физико-математическая и естественнонаучная школы.",
    ),
    (
        "KFU",
        "Казанский (Приволжский) федеральный университет",
        "Казань",
        1804,
        8.8,
        "https://kpfu.ru",
        "Один из старейших университетов России. Крупный образовательный и научный центр Поволжья. Особо известен медицинским и химическим факультетами.",
    ),
    (
        "UrFU",
        "Уральский федеральный университет имени первого Президента России Б. Н. Ельцина",
        "Екатеринбург",
        1920,
        8.5,
        "https://urfu.ru",
        "Ключевой вуз Урала. Объединяет инженерные, естественнонаучные и гуманитарные направления. Активно сотрудничает с промышленными предприятиями региона.",
    ),
    (
        "RUDN",
        "Российский университет дружбы народов имени Патриса Лумумбы",
        "Москва",
        1960,
        8.3,
        "https://rudn.ru",
        "Самый интернациональный вуз России. Обучает студентов из 150 стран. Сильные программы по медицине, юриспруденции и международным отношениям.",
    ),
    (
        "SFEDU",
        "Южный федеральный университет",
        "Ростов-на-Дону",
        1915,
        8.0,
        "https://sfedu.ru",
        "Крупнейший научно-образовательный центр Юга России. Объединяет шесть академий и институтов. Развивает направления от нанотехнологий до архитектуры.",
    ),
    (
        "FEFU",
        "Дальневосточный федеральный университет",
        "Владивосток",
        1899,
        8.2,
        "https://dvfu.ru",
        "Современный кампус на острове Русский. Ведущий вуз Дальнего Востока с акцентом на морские технологии, биотехнологии и востоковедение.",
    ),
    (
        "SiberianFU",
        "Сибирский федеральный университет",
        "Красноярск",
        2006,
        7.9,
        "https://sfu-kras.ru",
        "Образован путём слияния четырёх вузов. Крупнейший вуз Сибири по числу студентов. Специализируется на лесном деле, металлургии и экономике региона.",
    ),
    (
        "Lobachevsky",
        "Нижегородский государственный университет имени Н. И. Лобачевского",
        "Нижний Новгород",
        1916,
        8.1,
        "https://unn.ru",
        "Ведущий классический университет Приволжья. Известен научными школами в области радиофизики, химии и IT. Активно участвует в федеральных программах поддержки науки.",
    ),
]


async def _city_id(session: AsyncSession, city_name: str) -> int:
    """Создаёт город при необходимости. Неудачные варианты INSERT изолированы savepoint’ом (иначе транзакция PG «aborted»)."""
    r = (await session.execute(text("SELECT city_id FROM dwh.dim_city WHERE city_name = :n LIMIT 1"), {"n": city_name})).first()
    if r:
        return int(r[0])

    attempts: list[tuple[str, dict]] = [
        ("INSERT INTO dwh.dim_city (city_name) VALUES (:n) RETURNING city_id", {"n": city_name}),
        (
            "INSERT INTO dwh.dim_city (city_name, region_name) VALUES (:n, :r) RETURNING city_id",
            {"n": city_name, "r": city_name},
        ),
        (
            """
            INSERT INTO dwh.dim_city (city_name, region_id)
            SELECT :n, r.region_id
            FROM dwh.dim_region r
            LIMIT 1
            RETURNING city_id
            """,
            {"n": city_name},
        ),
    ]
    last_exc: Exception | None = None
    for sql, params in attempts:
        try:
            async with session.begin_nested():
                ins = await session.execute(text(sql), params)
                return int(ins.scalar_one())
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            continue
    raise last_exc if last_exc else RuntimeError(f"Не удалось создать город «{city_name}» в dwh.dim_city")


async def seed_reference_universities(session: AsyncSession) -> dict[str, int]:
    """Обновляет или добавляет вузы из справочника. Не делает commit."""
    cities = {row[2] for row in REFERENCE_UNIVERSITIES}
    for city in sorted(cities):
        await _city_id(session, city)

    upserted = 0
    for code, name, city_name, fy, rating, website, desc in REFERENCE_UNIVERSITIES:
        code_db = _clip(code, _MAX_CODE_LEN)
        name_db = _clip(name, _MAX_NAME_LEN)
        web_db = _clip(website, _MAX_WEB_LEN) if website else None
        cid = await _city_id(session, city_name)
        existing = (
            await session.execute(
                text("SELECT university_id FROM dwh.dim_university WHERE university_code = :c LIMIT 1"),
                {"c": code_db},
            )
        ).first()
        if existing:
            await session.execute(
                text(
                    """
                    UPDATE dwh.dim_university
                    SET university_name = :name,
                        city_id = :cid,
                        foundation_year = :fy,
                        rating = :rating,
                        website = :web,
                        description = :desc
                    WHERE university_code = :code
                    """
                ),
                {
                    "code": code_db,
                    "name": name_db,
                    "cid": cid,
                    "fy": fy,
                    "rating": rating,
                    "web": web_db,
                    "desc": desc,
                },
            )
        else:
            await session.execute(
                text(
                    """
                    INSERT INTO dwh.dim_university (
                        university_code, university_name, city_id, foundation_year, rating, website, description
                    ) VALUES (
                        :code, :name, :cid, :fy, :rating, :web, :desc
                    )
                    """
                ),
                {
                    "code": code_db,
                    "name": name_db,
                    "cid": cid,
                    "fy": fy,
                    "rating": rating,
                    "web": web_db,
                    "desc": desc,
                },
            )
        upserted += 1

    return {"universities_upserted": upserted, "cities": len(cities)}
