-- URL логотипа/фото вуза (файл храните отдельно; в БД — ссылка).
ALTER TABLE dwh.dim_university
    ADD COLUMN IF NOT EXISTS logo_url TEXT;

COMMENT ON COLUMN dwh.dim_university.logo_url IS 'URL изображения вуза (HTTPS или относительный путь к статике)';
