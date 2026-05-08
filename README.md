# UNI — дашборд выпускников и админка

Веб-приложение: публичный дашборд по витрине `mart`, каталог вузов, статьи; админка — загрузка CSV, справочник вузов, JWT-авторизация.

## Требования

- Python 3.11+
- Node.js 20+ (npm)
- PostgreSQL с базой данных **`UNI`** (имя базы обязательно `uni` — проверяется в `app.config`)

## База данных

1. Создайте БД `UNI` и пользователя с правами на неё.
2. При необходимости выполните SQL из каталога `backend/migrations/` (расширения, триггеры staging и т.д.) — порядок зависит от вашей схемы; для первого развёртывания ориентируйтесь на ошибки при старте API и документацию к миграциям в репозитории.

## Бэкенд

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows; на Unix: cp .env.example .env
```

Отредактируйте `backend/.env`:

| Переменная | Описание |
|------------|----------|
| `DATABASE_URL` | `postgresql+asyncpg://USER:PASSWORD@HOST:5432/UNI` |
| `JWT_SECRET` | Случайная длинная строка |
| `ADMIN_LOGIN` / `ADMIN_PASSWORD` | Учётная запись админки |
| `AUTO_BOOTSTRAP_DASHBOARD` | `true` — при пустой витрине подставить демо-данные при старте; `false` — только ваши данные |

Запуск API:

```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Проверка: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## Фронтенд (разработка)

В отдельном терминале:

```bash
cd frontend
npm install
npm run dev
```

На Windows для прокси `/api` на порт 8000:

```bash
npm run dev:win
```

Сайт: [http://127.0.0.1:5173](http://127.0.0.1:5173)

Переменная `VITE_API_BASE_URL`: для dev обычно не задаётся (запросы идут на тот же origin, Vite проксирует `/api`). Если задаёте URL бэкенда, **не** добавляйте суффикс `/api` (иначе путь удвоится).

## Сборка для продакшена

```bash
cd frontend
npm run build
```

Каталог `frontend/dist` должен быть доступен бэкенду: он ищет `frontend/dist` относительно корня репозитория или текущей рабочей директории. Запуск только API после сборки:

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Статика и клиентские маршруты отдаются через FastAPI.

## Структура

- `backend/app` — FastAPI, роуты, сервисы импорта и сидирования
- `frontend/src` — Vue 3, Pinia, Vite

Файл `backend/.env` в репозиторий не коммитьте; используйте `backend/.env.example`.
