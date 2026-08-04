# 📘 Guide Utilisateur Complet — SmartShop WhatsApp

**Version :** 1.0.0 MVP  
**Date :** 04 Août 2026  
**Langue :** Français  
**Public :** Administrateur, Commerçants, Clients

---

## 📑 Table des Matières

1. [À Propos de SmartShop](#à-propos)
2. [Guide Admin (Super-Administrateur)](#guide-admin)
3. [Guide Commerçant (Merchant)](#guide-commerçant)
4. [Guide Client (Storefront)](#guide-client)
5. [FAQ & Dépannage](#faq)
6. [Support](#support)

---

<a id="à-propos"></a>

## 🎯 À Propos de SmartShop

### Qu'est-ce que SmartShop ?

SmartShop WhatsApp est une **plateforme de commerce mobile** conçue pour les petits commerçants, restaurants, boutiques de mode et vendeurs du Cameroun.

**Objectifs :**
- ✅ Créer une boutique en ligne en **moins de 30 minutes**
- ✅ Recevoir les commandes **directement sur WhatsApp**
- ✅ Gérer les produits, stocks et commandes **depuis un téléphone**
- ✅ Accepter les paiements **MTN MoMo** et **Orange Money**
- ✅ Voir vos ventes et statistiques en **temps réel**

### Qui utilise SmartShop ?

| Rôle | Utilisation |
|------|-----------|
| **Admin** | Gère tous les commerçants, abonnements, suspensions, statistiques globales |
| **Commerçant** | Crée une boutique, ajoute produits, reçoit commandes, gère clients |
| **Client** | Voit la boutique, ajoute au panier, passe commande, paie |

### Comment ça marche ?

```
1. Commerçant crée boutique sur SmartShop
   ↓
2. Commerçant ajoute ses produits (nom, prix, photo, stock)
   ↓
3. Commerçant partage lien de sa boutique sur WhatsApp/Facebook
   ↓
4. Client ouvre le lien → voit les produits → ajoute au panier
   ↓
5. Client checkout → envoie commande par WhatsApp au commerçant
   ↓
6. Commerçant reçoit commande dans son dashboard
   ↓
7. Commerçant confirme → prépare → livre
   ↓
8. Client reçoit → paie (MTN/Orange) → commande livrée
```

---

<a id="guide-admin"></a>

## 👨‍💼 Guide Admin (Super-Administrateur)

### Accès Admin

**URL :** `http://localhost:8000/admin` (remplacez localhost par votre domaine en production)

**Identifiants de connexion :**
```
Email : admin@smartshop.cm
Mot de passe : smartshop123
```

**Note :** Changez le mot de passe immédiatement en production !

### Écran d'Accueil (Vue Globale)

Quand vous vous connectez, vous voyez un **tableau de bord** avec :

#### 📊 Cartes KPI (Haut de page)
- **Chiffre d'affaires total** : Somme de tous les paiements reçus (FCFA)
- **Nombre de boutiques** : Total de commerçants inscrits
- **Commandes en attente** : Commandes non encore confirmées
- **Paiements en retard** : Abonnements impayés

#### 📈 Graphiques
- **Revenue courbe** : Revenus par jour/semaine/mois
- **Top boutiques** : Les commerçants avec le plus de ventes
- **Statut commandes** : Répartition (new, confirmed, delivered, cancelled)

### Menu Admin (Onglets)

#### 1️⃣ **Vue globale** (`/admin`)
**Qu'est-ce que c'est ?**
- Tableau de bord principal de la plateforme
- Résumé de tous les commerçants et ventes

**Fonctionnalités :**
- Voir KPIs (revenue, shops, orders, payments)
- Voir graphique revenue
- Voir incidents (paiements échoués, webhooks)

**Actions :** Aucune ici, juste consultation

---

#### 2️⃣ **Abonnements** (`/admin/billing`)
**Qu'est-ce que c'est ?**
- Gestion des abonnements SaaS (paiements mensuels des commerçants)
- Voir qui a payé, qui est impayé, suspendre boutiques

**Tableau :**
Pour chaque boutique vous voyez :
- **Boutique** : Nom du commerçant
- **Plan** : Essai / Starter / Business / Premium
- **Montant/mois** : Prix de l'abonnement (FCFA)
- **État** : 
  - 🟢 À jour (abonnement payé)
  - 🟡 Expire bientôt (< 3 jours avant fin)
  - 🔴 En retard (date dépassée)
  - ⚫ Suspendu (impayé, boutique désactivée)

**Actions :**
- **Mark as Paid** : Enregistrer un paiement reçu (prolonge d'1 mois)
- **Change Plan** : Passer de Starter à Business, etc.

**Exemple :**
```
Boutique: "Demo Fashion Store"
Plan: Starter (5000 FCFA/mois)
État: À jour (expire 15 Août 2026)
Actions: [Mark Paid] [Change Plan] 

→ Si vous cliquez "Mark Paid":
  • Abonnement prolongé jusqu'au 15 Septembre
  • Boutique reste visible aux clients
  • Commerçant peut continuer à vendre
```

---

#### 3️⃣ **Boutiques** (`/admin/shops`)
**Qu'est-ce que c'est ?**
- Liste de TOUTES les boutiques créées
- Voir statut (active, suspended, pending)

**Tableau :**
Pour chaque boutique :
- **Nom** : "Demo Fashion Store"
- **Propriétaire** : Email du commerçant
- **Statut** : 
  - 🟢 Active (visible aux clients)
  - 🔴 Suspended (inaccessible)
  - 🟡 Pending (en attente de vérification)
- **Abonnement** : Plan actuel
- **Créée le** : Date de création

**Actions :**
- **Voir détails** : Informations boutique complètes
- **Suspendre** : Rendre inaccessible (si impayée, spam, etc.)
- **Réactiver** : Remettre active après suspension
- **Supprimer** : Suppression logique (données conservées)

**Exemple :**
```
Boutique: "Fashion Store Yaoundé"
Statut: Suspended (impayée depuis 10 jours)
Actions: 
  → Cliquer "Réactiver" si paiement reçu
  → OU laisser suspendue si toujours impayée
```

---

#### 4️⃣ **Incidents** (`/admin/incidents`)
**Qu'est-ce que c'est ?**
- Erreurs système, paiements échoués, webhooks non confirmés

**Exemples d'incidents :**
- "Paiement MTN échoué pour commande #2550 (timeout)"
- "Webhook signature invalide de Orange Money"
- "Erreur base de données lors de création produit"

**Actions :**
- Voir détails de l'erreur
- Marquer comme "résolu"
- Rejouer le webhook (si paiement échoué)

---

#### 5️⃣ **Journal d'Audit** (`/admin/audit`)
**Qu'est-ce que c'est ?**
- Historique de TOUTES les actions faites par les admins
- Traçabilité totale

**Colonne :**
- **Admin** : Qui a fait l'action
- **Action** : Qu'est-ce qui a été fait (suspend, mark_paid, etc.)
- **Cible** : Boutique / Commerçant affecté
- **Date/Heure** : Quand
- **Détails** : Données techniques

**Exemple :**
```
Admin: Claude Code
Action: shop.suspend
Cible: "Fashion Douala" (shop_id: 12)
Date: 04 Aug 2026 14:30:00
Détails: {"reason": "subscription_overdue", "days_late": 5}
```

---

### Tâches Courantes Admin

#### ❓ "Un commerçant dit que sa boutique n'apparaît plus"

**Diagnostic :**
1. Allez à **Boutiques** (`/admin/shops`)
2. Cherchez la boutique par nom
3. Vérifiez le **Statut** :
   - Si **Suspended** → C'est une suspension (impayé?)
   - Si **Active** → Problème technique

**Solution si Suspended :**
- Cliquez **Réactiver** si paiement reçu
- Message au commerçant : "Paiement confirmé, boutique réactivée"

#### ❓ "Un commerçant n'a pas payé son abonnement"

**Diagnostic :**
1. Allez à **Abonnements** (`/admin/billing`)
2. Trouvez la boutique
3. Vérifiez l'**État** :
   - 🔴 En retard → Suspension automatique dans 3 jours
   - ⚫ Suspendu → Déjà suspendue

**Action :**
- Contactez le commerçant (email/WhatsApp)
- Si paiement reçu → Cliquez **Mark as Paid**
- Si refus → Laissez suspendue

#### ❓ "Erreur technique : paiement échoué mais commande créée"

**Diagnostic :**
1. Allez à **Incidents**
2. Trouvez l'erreur (webhook ou paiement)
3. Lire détails techniques

**Action :**
- Contactez fournisseur paiement (MTN/Orange)
- Cliquez **Rejouer webhook** si applicable
- Compensez commerçant si erreur de notre côté

---

<a id="guide-commerçant"></a>

## 🏪 Guide Commerçant (Merchant)

### Accès Commerçant

**URL :** `http://localhost:8000/app`

**Identifiants de test :**
```
Email : demo@boutique.cm
Mot de passe : demo123456
```

### 1. Page de Connexion

**Écran :**
- Champ "E-mail ou téléphone"
- Champ "Mot de passe"
- Bouton "Se connecter"
- Lien "Créer une boutique" (si pas encore inscrit)

**Actions :**
1. Entrez votre email/téléphone
2. Entrez votre mot de passe
3. Cliquez "Se connecter"

**Problème ?**
- "Identifiants invalides" → Vérifiez email et mot de passe
- "Compte désactivé" → Contactez support

---

### 2. Dashboard Principal

**Qu'est-ce que c'est ?**
Vue d'ensemble de votre boutique et ventes

**Éléments affichés :**

#### 📊 Cartes KPI (Haut)
- **Chiffre d'affaires (aujourd'hui)** : Total ventes du jour
- **Commandes en attente** : Nombre de commandes "nouvelles" non confirmées
- **Produits en stock** : Nombre total de produits disponibles
- **Clients uniques** : Nombre de clients différents (historique)

#### 📈 Graphique
- **Courbe revenue** : Vos ventes par jour (derniers 7 jours)

#### 📋 Tableau Commandes Récentes
- **Référence** : #2550, #2551, etc.
- **Client** : Nom du client
- **Montant** : Total FCFA
- **Statut** : new, confirmed, ready, delivered, etc.
- **Action** : Cliquez pour voir détails

#### 🔗 Lien de Partage
**Votre URL publique :**
```
https://smartshop.cm/s/demo-fashion
← Partagez ce lien sur WhatsApp/Facebook/Instagram
```

**Actions :**
- **Copier lien** : Pour partager
- **QR Code** : Pour afficher en physique (magasin)

---

### 3. Gestion des Produits

**Menu :** Cliquez "Produits" dans le menu de gauche

#### 3.1 Voir tous les produits

**Tableau :**
Pour chaque produit :
- **Image** : Photo du produit
- **Nom** : "T-Shirt Noir Premium"
- **Prix** : "8 500 FCFA"
- **Stock** : "15 disponibles"
- **Statut** : 
  - 🟢 Disponible
  - 🔴 Rupture
  - 🟡 Pré-commande
  - ⚫ Masqué (clients ne voient pas)

**Actions :**
- **Éditer** : Modifier nom, prix, stock, etc.
- **Dupliquer** : Copier le produit (utile pour variantes)
- **Archiver** : Masquer aux clients (garder données)
- **Supprimer** : Suppression définitive

---

#### 3.2 Créer un nouveau produit

**Formulaire :**

| Champ | Explication | Exemple |
|-------|-----------|---------|
| **Nom** | Nom du produit | "T-Shirt Bleu Ocean" |
| **Description** | Détails, matière, entretien | "Coton 100%, confortable, machine 30°C" |
| **Catégorie** | Groupe du produit | Vêtements, Accessoires, Chaussures |
| **Prix** | Montant en FCFA | 8500 |
| **Prix promo** | Prix réduit (optionnel) | 6000 (25% de réduction) |
| **Photo** | Image du produit | [Uploader image] |
| **SKU** | Code interne (optionnel) | TSHIRT-001 |
| **Stock** | Nombre disponibles | 20 |
| **Seuil alerte** | Vous alerter si stock < ce nombre | 5 (alerte si < 5) |
| **Statut** | Disponible/Rupture/Masqué | Disponible |

**Étapes :**
1. Cliquez "+ Ajouter un produit"
2. Remplissez les champs
3. Cliquez "Sauvegarder"

**Astuce :** Les clients voient vos produits sur la page `https://smartshop.cm/s/demo-fashion`

---

#### 3.3 Variantes (Tailles, Couleurs)

**Exemple :**
```
Produit: "T-Shirt"
Variantes:
  - Taille S : 8500 FCFA (stock 10)
  - Taille M : 8500 FCFA (stock 15)
  - Taille L : 9000 FCFA (stock 8)
  - Taille XL: 9500 FCFA (stock 5)
```

**Comment ajouter :**
1. Créez le produit "T-Shirt"
2. En bas du formulaire : "+ Ajouter une variante"
3. Entrez Taille/Couleur/Format
4. Entrez prix spécifique et stock

**Clients voient :**
```
T-Shirt (dropdown Taille: S / M / L / XL)
Prix selon taille sélectionnée
```

---

### 4. Gestion des Commandes

**Menu :** Cliquez "Commandes"

#### 4.1 Liste des commandes

**Tableau :**
Pour chaque commande :
- **Référence** : #2550
- **Client** : Nom + téléphone
- **Montant** : 25 000 FCFA
- **Statut** : 
  - 🔵 New (nouvelle, à confirmer)
  - 🟢 Confirmed (confirmée)
  - 🟡 Preparing (en préparation)
  - 🟠 Ready (prête à livrer)
  - ✅ Delivered (livrée)
  - ❌ Cancelled (annulée)
- **Date** : Quand créée

**Filtres :**
- Par statut (Show all / New / Confirmed / etc.)
- Par date (Dernière semaine / Mois / etc.)

---

#### 4.2 Détails d'une commande

Cliquez sur une commande pour voir :

**👤 Infos Client :**
- Nom : "Amina Kamga"
- Téléphone : "+237 670 000 001"
- Email : (optionnel)

**📦 Articles :**
```
1x T-Shirt Noir (Taille M) → 8 500 FCFA
1x Jean Classique → 25 000 FCFA
───────────────────────────────
Sous-total : 33 500 FCFA
Frais livraison : 2 000 FCFA
Remise : 0 FCFA
TOTAL : 35 500 FCFA
```

**📍 Livraison :**
- Adresse : "Yaoundé, Carrefour Mvan, près épicerie Mbok"
- Zone : "Yaoundé Centre"
- Frais : 2000 FCFA

**💳 Paiement :**
- Méthode : "MTN MoMo" / "Orange Money" / "Paiement à la livraison"
- Statut : "En attente" / "Payé" / "Échoué"
- Référence : "PAY-2550-MTN-001" (si payé)

**⏱️ Historique Statuts :**
```
04 Aug 14:30 - New (créée)
04 Aug 14:45 - Confirmed (vous avez confirmé)
04 Aug 15:00 - Preparing (en préparation)
04 Aug 16:30 - Ready (prête à livrer)
```

---

#### 4.3 Changer le statut d'une commande

**Flux de statuts :**
```
New (créée par client)
  ↓ (Vous confirmez)
Confirmed
  ↓ (Vous préparez)
Preparing
  ↓ (Prêt à livrer)
Ready
  ↓ (Livrer aux clients)
Delivered
```

**Actions :** Boutons pour passer au statut suivant

**Exemple :**
```
1. Vous voyez: "Commande #2550 - Status: New"
2. Vous préparez les articles
3. Vous cliquez "Confirmer" → Statut devient "Confirmed"
4. Vous emballez
5. Vous cliquez "Marquer prête" → Status: "Ready"
6. Client vient chercher/vous livrez
7. Vous cliquez "Marquer livrée" → Status: "Delivered"
```

**Quand le statut change :**
- Client reçoit notification WhatsApp (optionnel)
- Client voit le statut dans sa page de suivi
- Vous pouvez ajouter un message (ex: "Prête à chercher demain matin")

---

#### 4.4 Message WhatsApp intégré

**Qu'est-ce que c'est ?**
Bouton pour contacter le client directement

**Actions :**
- Cliquez "💬 Contacter client"
- WhatsApp s'ouvre avec un message pré-rempli
- Exemple : "Bonjour Amina, votre commande #2550 est prête ! Vous pouvez la chercher demain matin ?"

---

### 5. Gestion des Clients

**Menu :** Cliquez "Clients"

#### 5.1 Liste des clients

**Tableau :**
Pour chaque client :
- **Nom** : "Amina Kamga"
- **Téléphone** : "+237 670 000 001"
- **Commandes** : "5 commandes"
- **Dépenses** : "125 500 FCFA" (total historique)
- **Statut** : 
  - 🟢 Actif
  - 🔴 Bloqué (abusif)

---

#### 5.2 Détails client

Cliquez sur un client pour voir :
- Historique de toutes ses commandes
- Montant total dépensé
- Dernière commande
- Notes internes (pour vous)

**Actions :**
- **Ajouter note** : "Client picky, rappeler les délais"
- **Bloquer** : Si client abusif/spam (ne pourra plus passer commande)
- **Débloquer** : Si erreur ou réconciliation

---

### 6. Statistiques & Rapports

**Menu :** Cliquez "Statistiques"

#### Que voyez-vous ?

**📊 Cartes KPI :**
- **Revenue Mois** : Total ventes ce mois
- **Commandes Mois** : Nombre de commandes
- **Clients Mois** : Clients uniques ce mois
- **Panier moyen** : Revenue / Commandes

**📈 Graphiques :**
- **Revenue courbe** : Ventes par jour/semaine
- **Top produits** : Vos produits les plus vendus
- **Statut commandes** : Répartition (new, delivered, cancelled)

**📋 Tableau :**
- **Produits en rupture** : "Jean 0 stock"
- **Produits bientôt rupture** : "Chemise 2 stock < seuil 5"
- **Nouveaux clients** : Clients de cette semaine

---

### 7. Configuration Boutique

**Menu :** Cliquez "Paramètres"

#### Infos Boutique

| Champ | Explication | Exemple |
|-------|-----------|---------|
| **Nom boutique** | Votre nom | "Fashion Store Yaoundé" |
| **Description** | Qui êtes-vous | "Vêtements modernes pour tous, 5 ans d'expérience" |
| **Logo** | Image de la boutique | [Uploader] |
| **Couleur thème** | Couleur principale | 🟢 Vert (par défaut) |
| **Téléphone** | Votre numéro | "+237 670 000 001" |
| **Email** | Votre email | "shop@exemple.cm" |
| **Adresse** | Localisation physique | "Yaoundé, Carrefour Mvan" |
| **Ville** | Ville | "Yaoundé" |
| **Horaires** | Heures d'ouverture | "Lun-Sam 9h-18h, Dimanche fermé" |
| **Ouvert/Fermé** | État | 🟢 Ouvert |

#### Zones de Livraison

**Qu'est-ce que c'est ?**
Vous définissez où vous livrez et combien ça coûte

**Exemple :**
```
Zone 1: "Yaoundé Centre"
  Frais: 2000 FCFA
  
Zone 2: "Yaoundé Banlieue"
  Frais: 3000 FCFA

Zone 3: "Douala"
  Frais: 5000 FCFA
```

**Clients choisiront leur zone au checkout**

#### Moyens de Paiement

Cochez ce que vous acceptez :
- ✅ Paiement à la livraison (COD)
- ✅ MTN MoMo
- ✅ Orange Money

#### Abonnement

- **Plan actuel** : "Starter"
- **Montant/mois** : "5 000 FCFA"
- **Date expiration** : "15 Septembre 2026"
- **Produits max** : "50"
- **Commandes/mois max** : "150"

---

### 8. Tableau de Bord (Accueil)

C'est la page que vous voyez quand vous vous loggez.

**Résumé rapide de votre business :**
- Combien vous avez gagné aujourd'hui
- Combien de commandes en attente
- Combien de produits en stock
- Lien de partage de votre boutique

**Actions rapides :**
- "+ Ajouter un produit"
- "Voir mes commandes"
- "Copier lien boutique"

---

<a id="guide-client"></a>

## 👥 Guide Client (Storefront)

### Accès Client

**URL :** `http://localhost:8000/s/demo-fashion`

**Note :** Pas besoin de compte client ! Achat en visiteur.

---

### 1. Accueil de la Boutique

**Vous voyez :**
- **Logo & nom** : "Demo Fashion Store"
- **Description** : "Vêtements modernes..."
- **Horaires** : "Ouvert aujourd'hui, 9h-18h"
- **Bouton appel** : Appeler commerçant
- **Bouton WhatsApp** : Contacter directement

---

### 2. Parcourir les Produits

#### Catégories
Au-dessus, des **tags** pour filtrer :
- "Tous"
- "Vêtements"
- "Accessoires"
- "Chaussures"

Cliquez pour filtrer par catégorie.

#### Grille de Produits
Pour chaque produit :
- **Image** : Photo du produit
- **Nom** : "T-Shirt Noir Premium"
- **Prix** : "8 500 FCFA"
- **Stock** : "15 disponibles" OU "Rupture" (grisé)
- **Bouton "Ajouter au panier"**

---

### 3. Voir un Produit

Cliquez sur un produit pour voir détails :

**Infos :**
- **Photo grande** : Zoomable
- **Nom** : "T-Shirt Noir Premium"
- **Description** : "Confortable et durable, coton 100%"
- **Prix** : "8 500 FCFA"
- **Note** : "4.6/5 (134 avis)" (futur)

**Si variantes (tailles, couleurs) :**
```
Taille: [S] [M] [L] [XL]
Couleur: [Noir] [Bleu] [Rouge]
```

**Sélecteurs :**
- Quantité : [−] 1 [+]
- Taille : Dropdown
- Couleur : Dropdown

**Bouton :** "Ajouter au panier" (vert)

---

### 4. Panier

**Accès :** Icône panier 🛒 (coin haut droit)

**Affichage :**
```
Panier (3 articles)

1x T-Shirt Noir (Taille M)
    Prix: 8 500 FCFA
    Quantité: [−] 1 [+]
    Sous-total: 8 500 FCFA
    [Supprimer]

1x Jean Classique
    Prix: 25 000 FCFA
    Quantité: [−] 1 [+]
    Sous-total: 25 000 FCFA
    [Supprimer]

─────────────────────────
Sous-total : 33 500 FCFA
───────────────────────────

[Continuer les achats] [Passer la commande]
```

**Actions :**
- Modifier quantité (−/+)
- Supprimer un article
- Continuer shopping (retour au catalogue)
- **Passer la commande** (→ Checkout)

---

### 5. Checkout (Commander)

**Étape 1 : Vos infos**
```
Nom : ________________________
Téléphone : +237 ____________
Email (optionnel) : __________
```

**Étape 2 : Adresse de livraison**
```
Adresse : ____________________________
  (Ex: "Yaoundé, Carrefour Mvan, près épicerie Mbok")
Ville : [Dropdown: Yaoundé / Douala / Kribi / ...]
Quartier : ____________________________
```

**Étape 3 : Livraison**
Vous choisissez une zone :
```
Zone 1: "Yaoundé Centre" → Frais: 2000 FCFA
Zone 2: "Yaoundé Banlieue" → Frais: 3000 FCFA
Zone 3: "Douala" → Frais: 5000 FCFA
```

**Étape 4 : Paiement**
Vous choisissez comment payer :
```
○ Paiement à la livraison (sans frais)
○ MTN MoMo (immédiat)
○ Orange Money (immédiat)
```

**Étape 5 : Résumé**
```
Articles :
  1x T-Shirt 8 500 FCFA
  1x Jean 25 000 FCFA
  Sous-total : 33 500 FCFA

Livraison (Zone Yaoundé Centre) : 2 000 FCFA

TOTAL : 35 500 FCFA

Moyen de paiement : Paiement à la livraison
```

**Bouton : "Valider la commande"**

---

### 6. Confirmation WhatsApp

**Quand vous validez :**

1. **Confirmation affichée :**
   ```
   ✅ Commande confirmée !
   
   Référence : #2550
   Total : 35 500 FCFA
   
   Votre message WhatsApp est prêt à envoyer !
   ```

2. **Message WhatsApp s'ouvre :**
   ```
   À : +237 670 000 001 (commerçant)
   
   "Bonjour, je viens de passer commande #2550
   
   Articles :
   - 1x T-Shirt Noir (Taille M) = 8 500 FCFA
   - 1x Jean Classique = 25 000 FCFA
   
   Livraison : Yaoundé Centre
   Total : 35 500 FCFA
   
   Mode paiement : Paiement à la livraison
   
   Merci ! 👋"
   ```

3. **Vous cliquez "Envoyer"** sur WhatsApp
4. Commerçant reçoit le message
5. Commerçant confirme la commande dans son dashboard
6. Commerçant vous contacte pour confirmer livraison

---

### 7. Suivre ma Commande

**URL :** `http://localhost:8000/s/demo-fashion/order/2550` (lien envoyé avec confirmation)

**Vous voyez :**
- Statut actuel : 🟡 "Preparing"
- Historique :
  ```
  04 Aug 14:30 - New (créée)
  04 Aug 14:45 - Confirmed (commerçant a confirmé)
  04 Aug 15:00 - Preparing (en préparation)
  04 Aug 16:30 - Ready (prête à chercher !)
  ```
- Message du commerçant : "Prête à chercher demain 9h !"
- Bouton "Contacter commerçant" (WhatsApp)

---

<a id="faq"></a>

## ❓ FAQ & Dépannage

### Admin

**Q: Comment suspendre une boutique qui spam ?**
A: Allez à `/admin/shops`, trouvez la boutique, cliquez "Suspendre" et choisissez raison "Spam/Contenu inapproprié".

**Q: Un commerçant dit avoir payé mais la boutique est suspendue**
A: Allez à `/admin/billing`, trouvez la boutique, cliquez "Mark as Paid", puis allez à `/admin/shops` et cliquez "Réactiver".

**Q: Quel est le délai avant suspension auto pour impayé ?**
A: 3 jours de retard (configurable). Exemple : abonnement expire 15 Août → suspension le 18 Août.

**Q: Peut-on voir qui a téléchargé les données clients ?**
A: Oui, allez à `/admin/audit` et filtrez par "export".

---

### Commerçant

**Q: Où est mon lien de boutique ?**
A: Dans le Dashboard, en bas : "Votre lien de partage : https://smartshop.cm/s/demo-fashion"

**Q: Comment ajouter une remise sur un produit ?**
A: Allez à Produits → Éditer le produit → Remplissez "Prix promo" (optionnel).

**Q: Quand un client ajoute au panier, je reçois une notification ?**
A: Non. Vous ne recevez une notification que quand il passe la commande et envoie le message WhatsApp.

**Q: Puis-je changer le thème/couleur de ma boutique ?**
A: Oui, Paramètres → Couleur thème. Les options disponibles sont : Vert, Bleu, Rose, Orange.

**Q: Qu'est-ce qui se passe si un produit est en rupture ?**
A: Mettez le statut à "Rupture" ou remettez le stock à 0. Le produit s'affichera grisé et le bouton "Ajouter au panier" sera désactivé.

**Q: Puis-je modifier un prix après que des clients aient vu ?**
A: Oui, modifiez quand vous voudrez. Les nouveaux clients voient le nouveau prix. Les commandes en cours gardent l'ancien prix.

**Q: Comment exporter la liste de mes clients ?**
A: Allez à Clients → Cliquez "📥 Exporter". Vous téléchargez un fichier CSV.

**Q: Quand mon abonnement expire, mes produits disparaissent ?**
A: Non. Votre boutique devient juste inaccessible (les clients reçoivent une erreur 403). Vos données sont conservées. Payez et la boutique réapparaît.

---

### Client

**Q: Comment modifier ma commande après l'avoir passée ?**
A: Contactez le commerçant directement via WhatsApp (dans l'historique de commande).

**Q: Et si j'oublie de payer avec MTN/Orange ?**
A: Si vous aviez choisi "MTN MoMo", le statut restera "En attente de paiement". Le commerçant peut vous contacter pour relancer.

**Q: Puis-je retourner un produit ?**
A: Cela dépend du commerçant. Contactez-le directement via WhatsApp.

**Q: Ma commande est marquée "Livrée" mais je n'ai pas reçu**
A: Contactez le commerçant immédiatement. Possiblement erreur ou livraison non passée.

---

<a id="support"></a>

## 📞 Support & Contact

### Pour les Admins
**Email :** support@smartshop.cm  
**WhatsApp :** +237 6 XX XX XX XX  
**Horaires :** Lun-Ven 9h-17h (heure Cameroun)

### Pour les Commerçants
**Centre d'aide :** `http://localhost:8000/help` (FAQ + vidéos tutoriels)  
**Email support :** support@smartshop.cm  
**Chat live :** Disponible dans le dashboard (Lun-Ven 9h-17h)

### Pour les Clients
**Chat boutique :** Cliquez "Contacter boutique" sur la page de la boutique  
**Support général :** support@smartshop.cm

---

## 📚 Ressources Supplémentaires

- **Vidéos tutoriels** : [À venir]
- **Blog** : Articles sur "Démarrer votre e-commerce", "Optimiser vos ventes"
- **Webinaires** : Jeudi 18h (gratuit, inscription requise)
- **Communauté** : Groupe Facebook SmartShop Cameroun (conseils entre commerçants)

---

## 🚀 Conseils Pratiques

### Pour les Commerçants

1. **Utilisez des photos de bonne qualité** : Les clients achètent avec les yeux
2. **Mettez des descriptions détaillées** : Matière, taille, mode d'entretien
3. **Mettez à jour le stock régulièrement** : Évitez "rupture" après vente
4. **Répondez vite sur WhatsApp** : Les clients s'impatient
5. **Publiez régulièrement** : Ajoutez des nouveaux produits chaque semaine

### Pour les Clients

1. **Vérifiez l'adresse avant de valider** : Pas d'édition après
2. **Copiez le lien de suivi** : Vous pourrez vérifier le statut plus tard
3. **Contactez le commerçant avant de faire un retour** : Chaque boutique a sa politique
4. **Donnez un avis** : Cela aide les autres clients (futur)

---

## 📋 Checklist Démarrage Commerçant

- [ ] Créer compte SmartShop
- [ ] Compléter informations boutique (nom, logo, horaires)
- [ ] Ajouter au moins 5 produits
- [ ] Configurer zones de livraison
- [ ] Copier lien boutique
- [ ] Partager sur WhatsApp/Facebook/Instagram
- [ ] Attendre première commande
- [ ] Confirmer et livrer
- [ ] Demander avis client

---

**Dernier mise à jour :** 04 Août 2026  
**Version :** 1.0.0  
**Langue :** Français

Pour des mises à jour et corrections, contactez support@smartshop.cm
