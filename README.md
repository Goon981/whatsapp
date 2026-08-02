# SmartShop WhatsApp

Plateforme SaaS de commerce mobile pour petits commerces (restaurants, mode,
cosmétique, commerce général) présents sur WhatsApp. Chaque commerçant crée sa
boutique, reçoit des commandes, encaisse par Mobile Money et gère ses ventes
depuis un téléphone — sans compétence technique.

Ce dépôt est une implémentation **MVP** du cahier des charges *SmartShop WhatsApp*
(commerce camerounais, devise FCFA). Il couvre les trois espaces attendus :
storefront public, espace commerçant et super-administration, avec une API REST
documentée (OpenAPI).

## Stack technique

| Couche      | Choix                                   |
|-------------|-----------------------------------------|
| Backend     | **FastAPI** (Python 3.13), API REST + OpenAPI |
| Données     | **SQLAlchemy 2** + SQLite (dev) / PostgreSQL (prod) |
| Frontend    | **Jinja2** server-rendered, mobile-first, sans build |
| Sécurité    | Mots de passe **PBKDF2-SHA256**, sessions par **jetons HMAC signés** |
| Paiement    | Abstraction multi-fournisseurs + **agrégateur Mobile Money simulé** |

> Le cahier des charges recommande Flutter/PWA + FastAPI/NestJS/Laravel + PostgreSQL.
> Ce MVP prend **FastAPI + PostgreSQL-ready + PWA server-rendered** : le lien
> boutique reste accessible sans installation, objectif clé du projet.

## Démarrage rapide

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python -m app.seed            # crée la base + données de démonstration
python -m uvicorn app.main:app --reload
```

Ouvrir http://localhost:8000

### Comptes de démonstration

| Rôle          | Identifiant             | Mot de passe   | Accès        |
|---------------|-------------------------|----------------|--------------|
| Commerçant    | `amina@boutique.cm`     | `smartshop123` | `/app`       |
| Super-admin   | `admin@smartshop.cm`    | `smartshop123` | `/admin`     |
| Boutique démo | —                       | —              | `/s/chez-amina` |

## Structure

```
app/
  main.py             Point d'entrée FastAPI (API + 3 apps HTML)
  config.py           Configuration (secrets via variables d'environnement)
  database.py         Moteur & session SQLAlchemy
  models.py           Modèle de données (§10) — montants entiers FCFA
  schemas.py          Schémas Pydantic (validation serveur)
  security.py         Hachage mots de passe, jetons signés, signatures webhook
  deps.py             Auth + isolation multi-tenant (RM-05)
  templating.py       Jinja2 partagé (filtre FCFA)
  utils.py            Slugs de boutique
  services/
    pricing.py        Recalcul serveur des totaux (RM-02, RM-08)
    orders.py         Cycle de vie commande, stock (RM-04), webhook (RM-07)
    payments.py       Agrégateur Mobile Money simulé (multi-fournisseurs)
    whatsapp.py       Message structuré + lien wa.me pré-rempli (§6.6)
    stats.py          Agrégats tableau de bord & plateforme (§6.9, §7)
  routers/
    auth, shops, catalog, orders, payments, stats, admin   → API REST (§13)
    storefront, merchant, superadmin                       → apps HTML (§8)
  templates/          Storefront, merchant, admin (mobile-first)
  static/             CSS design system + JS panier
tests/                Tests d'acceptation (§15) et règles métier
```

## Documentation API

- Swagger UI : http://localhost:8000/docs
- OpenAPI JSON : http://localhost:8000/openapi.json

Principaux endpoints : authentification, boutiques, catalogue, commandes
(`/checkout`), paiements (`/webhook`), statistiques, administration.

## Paiement Mobile Money (simulation)

Le MVP fournit un **agrégateur simulé** (`services/payments.py`) qui respecte les
règles du cahier des charges :

- La confirmation d'un paiement vient **exclusivement d'un webhook signé côté
  serveur** — jamais de l'écran du client (§6.7).
- Le webhook est **idempotent** : un même `event_id` ne double jamais une
  transaction (RM-07).
- Aucun code PIN Mobile Money n'est stocké.

Simuler une confirmation de paiement :

```bash
# corps signé HMAC-SHA256 avec SMARTSHOP_PAYMENT_WEBHOOK_SECRET
curl -X POST http://localhost:8000/api/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: <hmac_sha256_du_corps>" \
  -d '{"event_id":"evt-1","payment_reference":"PAY-XXXX","status":"success"}'
```

Pour brancher un agrégateur réel compatible Cameroun, implémenter l'interface
`PaymentProvider` et l'enregistrer dans `get_provider`.

## Tests

```bash
pip install pytest httpx
python -m pytest -q
```

Les tests couvrent les critères d'acceptation (§15) et les règles métier :
recalcul serveur du total (RM-02), isolation multi-tenant (RM-05), idempotence
du webhook (RM-07), réservation de stock (RM-04), commande enregistrée une seule
fois, message WhatsApp correct, boutique suspendue inaccessible (RM-01).

## Traçabilité des règles métier

| Règle | Où |
|-------|----|
| RM-01 boutique suspendue inaccessible | `routers/orders.py`, `routers/storefront.py`, `services/stats.py` |
| RM-02 total recalculé serveur | `services/pricing.py` |
| RM-03 commande payée non supprimable | `services/orders.py::can_delete` |
| RM-04 réservation de stock configurable | `services/orders.py` |
| RM-05 isolation multi-tenant | `deps.py`, filtrage `shop_id` partout |
| RM-06 accès superadmin support | `deps.py::require_shop_access` |
| RM-07 webhook idempotent | `services/orders.py::apply_payment_event`, `models.WebhookEvent` |
| RM-08 montants entiers FCFA | `models.py` (Integer), `services/pricing.py` |
| RM-09 suppression logique | `is_archived` / `is_deleted` |
| RM-10 WhatsApp ne remplace pas l'enregistrement | commande créée avant tout envoi |

## Sécurité & production

- Définir tous les secrets via l'environnement (voir `.env.example`) —
  `SMARTSHOP_SECRET_KEY`, `SMARTSHOP_PAYMENT_WEBHOOK_SECRET`.
- Passer `SMARTSHOP_COOKIE_SECURE=true` derrière HTTPS.
- Utiliser PostgreSQL (`SMARTSHOP_DATABASE_URL`) et un vrai système de migrations
  (Alembic) en production.
- En-têtes HTTP durcis, mots de passe hachés, validation serveur systématique.

## Périmètre & suites (post-MVP)

Non inclus dans ce MVP (conformément au cahier des charges) : application native
iOS/Flutter complète, marketplace multi-vendeurs, livraison partenaire intégrée,
API WhatsApp Business (notifications automatiques), fidélité avancée, comptabilité,
multidevise. L'architecture (abstraction paiement, isolation par boutique, API
documentée) est prête pour ces extensions.
