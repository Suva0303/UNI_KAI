"""Проверка строк перед загрузкой в staging.stg_graduates — типы, обязательность, допустимое содержимое."""

from __future__ import annotations

import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

_PLACEHOLDER_TOKENS = frozenset(
    {
        "n/a",
        "na",
        "#n/a",
        "null",
        "none",
        "nan",
        "-",
        "—",
        "нет данных",
        "не указано",
    }
)

_GY_MIN = 1950
_GY_MAX = 2100
_BY_MIN = 1940
_BY_MAX = 2015

_BOOL_TRUE = frozenset({"1", "true", "t", "yes", "y", "да", "д"})
_BOOL_FALSE = frozenset({"0", "false", "f", "no", "n", "нет", "н"})

# Лимиты длины текстовых полей
_TEXT_MAX: dict[str, int] = {
    "local_student_id": 256,
    "university_code": 64,
    "program_code": 128,
    "program_name": 512,
    "specialization_edu_code": 128,
    "specialization_edu_name": 512,
    "gender": 32,
    "company_name": 512,
    "inn": 12,
    "industry_name": 256,
    "position": 256,
    "specialization_work_code": 128,
    "specialization_work_name": 512,
}


def _empty(val: object | None) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _is_placeholder_like(val: object | None) -> bool:
    """Как «пусто» для обязательных полей и пропуска необязательных: N/A, «-», null и т.п."""
    if _empty(val):
        return True
    if isinstance(val, str):
        return val.strip().lower() in _PLACEHOLDER_TOKENS
    return False


def row_is_effectively_blank(raw_row: dict[str, Any], column_names: list[str]) -> bool:
    """Все указанные колонки пустые или распознанные плейсхолдеры — строку импорт пропускает."""
    return all(_empty(raw_row.get(c)) or _is_placeholder_like(raw_row.get(c)) for c in column_names)


def _preview(val: object, max_len: int = 80) -> str:
    s = str(val).replace("\n", " ").strip()
    return s[:max_len] + ("…" if len(s) > max_len else "")


def _type_name_for_message(val: object) -> str:
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "логическое значение"
    if isinstance(val, int):
        return "целое число"
    if isinstance(val, float):
        return "число с плавающей точкой"
    return type(val).__name__


def _parse_int_strict(val: object | None) -> int | None:
    """Год выпуска/рождения: строка, int; числа Excel 2020.0 только с нулевой дробью."""
    if _empty(val) or _is_placeholder_like(val):
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        if not math.isfinite(val) or abs(val - round(val)) > 1e-9:
            return None
        return int(round(val))
    s = str(val).strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        try:
            x = float(s)
        except ValueError:
            return None
        if not math.isfinite(x) or abs(x - round(x)) > 1e-9:
            return None
        return int(round(x))
    return None


def _integral_string_for_identifier(val: object) -> tuple[str | None, str | None]:
    """local_student_id / university_code: целое int/float из Excel или строка; bool — ошибка."""
    if isinstance(val, bool):
        return None, "логическое значение"
    if isinstance(val, int):
        return str(val), None
    if isinstance(val, float):
        if not math.isfinite(val):
            return None, "неконечное число"
        if abs(val - round(val)) > 1e-9:
            return None, "ожидается целое значение без дробной части"
        return str(int(round(val))), None
    return None, None


def _bool_field_issue(val: object | None, col: str) -> str | None:
    if _empty(val) or _is_placeholder_like(val):
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, int | float):
        if val in (0, 1) or val == 0.0 or val == 1.0:
            return None
        return f"{col}: ожидается логическое значение (да/нет или 0/1), получено {_type_name_for_message(val)} «{_preview(val)}»"
    s = str(val).strip().lower()
    if s in _BOOL_TRUE or s in _BOOL_FALSE:
        return None
    return f"{col}: ожидается да/нет, 0/1, true/false; получено «{_preview(val)}»"


def _salary_issues(val: object | None, col: str) -> str | None:
    if _empty(val) or _is_placeholder_like(val):
        return None
    if isinstance(val, bool):
        return f"{col}: некорректный тип — логическое значение вместо суммы"
    if isinstance(val, int | float):
        try:
            dec = Decimal(str(val))
        except InvalidOperation:
            return f"{col}: некорректное числовое значение зарплаты «{_preview(val)}»"
        if dec < 0:
            return f"{col}: зарплата не может быть отрицательной «{_preview(val)}»"
        return None
    s = str(val).strip().replace(" ", "").replace(",", ".").replace("\u00a0", "")
    try:
        dec = Decimal(s)
    except InvalidOperation:
        return f"{col}: некорректное числовое значение зарплаты «{_preview(val)}»"
    if dec < 0:
        return f"{col}: зарплата не может быть отрицательной «{_preview(val)}»"
    return None


def _hire_date_issues(val: object | None, col: str) -> str | None:
    if _empty(val) or _is_placeholder_like(val):
        return None
    if isinstance(val, int | float | bool):
        return f"{col}: ожидается дата в виде строки, получено {_type_name_for_message(val)} «{_preview(val)}»"
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            datetime.strptime(s, fmt)
            return None
        except ValueError:
            continue
    return f"{col}: ожидается дата (ГГГГ-ММ-ДД, ДД.ММ.ГГГГ или ДД/ММ/ГГГГ), получено «{_preview(val)}»"


def _finalize_text_value(s: str, col: str, prefix: str) -> list[str]:
    """Проверки после получения финальной строки (длина, управляющие символы)."""
    out: list[str] = []
    if _CONTROL_CHARS.search(s):
        out.append(f"{prefix}, колонка «{col}»: недопустимы управляющие символы в значении")
        return out
    if "\n" in s or "\r" in s:
        out.append(f"{prefix}, колонка «{col}»: перенос строки внутри ячейки недопустим")
        return out
    max_len = _TEXT_MAX.get(col, 512)
    if len(s) > max_len:
        out.append(f"{prefix}, колонка «{col}»: длина текста {len(s)} симв., максимум {max_len}")
    return out


def _identifier_field_issues(val: object | None, col: str, prefix: str) -> list[str]:
    """Обязательные идентификаторы: строка или целое число из Excel."""
    if _empty(val) or _is_placeholder_like(val):
        return [f"{prefix}, колонка «{col}»: обязательное поле не заполнено"]
    num_s, num_err = _integral_string_for_identifier(val)
    if num_s is not None:
        return _finalize_text_value(num_s, col, prefix)
    if num_err:
        return [
            f"{prefix}, колонка «{col}»: некорректный тип содержимого — {num_err}, получено {_type_name_for_message(val)} «{_preview(val)}»"
        ]
    s = str(val).strip()
    if s == "":
        return [f"{prefix}, колонка «{col}»: обязательное поле не заполнено"]
    return _finalize_text_value(s, col, prefix)


def _optional_text_issues(val: object | None, col: str, prefix: str) -> list[str]:
    """Необязательный текст; плейсхолдеры игнорируются как «пусто»."""
    if _empty(val) or _is_placeholder_like(val):
        return []
    if isinstance(val, bool | int | float):
        return [
            f"{prefix}, колонка «{col}»: ожидается текстовая строка, получено {_type_name_for_message(val)} «{_preview(val)}»"
        ]
    s = str(val).strip()
    if s == "":
        return []
    return _finalize_text_value(s, col, prefix)


def _inn_issues(val: object | None, prefix: str) -> list[str]:
    col = "inn"
    if _empty(val) or _is_placeholder_like(val):
        return []
    if isinstance(val, bool | int | float):
        return [
            f"{prefix}, колонка «{col}»: ожидается строка с цифрами ИНН, получено {_type_name_for_message(val)} «{_preview(val)}»"
        ]
    optional_shape = _optional_text_issues(val, col, prefix)
    if optional_shape:
        return optional_shape
    s = re.sub(r"\s+", "", str(val).strip())
    if not re.fullmatch(r"\d{10}|\d{12}", s):
        return [
            f"{prefix}, колонка «{col}»: ожидается ИНН юр. лица (10 цифр) или физ. лица (12 цифр), получено «{_preview(val)}»"
        ]
    return []


def collect_staging_row_issues(raw_row: dict[str, Any], data_row_number: int) -> list[str]:
    """
    Проблемы для строки данных (первая после заголовка = 1).

    Вызов для полностью пустых строк запрещён: их отсекает импорт через row_is_effectively_blank.
    """
    r = raw_row
    issues: list[str] = []
    prefix = f"Строка {data_row_number}"

    issues.extend(_identifier_field_issues(r.get("local_student_id"), "local_student_id", prefix))
    issues.extend(_identifier_field_issues(r.get("university_code"), "university_code", prefix))

    gy_raw = r.get("graduation_year")
    if _empty(gy_raw) or _is_placeholder_like(gy_raw):
        issues.append(f"{prefix}, колонка «graduation_year»: обязательное поле не заполнено")
    else:
        gy = _parse_int_strict(gy_raw)
        if gy is None:
            issues.append(
                f"{prefix}, колонка «graduation_year»: ожидается целое число года, получено {_type_name_for_message(gy_raw)} «{_preview(gy_raw)}»"
            )
        elif gy < _GY_MIN or gy > _GY_MAX:
            issues.append(
                f"{prefix}, колонка «graduation_year»: год вне допустимого диапазона ({_GY_MIN}–{_GY_MAX})"
            )

    by_raw = r.get("birth_year")
    if not _empty(by_raw) and not _is_placeholder_like(by_raw):
        by = _parse_int_strict(by_raw)
        if by is None:
            issues.append(
                f"{prefix}, колонка «birth_year»: ожидается целое число, получено {_type_name_for_message(by_raw)} «{_preview(by_raw)}»"
            )
        elif by < _BY_MIN or by > _BY_MAX:
            issues.append(f"{prefix}, колонка «birth_year»: год вне допустимого диапазона ({_BY_MIN}–{_BY_MAX})")

    for col in (
        "program_code",
        "program_name",
        "specialization_edu_code",
        "specialization_edu_name",
        "gender",
        "company_name",
        "industry_name",
        "position",
        "specialization_work_code",
        "specialization_work_name",
    ):
        issues.extend(_optional_text_issues(r.get(col), col, prefix))

    issues.extend(_inn_issues(r.get("inn"), prefix))

    for col in ("is_employed", "works_by_specialty"):
        detail = _bool_field_issue(r.get(col), col)
        if detail:
            tail = detail.split(":", 1)[1].strip()
            issues.append(f"{prefix}, колонка «{col}»: {tail}")

    if salary_err := _salary_issues(r.get("salary"), "salary"):
        tail = salary_err.split(":", 1)[1].strip()
        issues.append(f"{prefix}, колонка «salary»: {tail}")

    if hire_err := _hire_date_issues(r.get("hire_date"), "hire_date"):
        tail = hire_err.split(":", 1)[1].strip()
        issues.append(f"{prefix}, колонка «hire_date»: {tail}")

    return issues
