-- =============================================================================
-- Staging: stg_graduates — автоматические student_hash, load_timestamp и id.
-- =============================================================================
--
-- Алгоритм student_hash (дубликат описания см. комментарий к build_student_hash
-- в app/services/import_service.py; значения должны совпадать с триггером ниже).
--
-- 1) S := TRIM(local_student_id::text), допускается пустая строка только если столбцы
--    приходят некорректно; на этапе импорта они обязательны.
-- 2) U := TRIM(university_code::text)
-- 3) Байтовая строка B := convert_to(S, 'UTF8') || convert_to(U, 'UTF8')
--    (конкатенация UTF-8 последовательностей, без разделителя между полями).
-- 4) H := SHA-256(B); student_hash := encode(H, 'hex') — шестнадцатеричная строка
--    из 64 символов в нижнем регистре.
--
-- Перед INSERT/UPDATE ключевых столбцов триггер пересчитывает student_hash заново,
-- переданное клиентом значение не используется как истина.
--
-- Зависимость: расширение pgcrypto (функции digest и convert_to уже в ядре 15+ —
-- digest в pgcrypto; convert_to встроенное).
--

CREATE SCHEMA IF NOT EXISTS staging;

CREATE SCHEMA IF NOT EXISTS public;

CREATE SCHEMA IF NOT EXISTS extensions;

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;

CREATE OR REPLACE FUNCTION staging.stg_graduates_set_student_hash()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.student_hash := encode(
        extensions.digest(
            convert_to(trim(BOTH FROM coalesce(NEW.local_student_id::text, '')), 'UTF8')
                || convert_to(trim(BOTH FROM coalesce(NEW.university_code::text, '')), 'UTF8'),
            'sha256'
        ),
        'hex'
    );
    RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS staging.stg_graduates (
    id                 BIGSERIAL PRIMARY KEY,
    local_student_id   TEXT NOT NULL,
    university_code    TEXT NOT NULL,
    program_code       TEXT,
    program_name       TEXT,
    specialization_edu_code TEXT,
    specialization_edu_name TEXT,
    birth_year         INTEGER,
    graduation_year    INTEGER,
    gender             TEXT,
    is_employed        BOOLEAN,
    company_name       TEXT,
    inn                TEXT,
    industry_name      TEXT,
    "position"         TEXT,
    salary             NUMERIC,
    specialization_work_code TEXT,
    specialization_work_name TEXT,
    hire_date          DATE,
    works_by_specialty BOOLEAN,
    task_id            TEXT NOT NULL,
    student_hash       CHARACTER VARYING(64) NOT NULL DEFAULT '',
    load_timestamp     TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', NOW())
);

ALTER TABLE staging.stg_graduates
    ALTER COLUMN load_timestamp SET DEFAULT timezone('utc', NOW());

DROP TRIGGER IF EXISTS trg_stg_graduates_student_hash ON staging.stg_graduates;

CREATE TRIGGER trg_stg_graduates_student_hash
    BEFORE INSERT OR UPDATE OF local_student_id, university_code
    ON staging.stg_graduates
    FOR EACH ROW
    EXECUTE PROCEDURE staging.stg_graduates_set_student_hash();
