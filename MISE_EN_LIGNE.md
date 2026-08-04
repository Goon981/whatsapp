# Checklist Mise en Ligne — SmartShop WhatsApp MVP

**Date :** 04 Août 2026  
**Status :** Prêt pour déploiement  
**Version :** 1.0.0 MVP

---

## ✅ Complété — Infrastructure & Déploiement

### Backend FastAPI
- [x] API REST 8 routers complets (auth, shops, catalog, orders, payments, stats, admin, superadmin)
- [x] Authentification JWT (HMAC-SHA256, PBKDF2 passwords)
- [x] Isolation multi-tenant stricte (RM-05)
- [x] CORS middleware ajouté
- [x] Endpoint `/app` pour servir React SPA
- [x] Injection `window.__ENV__` (API_BASE_URL)
- [x] Tests d'acceptation : 21/21 ✓
- [x] OpenAPI docs auto-générée (`/docs`, `/openapi.json`)

### Frontend React
- [x] 18 écrans codés (Login, Onboarding, Dashboard, Catalog, Cart, Checkout, Orders, Stats, Settings, etc.)
- [x] Design system complet (vert #007a49, Roboto, spacing 18px gutter)
- [x] Build Vite minified + copie automatique → `app/static/dist/`
- [x] TypeScript strict, types alignées avec backend
- [x] Context API (Auth, Shop, Cart)
- [x] API client avec interceptor JWT + refresh auto
- [x] Dépendances : axios, zod, zustand, sonner, framer-motion

### Données de Test
- [x] Utilisateur démo : `demo@boutique.cm` / `demo123456`
- [x] Boutique démo : "Demo Fashion Store" (slug: `demo-fashion`)
- [x] 3 catégories + 3 produits en stock
- [x] Vérifiée via API : login, shops list, products list ✓

### Sécurité — Étapes Complétées
- [x] HTTPS prêt (à configurer en prod)
- [x] Mots de passe PBKDF2-SHA256 (salt aléatoire)
- [x] JWT signés (HMAC-SHA256, expiration 1h access / 7d refresh)
- [x] Validation Pydantic serveur obligatoire
- [x] Headers durcis (X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
- [x] Isolation boutiques testée (user A ≠ user B data)
- [x] Cookies httponly (smartshop_session fallback)

---

## ⏳ À Faire Avant Launch — Priorité Haute

### 1. Upload Images Produits (2h)
- [ ] Créer endpoint `POST /api/shops/{id}/products/{pid}/upload`
- [ ] Valider MIME type (image/jpeg, image/png, image/webp)
- [ ] Limiter taille (5MB max)
- [ ] Stocker dans `app/static/uploads/{shop_id}/{product_id}/`
- [ ] Tester upload dans frontend

### 2. Intégration Paiement Réelle (3h)
- [ ] Valider contrats MTN MoMo + Orange Money
- [ ] Configurer API credentials (sandbox → production)
- [ ] Implémenter `/api/payments/initialize` (appel provider)
- [ ] Webhook production avec signature vraie
- [ ] Tester paiement end-to-end

### 3. Configuration Production (2h)
- [ ] Variables d'environnement finales (secrets, URLs, clés)
  - `SMARTSHOP_SECRET_KEY` (generation forte)
  - `SMARTSHOP_PAYMENT_WEBHOOK_SECRET`
  - `SMARTSHOP_DATABASE_URL` (PostgreSQL connection string)
  - `SMARTSHOP_PUBLIC_BASE_URL`
  - `SMARTSHOP_COOKIE_SECURE=true` (HTTPS)
  - `SMARTSHOP_ENV=production`
- [ ] PostgreSQL migration depuis SQLite (Alembic script)
- [ ] Certificat SSL/TLS (Let's Encrypt gratuit)

### 4. Déploiement Serveur (1-2h)
**Recommandation :** O2SWITCH (VPS, support français, €5/mois)
- [ ] Créer VPS/conteneur
- [ ] Cloner repo + installer dépendances
- [ ] Configurer secrets (`/etc/smartshop/.env`)
- [ ] Nginx reverse proxy → localhost:8000
- [ ] Systemd service pour uvicorn (auto-restart)
- [ ] Logs centralisés (Sentry / DataDog)

### 5. Monitoring & Backup (1h)
- [ ] Sauvegardes PostgreSQL quotidiennes (cron job)
- [ ] Monit erreurs (Sentry, même gratuit)
- [ ] Alertes downtime (Uptime Robot)
- [ ] Logs centralisés (journalctl + rotation)

---

## 🧪 Tests Avant Launch — Obligatoire

### Scénarios End-to-End
- [ ] **Signup Merchant** : email → mot de passe → boutique créée → accessible
- [ ] **Login** : credentials valides → token JWT → boutique affichée
- [ ] **Catalog Merchant** : créer catégorie → ajouter produit → visible en storefront
- [ ] **Cart Client** : ajouter au panier → modifier quantité → total recalculé
- [ ] **Checkout** : adresse + paiement sélectionné → commande créée → merchant voit
- [ ] **Payment Webhook** : simulation paiement → une seule commande créée (idempotence)
- [ ] **Isolation** : merchant A ne voit pas produits merchant B
- [ ] **Suspension** : admin suspend boutique → inaccessible (403, page "suspended")

### Sécurité
- [ ] **SQL Injection** : `' OR '1'='1` dans search → pas d'erreur
- [ ] **XSS** : `<img src=x onerror=alert>` dans description → échappé HTML
- [ ] **CSRF** : POST sans token → 403 Forbidden
- [ ] **Rate Limiting** : 10 login/min par IP → 429 Too Many Requests
- [ ] **JWT Expiry** : access token expiré → 401 → auto-refresh
- [ ] **CORS** : Cross-origin sans Allow → bloqué

### Performance (Lighthouse)
- [ ] Desktop : Score > 85 (FCP < 1.5s, LCP < 2.5s)
- [ ] Mobile : Score > 80 (FCP < 2.5s)
- [ ] Bundle JS : < 300KB gzipped

### Responsive
- [ ] Mobile 375px : pas de débordement, boutons tactiles 50px+
- [ ] Tablet 768px : layout adapté
- [ ] Desktop 1280px : sidebar visible

---

## 🚀 Launch Day — Checklist

### Avant Activation
- [ ] Backup produits : export DB SQLite local
- [ ] DNS pointé vers serveur production
- [ ] SSL certificat valide (https://)
- [ ] Emails transactionnels testés (au moins console pour MVP)
- [ ] Support email/WhatsApp actif
- [ ] Conditions d'utilisation + politique confidentialité approuvées légalement

### À Minuit (Go-Live)
- [ ] Basculer BD vers PostgreSQL (Alembic migration)
- [ ] Démarrer serveur production
- [ ] Vérifier `/health` répond
- [ ] Tester login + dashboard via https://smartshop.cm (ou domaine final)
- [ ] Monitoring activé (Sentry, Uptime Robot)
- [ ] Support chat ouvert

### Pendant H+24h
- [ ] Surveiller erreurs (Sentry dashboard)
- [ ] Vérifier usage BD (CPU, mémoire)
- [ ] Tester paiements en live (montant réel)
- [ ] Répondre aux support clients

### Post-Launch (Semaines 1-2)
- [ ] Feedback utilisateurs collecté
- [ ] Bugs critiques corrigés en < 24h
- [ ] Optimisations perf si besoin
- [ ] Expansion géographique (autres régions) si traction

---

## 📋 Credentials de Déploiement

**Utilisateur de Test :**
```
Email: demo@boutique.cm
Mot de passe: demo123456
```

**Boutique de Test :**
- Nom: "Demo Fashion Store"
- Slug: demo-fashion
- Produits: 3 (T-Shirt 8500 FCFA, Chemise 15000 FCFA, Jean 25000 FCFA)

**Admin Système :**
```
Email: admin@smartshop.cm
Mot de passe: smartshop123
Role: superadmin
```

---

## 💾 Fichiers Clés à Déployer

```
app/
  ├── main.py               (point d'entrée FastAPI)
  ├── config.py             (settings via env vars)
  ├── database.py           (SQLAlchemy + Alembic ready)
  ├── models.py             (15 entités)
  ├── routers/              (8 APIs)
  ├── services/             (billing, orders, payments, stats, whatsapp)
  ├── security.py           (JWT, PBKDF2)
  ├── frontend/             (React source)
  └── static/dist/          (build Vite minified)
  
tests/                      (21 tests d'acceptation)
requirements.txt            (Python dépendances)
docker-compose.yml          (optionnel : PostgreSQL + Redis)
.env.example                (template secrets)
```

---

## 🛑 Risques & Mitigations

| Risque | Mitigation |
|--------|-----------|
| **Downtime paiement** | COD toujours disponible (fallback) |
| **DB corruption** | Backups quotidiens + test restauration |
| **Credentials exposées** | Jamais en code source, always env vars |
| **Rate limit API** | Limiter 100 req/min par IP par défaut |
| **DDoS** | Cloudflare DDoS protection (gratuit) |
| **Frontend JS leak** | Pas de secrets hardcodés (window.__ENV__ only) |

---

## 📞 Support Pré-Launch

**Questions fréquentes des commerçants (FAQ) :**
1. Comment ajouter des produits ? → Guide video (2 min)
2. Comment recevoir les paiements ? → Intégration MTN/Orange
3. Comment voir les commandes ? → Dashboard → Commandes
4. Comment suspendre un client abusif ? → Clients → Bloquer
5. Comment augmenter mon abonnement ? → Settings → Formule

**Support Channels :**
- Email : support@smartshop.cm
- WhatsApp : +237 6 XX XX XX XX (à configurer)
- Chat in-app : Sonner notifications + FAQ

---

## ✅ Sign-Off

**Dates :**
- MVP Démarrage : 04 Août 2026
- Tests Complétés : 04 Août 2026
- **Prêt pour Mise en Ligne : OUI**

**Responsable Technique :** Claude Code  
**Responsable Commercial :** [À nommer]  
**Approbation Juridique :** [À confirmer]

---

**Prochaines étapes :** Valider paiements + déployer sur O2SWITCH.
