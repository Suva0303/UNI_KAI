-- Схема public в типовой БД уже есть; отдельно создавать не нужно.
-- Если когда-то её удалили: CREATE SCHEMA IF NOT EXISTS public;

CREATE SCHEMA IF NOT EXISTS extensions;

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;
