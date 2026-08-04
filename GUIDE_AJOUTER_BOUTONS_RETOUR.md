# 🔙 Guide Ajouter les Boutons Retour au Frontend

**Problème remarqué :** Certaines pages n'ont pas de bouton "Retour" ou "← Précédent"  
**Solution :** Ajouter des boutons retour sur chaque écran

---

## 🎯 Stratégie

Chaque écran du Prototype doit avoir :
1. **Titre** de la page
2. **Bouton "← Retour"** (en haut à gauche OU en bas)
3. **Contenu** principal
4. **Boutons actions** (si applicable)

```
┌──────────────────────────────┐
│ ← Retour    Titre Page       │  ← Header avec retour
├──────────────────────────────┤
│                              │
│      Contenu principal       │
│                              │
├──────────────────────────────┤
│    [Action] [Action]         │  ← Boutons actions
└──────────────────────────────┘
```

---

## 📝 Exemple de Code à Ajouter

### HTML/JSX Pattern

**Chaque écran devrait avoir :**

```jsx
<div className="screen">
  {/* Header avec Retour */}
  <header className="screen-header">
    <button 
      className="btn-back"
      onClick={() => navigation.goBack()}
    >
      ← Retour
    </button>
    <h1>Titre de la Page</h1>
  </header>

  {/* Contenu */}
  <main className="screen-content">
    {/* ... votre contenu ... */}
  </main>

  {/* Actions */}
  <footer className="screen-footer">
    <button className="btn-primary">Action</button>
  </footer>
</div>
```

### CSS à Ajouter

```css
.screen-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
}

.btn-back {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #007a49;
  padding: 8px;
}

.btn-back:hover {
  opacity: 0.7;
}

.screen-header h1 {
  flex: 1;
  margin: 0;
  font-size: 20px;
}
```

---

## 📱 Écrans à Modifier

### Liste des Écrans (du Prototype.tsx)

| # | Écran | Retour vers | Status |
|----|-------|-------------|--------|
| 1 | Login | Accueil | ✅ Pas besoin |
| 2 | Register | Login | ➕ À ajouter |
| 3 | Onboarding | Dashboard | ➕ À ajouter |
| 4 | Dashboard | N/A | ✅ Accueil |
| 5 | Products List | Dashboard | ➕ À ajouter |
| 6 | Product Form | Products List | ➕ À ajouter |
| 7 | Orders List | Dashboard | ➕ À ajouter |
| 8 | Order Detail | Orders List | ➕ À ajouter |
| 9 | Customers | Dashboard | ➕ À ajouter |
| 10 | Stats | Dashboard | ➕ À ajouter |
| 11 | Settings | Dashboard | ➕ À ajouter |
| 12 | Storefront | N/A | ✅ Accueil |
| 13 | Product Detail | Catalog | ➕ À ajouter |
| 14 | Cart | Catalog | ➕ À ajouter |
| 15 | Checkout | Cart | ➕ À ajouter |
| 16 | Order Confirm | N/A | ✅ Accueil |
| 17 | Order Tracking | N/A | ✅ Accueil |
| 18 | Admin Dashboard | N/A | ✅ Admin |

**À faire :** Ajouter boutons retour sur ~12 écrans

---

## 🔧 Comment Faire (Étape par Étape)

### Étape 1 : Identifier la Navigation

Dans `src/Prototype.tsx`, trouvez où la navigation se fait :

```jsx
// Actuellement (navigation par état)
const [currentScreen, setCurrentScreen] = useState('login');

// À améliorer : ajouter un historique
const [screenHistory, setScreenHistory] = useState(['login']);
const [currentScreen, setCurrentScreen] = useState('login');

const navigateTo = (screen) => {
  setScreenHistory([...screenHistory, screen]);
  setCurrentScreen(screen);
};

const goBack = () => {
  if (screenHistory.length > 1) {
    const newHistory = screenHistory.slice(0, -1);
    setScreenHistory(newHistory);
    setCurrentScreen(newHistory[newHistory.length - 1]);
  }
};
```

### Étape 2 : Ajouter le Bouton à Chaque Écran

**Exemple pour l'écran "Register" :**

```jsx
{currentScreen === 'register' && (
  <div className="screen">
    <header className="screen-header">
      <button className="btn-back" onClick={goBack}>
        ← Retour
      </button>
      <h1>Créer un Compte</h1>
    </header>
    
    <main className="screen-content">
      {/* Formulaire d'inscription */}
      <form>
        <input type="text" placeholder="Nom complet" />
        <input type="email" placeholder="Email" />
        <input type="password" placeholder="Mot de passe" />
        <button type="submit">S'inscrire</button>
      </form>
    </main>
  </div>
)}
```

### Étape 3 : Ajouter CSS pour Styling

Ajoutez au fichier CSS :

```css
/* Bouton Retour */
.btn-back {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  color: #007a49;
  padding: 10px;
  font-weight: bold;
}

.btn-back:hover {
  background: #f0f0f0;
  border-radius: 4px;
}

.screen-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #f9f9f9;
  border-bottom: 1px solid #e0e0e0;
  position: sticky;
  top: 0;
  z-index: 10;
}

.screen-header h1 {
  margin: 0;
  font-size: 18px;
  flex: 1;
}
```

---

## ✅ Checklist Implémentation

**Pour chaque écran à modifier :**

- [ ] Ajouter bouton `← Retour` en haut
- [ ] Connecter bouton à fonction `goBack()`
- [ ] Tester navigation avant/arrière
- [ ] Vérifier style (responsive mobile)
- [ ] Vérifier qu'on ne peut pas revenir avant l'écran d'accueil

---

## 🎨 Design Guidelines

### Placement

**Option 1 (Recommandée) :** Haut gauche
```
[← Retour]  Titre                  [Menu]
```

**Option 2 :** Bas (pour petits écrans)
```
┌─────────────────────┐
│  Contenu            │
├─────────────────────┤
│ [← Retour] [Action] │
└─────────────────────┘
```

### Styling

**Bouton Retour Style :**
- Couleur : Vert #007a49 (brand color)
- Taille texte : 16px
- Padding : 10px
- Pas de bordure
- Hover : léger fond gris

### Exceptions

**Écrans sans retour :**
- Login (1ère page)
- Accueil dashboard
- Confirmation/Success (montrer lien accueil à la place)

---

## 🔄 Gestion Historique Complète

```jsx
// Navigation globale avec historique
const [navigationStack, setNavigationStack] = useState(['dashboard']);

const goTo = (screen) => {
  setNavigationStack([...navigationStack, screen]);
};

const goBack = () => {
  if (navigationStack.length > 1) {
    setNavigationStack(navigationStack.slice(0, -1));
  }
};

const canGoBack = () => navigationStack.length > 1;

const currentScreen = navigationStack[navigationStack.length - 1];
```

---

## 📋 Priorités

### Haute (Ajouter d'abord)
```
1. Register → Login
2. Onboarding → Dashboard
3. Product Form → Products List
4. Order Detail → Orders List
5. Product Detail (Storefront) → Catalog
6. Checkout → Cart
```

### Moyenne
```
7. Settings → Dashboard
8. Customers → Dashboard
9. Stats → Dashboard
```

### Basse (Optionnel)
```
10. Autres écrans de détail
```

---

## 🚀 Déployer les Changements

**Après modification :**

```bash
cd app/frontend
npm run build  # Rebuild
cd ../..
systemctl restart smartshop  # Redémarrer le service
```

---

## 🧪 Tester la Navigation

**Checklist de test :**
- [ ] Chaque écran a un bouton "Retour"
- [ ] Cliquer retour revient à l'écran précédent
- [ ] Impossible de revenir avant l'accueil
- [ ] Bouton responsive sur mobile
- [ ] Pas de bug d'historique (ex: boucles infinies)

---

## 📞 Support

**Si vous avez besoin d'aide pour ajouter les boutons :**
- Email : support@smartshop.cm
- WhatsApp : +237 6 XX XX XX XX

**Fichier à modifier :**
- `app/frontend/src/Prototype.tsx` - Ajouter les boutons retour

---

**Version :** 1.0  
**Date :** 04 Août 2026  
**Priorité :** Moyenne (Avant launch)
