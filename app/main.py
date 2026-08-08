"""Point d'entrée FastAPI de BAOBAY.

Monte l'API REST documentée (OpenAPI — §13), les fichiers statiques et les trois
applications HTML : storefront public, espace commerçant et super-administration.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
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
from .startup import enforce_subscriptions_loop, load_signing_key
from .templating import templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smartshop")

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    load_signing_key()
    # Suspension des abonnements échus. Portée par l'application faute de
    # planificateur côté hébergeur : sans elle, la route dédiée n'était appelée
    # par personne et aucun essai expiré n'était jamais fermé.
    watcher = asyncio.create_task(enforce_subscriptions_loop())
    logger.info("BAOBAY démarré (env=%s, base=%s).", settings.ENV, settings.DATABASE_URL.split("://", 1)[0])
    try:
        yield
    finally:
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher


# La documentation interactive détaille les 46 routes, leurs paramètres et
# leurs schémas : utile en développement, inutile à un visiteur de la vitrine et
# précieuse pour qui cherche une prise. Elle reste accessible en production à
# qui définit SMARTSHOP_EXPOSE_DOCS.
_docs_open = not settings.IS_PRODUCTION or settings.EXPOSE_DOCS

app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description=(
        "API de la plateforme de commerce mobile BAOBAY. "
        "Montants en entiers FCFA, isolation multi-tenant par boutique."
    ),
    lifespan=lifespan,
    docs_url="/docs" if _docs_open else None,
    redoc_url="/redoc" if _docs_open else None,
    openapi_url="/openapi.json" if _docs_open else None,
)

# Compression : aujourd'hui assurée par le routeur de l'hébergeur, mais celui-ci
# peut changer ou disparaître selon l'endroit où l'application est déployée.
# Starlette ne compresse pas deux fois — l'en-tête posé en amont est respecté.
app.add_middleware(GZipMiddleware, minimum_size=800)

# --- CORS (pour frontend React) -------------------------------------------- #
# Liste explicite d'origines : « * » combiné à ``allow_credentials`` conduit
# Starlette à renvoyer l'origine de l'appelant dès qu'un cookie accompagne la
# requête, si bien que n'importe quel site pouvait interroger l'API au nom d'un
# commerçant connecté et lire ses commandes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    max_age=600,
)

# Le HTML de l'application embarque ses scripts et ses styles (dont la palette
# de thème) : 'unsafe-inline' reste nécessaire, mais restreindre les sources à
# 'self' empêche l'injection d'un script hébergé ailleurs.
CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "object-src 'none'"
)


# --- Sécurité : en-têtes HTTP durcis (NFR 11.2) ---------------------------- #
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()"
    )
    if settings.IS_PRODUCTION:
        # Le site n'est servi qu'en HTTPS : interdire les retours en clair.
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    # Les pages HTML embarquent le JavaScript de l'application : sans en-tête de
    # cache, les navigateurs appliquent un cache heuristique et continuent de
    # servir l'ancienne version après un déploiement. On les marque donc comme
    # non stockables.
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    elif request.url.path.startswith("/static/") and request.query_params.get("v"):
        # Les gabarits demandent /static/…?v=<empreinte du contenu> : l'URL
        # change dès que le fichier change, le cache peut donc être gardé un an
        # sans revalidation. Sans le paramètre, on reste prudent.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
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


@app.get("/media/{file_id}", include_in_schema=False)
def serve_media(file_id: str, db: Session = Depends(get_db)):
    """Sert une image stockée en base.

    Le nom du fichier est un identifiant aléatoire attribué une fois pour
    toutes et son contenu ne change jamais : la réponse peut donc être mise en
    cache indéfiniment, ce qui évite de relire la base à chaque affichage du
    catalogue.
    """
    media = db.get(models.MediaFile, file_id)
    if media is None:
        raise StarletteHTTPException(status_code=404, detail="Image introuvable")
    return Response(
        content=media.data,
        media_type=media.content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Length": str(media.size or len(media.data)),
        },
    )


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


_CAMPAY_ENDPOINTS = {
    "sandbox": "https://demo.campay.net/api",
    "production": "https://www.campay.net/api",
}


def _describe_campay() -> dict:
    """État de la configuration Campay, sans jamais restituer une valeur.

    ``CAMPAY_MODE`` n'attend que « sandbox » ou « production ». Restituer la
    valeur telle quelle a publié un secret sur cette page, qui est ouverte à
    tous, le jour où une clé y avait été collée par erreur : on ne renvoie donc
    que des valeurs connues d'avance.
    """
    mode = (settings.CAMPAY_MODE or "").strip()
    known = mode in _CAMPAY_ENDPOINTS
    return {
        "mode": mode if known else "VALEUR INATTENDUE (attendu : sandbox ou production)",
        "authentification": (
            "jeton permanent" if settings.CAMPAY_PERMANENT_TOKEN
            else "identifiants" if (settings.CAMPAY_API_USER and settings.CAMPAY_API_PASSWORD)
            else "AUCUNE (paiements simules)"
        ),
        "permanent_token": "defini" if settings.CAMPAY_PERMANENT_TOKEN else "absent",
        "api_user": "definie" if settings.CAMPAY_API_USER else "ABSENTE",
        "api_password": "definie" if settings.CAMPAY_API_PASSWORD else "ABSENTE",
        "webhook_key": "definie" if settings.CAMPAY_WEBHOOK_KEY else "ABSENTE",
        "endpoint": _CAMPAY_ENDPOINTS.get(mode, "indetermine"),
    }


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
        # État de la configuration Campay, sans aucune valeur : « authentification
        # refusée » ne disait pas si un identifiant manquait ou si les
        # identifiants d'un environnement étaient présentés à l'autre.
        "campay": _describe_campay(),
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
    # ``exc.headers`` porte notamment le ``Retry-After`` des réponses 429 : le
    # laisser tomber privait les clients de l'information la plus utile.
    return JSONResponse(
        {"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None)
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse({"detail": exc.errors()}, status_code=422)
