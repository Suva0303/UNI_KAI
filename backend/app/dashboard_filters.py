"""Общие SQL-фрагменты фильтров для публичного API (mart.mart_employment_flat)."""

from __future__ import annotations

from typing import Any

_LEVEL_LIKE: dict[int, str] = {
    1: "%.03.%",
    2: "%.05.%",
    3: "%.04.%",
    4: "%.06.%",
    5: "%.07.%",
}

_EDUCATION_LEVEL_LABELS: dict[int, str] = {
    1: "Бакалавриат",
    2: "Специалитет",
    3: "Магистратура",
    4: "Аспирантура",
    5: "Докторантура",
}


def education_level_options_public() -> list[dict[str, int | str | None]]:
    """Опции фильтра «Уровень образования» для UI (level_id=None — без фильтра по уровню)."""
    out: list[dict[str, int | str | None]] = [{"level_id": None, "label": "Все"}]
    for lid in sorted(_LEVEL_LIKE.keys()):
        out.append({"level_id": lid, "label": _EDUCATION_LEVEL_LABELS.get(lid, str(lid))})
    return out


def merge_params(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = {**base}
    out.update(extra)
    return out


def filter_where_sql(
    *,
    level_id: int | None,
    region_id: int | None,
    university_id: int | None,
    program_code: str | None,
    graduation_year: int | None = None,
    params: dict[str, Any],
    alias: str = "m",
) -> str:
    """Append AND clauses; mutates params with bound keys."""
    clauses: list[str] = []

    if graduation_year is not None:
        clauses.append(f"{alias}.graduation_year = :_dash_graduation_year")
        params["_dash_graduation_year"] = graduation_year

    if level_id is not None and level_id in _LEVEL_LIKE:
        key = "_dash_level_pat"
        clauses.append(f"COALESCE({alias}.program_code, '') LIKE :{key}")
        params[key] = _LEVEL_LIKE[level_id]

    if region_id is not None:
        clauses.append(
            f"""
            {alias}.region_name = (
                SELECT s.region_name FROM (
                    SELECT DISTINCT region_name,
                           ROW_NUMBER() OVER (ORDER BY region_name)::int AS rid
                    FROM mart.mart_employment_flat
                    WHERE region_name IS NOT NULL AND TRIM(region_name) <> ''
                ) s
                WHERE s.rid = :_dash_region_id
            )
            """.strip()
        )
        params["_dash_region_id"] = region_id

    if university_id is not None:
        clauses.append(
            f"""
            {alias}.university_name = (
                SELECT u.university_name FROM dwh.dim_university u
                WHERE u.university_id = :_dash_university_id
            )
            """.strip()
        )
        params["_dash_university_id"] = university_id

    if program_code is not None and str(program_code).strip() != "":
        clauses.append(f"{alias}.program_code = :_dash_program_code")
        params["_dash_program_code"] = program_code.strip()

    if not clauses:
        return ""
    return " AND " + " AND ".join(clauses)
