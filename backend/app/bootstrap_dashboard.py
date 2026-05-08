from __future__ import annotations

import logging

from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.services.seed_dashboard import run_dashboard_seed
from app.services.seed_reference_universities import seed_reference_universities

logger = logging.getLogger(__name__)


async def ensure_mart_etl_updated_at_column() -> None:
    """Добавляет колонку etl_updated_at при отсутствии."""
    async with SessionLocal() as session:
        try:
            await session.execute(text("CREATE SCHEMA IF NOT EXISTS mart"))
            await session.execute(
                text(
                    "ALTER TABLE mart.mart_employment_flat ADD COLUMN IF NOT EXISTS etl_updated_at TIMESTAMPTZ"
                )
            )
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.warning("Не удалось добавить mart.mart_employment_flat.etl_updated_at (VIEW или нет таблицы): %s", exc)


async def ensure_articles_table() -> None:
    """Создаёт public.articles при необходимости."""
    async with SessionLocal() as session:
        try:
            await session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
            await session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS public.articles (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL DEFAULT '',
                        excerpt TEXT,
                        content TEXT,
                        category TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            await session.execute(text("ALTER TABLE public.articles ADD COLUMN IF NOT EXISTS image_url TEXT"))
            await session.commit()
        except Exception:  # noqa: BLE001
            await session.rollback()
            logger.exception("Не удалось создать public.articles (проверьте права на схему public в БД UNI)")
            return
    await seed_curated_public_articles()


def _pic(seed: str) -> str:
    """URL обложки по seed (picsum.photos)."""
    return f"https://picsum.photos/seed/{seed}/1200/630"


_CURATED_ARTICLES: list[dict[str, str | None]] = [
    {
        "title": "Минобрнауки усилит ограничения платного приёма в вузы",
        "excerpt": "Ведомство намерено совместно с Рособрнадзором и законодателями ужесточить контроль за долей платных мест.",
        "category": "Вузы и приём",
        "image_url": _pic("uni-curated-paid-admission"),
        "content": """Весной 2025 года Минобрнауки России заявило о намерении усилить работу по ограничению платного приёма в вузы. Речь идёт о согласованных действиях с Рособрнадзором и профильным комитетом Госдумы: цель — сделать платный контур предсказуемее для абитуриентов и снизить риски «перегретых» наборов на направления, которые слабее закреплены спросом на рынке труда.

Абитуриентам разумно заранее смотреть не только минимальные баллы прошлых лет, но и число мест по договору по выбранной программе и динамику трудоустройства выпускников (если эти данные доступны через вуз или открытые рейтинги).


Источник: РИА Новости, 18.03.2025 — https://ria.ru/20250318/minobrnauki-2005772623.html""",
    },
    {
        "title": "Новые правила приёма в вузы с 1 марта 2025 года",
        "excerpt": "Обновились сроки и лимиты на подачу заявлений, появилась интеграция с сервисами «Госуслуг», уточнены требования к вступительным экзаменам.",
        "category": "Правила приёма",
        "image_url": _pic("uni-curated-admission-rules"),
        "content": """С первого марта 2025 года для приёма в российские вузы действует обновлённый регламент. Ключевые практические моменты для абитуриента: уточнённые календарные рамки кампании, ограничение числа направлений, по которым можно одновременно участвовать в конкурсе, а также расширение сценариев подачи документов и согласия на зачисление через «Госуслуги» — это снижает бумажную нагрузку, но требует внимательности к дедлайнам в личном кабинете.

Перед подачей документов полезно сверить требования конкретного вуза (иногда правила кампуса жёстче общих) и заранее подготовить результаты экзаменов, которые вуз признаёт в 2025 году.


Источник: РИА Новости, 01.03.2025 — https://ria.ru/20250301/rossija-2002382298.html""",
    },
    {
        "title": "Поступление в бакалавриат после колледжа: изменения после I чтения в Госдуме",
        "excerpt": "Законодатели обсуждают ужесточение правил перехода из среднего профессионального образования в вуз.",
        "category": "Законодательство",
        "image_url": _pic("uni-curated-college-to-uni"),
        "content": """Весной 2025 года в Госдуме Российской Федерации прошло первое чтение инициативы об ужесточении условий поступления на программы бакалавриата для лиц со средним профессиональным образованием. Суть дискуссии — сделать траекторию «колледж → вуз» более прозрачной для конкурсных отборов и снять напряжение между «короткими» профессиональными программами и классической подготовкой к высшему звену.

Выпускникам колледжа важно отслеживать финальную редакцию (после чтений текст может меняться) и сохранять договорную/документальную связку между дипломом СПО и тем пакетом вступительных испытаний, который требует выбранный вуз.


Источник: Коммерсантъ — https://www.kommersant.ru/doc/7586202""",
    },
    {
        "title": "Правительство поддержало ограничения на платный приём в университеты",
        "excerpt": "Поправки к закону «Об образовании» затрагивают механизм установления предельной доли платных мест.",
        "category": "Регулирование",
        "image_url": _pic("uni-curated-gov-placements"),
        "content": """В конце апреля 2025 года в публичном поле сообщалось, что профильное звено правительства поддержало поправки к закону об образовании, которые расширяют возможность регулировать платный приём в вузах. Для наблюдателя это означает: доля платных мест и распределение бюджетных квот могут становиться управляемыми параметрами «сверху», а университетам — нужнее данные по трудоустройству и релевантности программ.

Абитуриентам стоит при выборе вуза смотреть не только на стоимость договора, но и на устойчивость профиля (аккредитация, отзывы работодателей, открытые рейтинги занятости).


Источник: РИА «Европейско-Азиатские Новости», 30.04.2025 — https://eanews.ru/rossiya/20250430105106/v-pravitelstve-rossii-podderzhali-ogranicheniya-na-platnyy-priem-v-universitety""",
    },
    {
        "title": "Трудоустройство выпускников 2024 года: что показывают открытые оценки",
        "excerpt": "По отдельным оценкам, около двух третей выпускников бакалавриата и специалитета находят работу; по магистратуре доля выше.",
        "category": "Рынок труда",
        "image_url": _pic("uni-curated-graduate-jobs"),
        "content": """В обсуждениях 2024–2025 годов периодически фигурируют агрегированные оценки по трудоустройству выпускников программ бакалавриата, специалитета и магистратуры. Важно понимать методологию: разные источники считают «трудоустроенным» по-разному (официальная занятость, ответы выпускников, данные работодателей), поэтому сравнивать проценты между отчётами можно только с оговорками.

Для студента полезнее не «средняя по больнице», а конкретная программа: стажировки, партнёрства вуза с отраслью, доля выпускников, подтвердивших трудоустройство по специальности (если вуз публикует такие метрики).


Источник: Корпорация МСП (пресс-материал) — https://corpmsp.ru/about/press/news/novosti-ekonomiki/v_rf_trudoustroeny_pochti_70_vypusknikov_bakalavriata_i_spetsialiteta_2024_goda/""",
    },
]


async def seed_curated_public_articles() -> None:
    """Вставляет демо-статьи, если заголовок ещё не встречался."""
    async with SessionLocal() as session:
        try:
            for row in _CURATED_ARTICLES:
                await session.execute(
                    text(
                        """
                        INSERT INTO public.articles (title, excerpt, content, category, image_url)
                        SELECT :title, :excerpt, :content, :category, :image_url
                        WHERE NOT EXISTS (SELECT 1 FROM public.articles a WHERE a.title = :title)
                        """
                    ),
                    row,
                )
            await session.commit()
        except Exception:  # noqa: BLE001
            await session.rollback()
            logger.exception("Не удалось добавить демо-статьи в public.articles")


async def ensure_dashboard_populated() -> None:
    """При AUTO_BOOTSTRAP_DASHBOARD=true заполняет пустую витрину демо-данными."""
    if not settings.auto_bootstrap_dashboard:
        return

    async with SessionLocal() as session:
        try:
            dim_cnt = int(await session.scalar(text("SELECT COUNT(*)::bigint FROM dwh.dim_university")) or 0)
        except Exception:  # noqa: BLE001
            dim_cnt = -1
        if dim_cnt == 0:
            try:
                ref = await seed_reference_universities(session)
                await session.commit()
                logger.info(
                    "Справочник вузов (демо): добавлено %s записей (%s городов)",
                    ref.get("universities_upserted"),
                    ref.get("cities"),
                )
            except Exception:  # noqa: BLE001
                await session.rollback()
                logger.exception("Справочник вузов не загружен (проверьте dwh.dim_city / dwh.dim_university)")
    async with SessionLocal() as session:
        missing_relation = False
        count = 0
        try:
            count = int(await session.scalar(text("SELECT COUNT(*) FROM mart.mart_employment_flat")) or 0)
        except Exception as exc:  # noqa: BLE001
            missing_relation = True
            logger.warning("mart.mart_employment_flat недоступна: %s", exc)
        if count > 0:
            return
        recreate = missing_relation
        res = await run_dashboard_seed(session, recreate_mart_as_table=recreate)
        if res.get("ok"):
            logger.info("Дашборд: загружены демо-данные (%s)", res.get("notes"))
            return
        logger.warning("Дашборд: первая попытка сидирования не удалась: %s", res.get("error"))
    if not recreate:
        async with SessionLocal() as session:
            res = await run_dashboard_seed(session, recreate_mart_as_table=True)
            if res.get("ok"):
                logger.info("Дашборд: витрина пересоздана и заполнена (%s)", res.get("notes"))
            else:
                logger.error("Дашборд: не удалось заполнить витрину: %s", res.get("error"))
    else:
        logger.error("Дашборд: не удалось заполнить витрину после пересоздания (проверьте схему dwh / mart).")
