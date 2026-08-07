"""Point d'entrée FastAPI de BAOBAY.

Monte l'API REST documentée (OpenAPI — §13), les fichiers statiques et les trois
applications HTML : storefront public, espace commerçant et super-administration.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, models
from .config import settings
from .database import get_db, init_db
from .models import Shop, ShopStatus
from .routers import (
    admin,
    auth,
    billing,
    catalog,
    invitations,
    merchant,
    orders,
    payments,
    setup,
    shops,
    stats,
    storefront,
    superadmin,
    uploads,
)
from .templating import templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smartshop")

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logger.info("BAOBAY démarré (env=%s).", settings.ENV)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description=(
        "API de la plateforme de commerce mobile BAOBAY. "
        "Montants en entiers FCFA, isolation multi-tenant par boutique."
    ),
    lifespan=lifespan,
)

# --- CORS (pour frontend React) -------------------------------------------- #
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Sécurité : en-têtes HTTP durcis (NFR 11.2) ---------------------------- #
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # Les pages HTML embarquent le JavaScript de l'application : sans en-tête de
    # cache, les navigateurs appliquent un cache heuristique et continuent de
    # servir l'ancienne version après un déploiement. On les marque donc comme
    # non stockables (les fichiers de /static gardent leur cache normal).
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


# --- Fichiers statiques ---------------------------------------------------- #
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# --- API REST (OpenAPI) ---------------------------------------------------- #
app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(setup.router)
app.include_router(shops.router)
app.include_router(catalog.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(stats.router)
app.include_router(admin.router)
app.include_router(uploads.router)
app.include_router(invitations.router)

# --- Applications HTML ----------------------------------------------------- #
app.include_router(storefront.router)
app.include_router(merchant.router)
app.include_router(superadmin.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def landing(request: Request):
    db = next(get_db())
    try:
        demo = (
            db.query(Shop)
            .filter(Shop.status == ShopStatus.ACTIVE, Shop.is_deleted.is_(False))
            .order_by(Shop.created_at.asc())
            .first()
        )
        demo_slug = demo.slug if demo else None
    finally:
        db.close()
    return templates.TemplateResponse(request, "landing.html", {"demo_shop": demo_slug})


def _describe_env(name: str) -> str:
    """État d'une variable d'environnement, sans jamais en révéler la valeur."""
    import os

    raw = os.getenv(name)
    if raw is None:
        return "absente"
    if not raw.strip():
        return "définie mais vide"
    if raw.strip().startswith("${{"):
        return "référence non résolue par Railway"
    scheme = raw.split("://", 1)[0] if "://" in raw else "valeur sans schéma"
    return f"définie ({scheme})"


@app.get("/health", include_in_schema=False)
def health():
    # Le moteur seul est exposé (jamais l'URL, qui porte les identifiants) :
    # il permet de vérifier qu'une base persistante est bien branchée, "sqlite"
    # signalant un stockage effacé à chaque déploiement. Le détail des variables
    # indique laquelle manque quand la base attendue n'est pas celle utilisée.
    backend = settings.DATABASE_URL.split("://", 1)[0]
    return {
        "status": "ok",
        "version": __version__,
        "database": backend,
        "env": {
            "SMARTSHOP_DATABASE_URL": _describe_env("SMARTSHOP_DATABASE_URL"),
            "DATABASE_URL": _describe_env("DATABASE_URL"),
        },
    }


# --- Frontend React SPA (fallback) ----------------------------------------- #
@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
@app.get("/app/{path:path}", response_class=HTMLResponse, include_in_schema=False)
def serve_app(request: Request, path: str = ""):
    """Serve React SPA index.html avec env vars injectées."""
    import json
    from pathlib import Path

    dist_dir = Path(settings.STATIC_DIR) / "dist"
    index_file = dist_dir / "index.html"

    if not index_file.exists():
        # Fallback si le build React n'existe pas encore
        return "Frontend not built. Run: cd app/frontend && npm run build"

    with open(index_file, "r", encoding="utf-8") as f:
        html = f.read()

    # Corriger les chemins des assets pour qu'ils pointent vers /static/dist/assets/
    html = html.replace('src="/assets/', 'src="/static/dist/assets/')
    html = html.replace('href="/assets/', 'href="/static/dist/assets/')

    # Injecter les variables d'env pour le frontend
    env_script = f"""
    <script>
        window.__ENV__ = {json.dumps({
            'API_BASE_URL': settings.PUBLIC_BASE_URL,
            'APP_VERSION': __version__,
        })};
    </script>
    """
    html = html.replace("</head>", env_script + "</head>")
    return html


# --- Gestion d'erreurs : HTML pour les pages, JSON pour l'API -------------- #
def _wants_html(request: Request) -> bool:
    path = request.url.path
    if path.startswith(("/api", "/static", "/docs", "/openapi", "/redoc", "/health")):
        return False
    return "text/html" in request.headers.get("accept", "")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and _wants_html(request):
        return templates.TemplateResponse(
            request, "error.html", {"code": 404, "message": "Page introuvable."}, status_code=404
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse({"detail": exc.errors()}, status_code=422)
