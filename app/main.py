"""Point d'entrée FastAPI de SmartShop WhatsApp.

Monte l'API REST documentée (OpenAPI — §13), les fichiers statiques et les trois
applications HTML : storefront public, espace commerçant et super-administration.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
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
    logger.info("SmartShop démarré (env=%s).", settings.ENV)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description=(
        "API de la plateforme de commerce mobile SmartShop WhatsApp. "
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
    return response


# --- Fichiers statiques ---------------------------------------------------- #
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# --- API REST (OpenAPI) ---------------------------------------------------- #
app.include_router(auth.router)
app.include_router(billing.router)
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


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "version": __version__}


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
