import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.bootstrap_dashboard import (
    ensure_articles_table,
    ensure_dashboard_populated,
    ensure_mart_etl_updated_at_column,
)
from app.routers import admin, public

_LOGGER = logging.getLogger(__name__)


def _discover_spa_dist() -> Path | None:
    """Каталог `frontend/dist` относительно корня проекта или текущей рабочей директории."""
    project_root = Path(__file__).resolve().parents[2]
    bases: list[Path] = []
    seen: set[str] = set()

    def _maybe_add(candidate: Path) -> None:
        try:
            r = candidate.resolve()
        except OSError:
            return
        k = str(r)
        if k not in seen:
            seen.add(k)
            bases.append(r)

    _maybe_add(project_root)
    _maybe_add(Path.cwd())
    _maybe_add(Path.cwd() / "project")

    for base in bases:
        dist = (base / "frontend" / "dist").resolve()
        idx = dist / "index.html"
        if idx.is_file():
            return dist
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_mart_etl_updated_at_column()
    await ensure_dashboard_populated()
    await ensure_articles_table()
    yield


app = FastAPI(title="UNI API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(public.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


_SPA_DIST = _discover_spa_dist()
_SPA_INDEX = _SPA_DIST / "index.html" if _SPA_DIST else None

if _SPA_DIST is not None and _SPA_INDEX is not None and _SPA_INDEX.is_file():
    _LOGGER.info("Статика SPA: %s", _SPA_DIST)
    _assets_dir = _SPA_DIST / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="spa_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_history_fallback(full_path: str) -> FileResponse:
        """SPA fallback для history mode."""
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not Found")
        safe_root = _SPA_DIST.resolve()
        candidate = (safe_root / full_path).resolve()
        try:
            candidate.relative_to(safe_root)
        except ValueError:
            return FileResponse(_SPA_INDEX)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_SPA_INDEX)
else:
    _LOGGER.warning("Не найден frontend/dist; клиентские маршруты без dev-сервера могут отдавать 404.")
