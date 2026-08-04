# 📱 Guide Installation SmartShop sur Téléphone

**Public :** Commerçants et Clients  
**Plateformes :** Android + iPhone  
**Coût :** Gratuit  
**Temps :** 2 minutes par utilisateur

---

## 📲 Méthode 1 : Lien Direct (Recommandé - Easiest)

### Pour Commerçant

**Partagez ce lien WhatsApp :**
```
Bonjour,

Accédez à votre boutique SmartShop directement depuis votre téléphone :

🔗 https://smartshop.cm/app

Tapez votre email et mot de passe pour vous connecter.
```

**Étapes pour le commerçant :**
1. Ouvrir le lien → `https://smartshop.cm/app`
2. Taper email et mot de passe
3. Dashboard s'affiche
4. **Ajouter à l'écran d'accueil** (voir ci-dessous)

### Pour Client (Acheteur)

**Partagez ce lien WhatsApp :**
```
🛍️ Bienvenue dans ma boutique !

Consultez mon catalogue et achetez directement :

🔗 https://smartshop.cm/s/votre-boutique-slug

Pas besoin de créer un compte !
```

**Étapes pour le client :**
1. Ouvrir le lien → `https://smartshop.cm/s/votre-boutique`
2. Parcourir les produits
3. Ajouter au panier
4. Checkout
5. Message WhatsApp pré-rempli s'ouvre automatiquement

---

## 🏠 Ajouter à l'Écran d'Accueil (Raccourci Rapide)

### Android

**Étapes :**
1. Ouvrir navigateur (Chrome, Firefox, etc.)
2. Aller sur `https://smartshop.cm/app` (ou `/s/votre-shop`)
3. Appuyer sur **3 points** (menu) en haut à droite
4. Sélectionner **"Ajouter à l'écran d'accueil"**
5. Taper le nom (ex: "SmartShop")
6. Cliquer **"Ajouter"**

**Résultat :**
- Une icône "SmartShop" apparaît sur l'écran d'accueil
- Un clic → ouvre directement l'app dans le navigateur
- Offline? Vous pouvez toujours voir les pages en cache

### iPhone

**Étapes :**
1. Ouvrir Safari
2. Aller sur `https://smartshop.cm/app`
3. Appuyer sur **Share** (carré avec flèche) en bas
4. Scroll → sélectionner **"Add to Home Screen"**
5. Taper le nom (ex: "SmartShop")
6. Cliquer **"Add"**

**Résultat :**
- Une icône "SmartShop" sur l'écran d'accueil
- Fonctionne comme une app (mais c'est juste un raccourci Safari)

---

## 📲 Méthode 2 : Progressive Web App (PWA - Avancé)

**Qu'est-ce que c'est ?**
Une "app" installée depuis le navigateur, fonctionne hors-ligne partiellement.

### Conditions
- SmartShop doit avoir service worker + manifest.json (À ajouter - voir section "Futur")

### Comment ça marchera (Bientôt)

**Android :**
1. Ouvrir SmartShop dans Chrome
2. Popup : **"Installer l'app"**
3. Cliquer **"Installer"**
4. App s'ajoute à côté des autres apps

**iPhone :**
1. Ouvrir SmartShop dans Safari
2. Appuyer **Share** → **"Add to Home Screen"** (même qu'avant)
3. Fonctionne comme une app

---

## 💡 Résumé : Quelle Méthode Choisir ?

| Méthode | Pour Qui | Avantages | Inconvénients |
|---------|----------|-----------|---------------|
| **Lien Direct** | Commerçant + Client | Simple, rapide, aucune app à installer | Nouveau lien à chaque fois |
| **Raccourci Écran Accueil** | Commerçant (principal) | Rapide, un clic, ressemble à une app | Utilise navigateur |
| **PWA** (futur) | Commerçant + Client | Fonctionne offline, vraie app | Complexe à mettre en place |

**Recommandation MVP :** Utilisez **Lien Direct** + **Raccourci Écran Accueil** pour commerçants.

---

## 📲 Instructions Détaillées par Rôle

### 🏪 Pour un COMMERÇANT

**Donnez-lui ce guide :**

```
"Voici comment accéder à votre boutique SmartShop depuis votre téléphone :

1. Cliquez ce lien : https://smartshop.cm/app
2. Entrez votre email et mot de passe
3. Vous verrez votre dashboard

Pour accès rapide chaque jour :
- Appuyez le menu (3 points)
- Sélectionnez "Ajouter à l'écran d'accueil"
- Maintenant vous avez une icône SmartShop sur votre téléphone !

Questions ? Contactez support."
```

**Texte à envoyer sur WhatsApp :**
```
Bonjour,

Votre boutique SmartShop est prête !

Accédez-y depuis votre téléphone :
https://smartshop.cm/app

Email: [leur email]
Mot de passe: [leur mdp]

Pour un raccourci rapide:
1. Ouvrir le lien ci-dessus
2. Menu 3 points → "Ajouter à l'écran d'accueil"

Bonne vente ! 🚀
```

### 👥 Pour un CLIENT (Acheteur)

**SMS ou WhatsApp :**
```
Salut !

Découvrez mon catalogue en ligne :
https://smartshop.cm/s/demo-fashion

Pas besoin de créer un compte, c'est gratuit !
Ajoute au panier et envoie-moi la commande par WhatsApp.

Merci 🙏
```

**Facebook/Instagram Post :**
```
🛍️ Achetez mes produits en ligne !

📱 Ouvrez ce lien : https://smartshop.cm/s/demo-fashion

Catalogue complet, paiement sécurisé.
Livraison partout à Yaoundé.

#SmartShop #Commerce #OnlineStore
```

---

## 🔧 Dépannage Mobile

### "La page ne charge pas"
- Vérifier connexion WiFi/données
- Attendre quelques secondes
- Recharger (flèche en haut)
- Essayer un autre navigateur (Chrome vs Firefox)

### "Je ne peux pas commander"
- Vérifier que vous êtes sur `/s/[shop-slug]`, pas `/app`
- Désactiver VPN si vous en avez un
- Vider le cache du navigateur

### "Le message WhatsApp ne s'ouvre pas"
- Vérifier que WhatsApp est installé
- Si SMS, demander au commerçant un autre numéro
- Essayer un autre navigateur

### "Pas d'accès à la boutique (erreur 403)"
- Vous êtes peut-être bloqué (admin a suspendu la boutique)
- Contacter le support

---

## 📲 Optimisation Mobile

### Vitesse

SmartShop est optimisé pour les connexions mobiles lentes :
- ✅ Images compressées
- ✅ Pas de vidéos auto-play
- ✅ Minimal JavaScript
- ✅ Cache navigateur

**Vitesse typique :** Charge complète en 2-5 secondes

### Données

Consommation par visite :
- Première visite : ~2-3 MB (images, CSS, JS)
- Visites suivantes : ~100-200 KB (cache activé)

**Conseil :** Ouvrir sur WiFi la 1ère fois.

### Batterie

L'app n'utilise pas beaucoup de batterie :
- Pas de GPS
- Pas de notifications push
- Pas de sync en arrière-plan

**Durée :** Peut rester ouverte sans drain batterie

---

## 🌐 Compatibilité

| Navigateur | Android | iPhone |
|-----------|---------|--------|
| Chrome | ✅ Meilleur | ✅ OK (via Safari) |
| Firefox | ✅ OK | ✅ OK |
| Safari | N/A | ✅ OK |
| Edge | ✅ OK | ✅ OK |
| Samsung Internet | ✅ OK | N/A |

**Recommandation :** Chrome (Android), Safari (iPhone)

---

## 🚀 Partage Viral

### Templates à Utiliser

**WhatsApp Statut / Story :**
```
🛍️ Accédez à ma boutique en ligne !
Consultez le catalogue → https://smartshop.cm/s/demo-fashion
C'est facile et rapide ! 💨
Livraison Yaoundé 🚚
```

**Group WhatsApp :**
```
Avez-vous vu ma nouvelle boutique en ligne ?
https://smartshop.cm/s/demo-fashion

Frais de port: 2000 FCFA
Paiement à la livraison accepté
Merci de partager ! 🙏
```

**Tiktok / Reels Caption :**
```
Achetez mes produits directement sur SmartShop!
Lien en bio 👆
#Commerce #OnlineShopping #Cameroun
```

---

## 📊 Recommandations

### Pour les Commerçants

1. **Faites un raccourci** → Accès rapide chaque jour
2. **Partagez votre lien partout** :
   - WhatsApp status
   - Groupes WhatsApp
   - Facebook
   - Instagram
   - SMS (clients importants)
3. **Encouragez les clients** → "Cliquez ce lien plutôt que d'appeler"
4. **Testez sur votre téléphone** → Assurez-vous que ça marche

### Pour les Clients

1. **Bookmarkez le lien** (menu → ajouter favoris)
2. **Installez le raccourci** → Accès au lancement du téléphone
3. **Partagez la boutique** → Plus de clients = plus de choix

---

## ☎️ Support Mobile

**Si problème :**
- Essayer un autre navigateur
- Vérifier la connexion
- Contacter le commerçant/admin

**Email Support :** support@smartshop.cm  
**WhatsApp Support :** +237 6 XX XX XX XX (à configurer)

---

## 🎯 Résumé Rapide

```
Commerçant → https://smartshop.cm/app
Client → https://smartshop.cm/s/[shop-slug]

Ajouter à écran d'accueil :
Android: Menu 3 points → "Ajouter à écran d'accueil"
iPhone: Safari Share → "Ajouter à écran d'accueil"

Partager le lien partout !
```

---

**Version :** 1.0  
**Date :** 04 Août 2026  
**Platform :** iOS + Android

Pour plus d'aide, consultez `GUIDE_UTILISATEUR.md`
