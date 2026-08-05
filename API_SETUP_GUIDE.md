# Guide Complet - Configuration des APIs MTN MoMo et Orange Money

## 📋 Table des matières
1. [MTN MoMo API](#mtn-momo-api)
2. [Orange Money API](#orange-money-api)
3. [Intégration dans SmartShop](#intégration-dans-smartshop)
4. [Test et Déploiement](#test-et-déploiement)

---

## MTN MoMo API

### Étape 1 : Créer un compte développeur MTN

1. Accédez à : **https://momodeveloper.mtn.com**
2. Cliquez sur **"Sign Up"** (Inscription)
3. Remplissez le formulaire :
   - Email professionnel
   - Mot de passe sécurisé
   - Confirmer l'email
4. Acceptez les conditions d'utilisation
5. Vérifiez votre email (lien de confirmation)

### Étape 2 : Créer une application

1. Connectez-vous à votre dashboard
2. Allez dans **"Apps"** → **"Create App"**
3. Remplissez les informations :
   - **App Name** : "SmartShop Cameroon"
   - **App Description** : "E-commerce platform for Cameroon"
   - **Primary Industry** : "Retail/E-commerce"
   - **Use Case** : "Payment Collection"
4. Acceptez l'accord de développeur
5. Cliquez sur **"Create"**

### Étape 3 : Récupérer les credentials

Après création de l'app, vous recevrez :

```
API Key: [Voir dans Settings]
Primary Key: [Dans l'app]
Secondary Key: [Dans l'app]
Subscription Key: [pour les tests]
Base URL: https://sandbox.momodeveloper.mtn.com (TEST)
Base URL: https://api.mtn.com (PROD)
```

### Étape 4 : Configuration pour Cameroun

1. Allez dans **Products** → **Collections**
2. Sélectionnez **"Cameroon"** comme pays
3. Copiez les endpoints :
   - **Collections API** : `/collection/v1_0/...`
   - **Disbursements API** : `/disbursement/v1_0/...`
4. Prenez note du **Currency** : `XAF` (Franc CFA)

### Étape 5 : Générer UUID pour les requêtes

```bash
# Générer un UUID unique pour chaque transaction
python3 -c "import uuid; print(str(uuid.uuid4()))"
# Exemple: 12345678-1234-1234-1234-123456789012
```

---

## Orange Money API

### Étape 1 : Créer un compte Orange Developer

1. Accédez à : **https://developer.orange.com**
2. Cliquez sur **"Register"** ou **"Sign Up"**
3. Remplissez le formulaire :
   - Nom complet
   - Email professionnel
   - Téléphone (optionnel)
   - Mot de passe
4. Vérifiez votre email
5. Complétez votre profil développeur

### Étape 2 : Créer une application

1. Dans le dashboard, allez à **"My Apps"**
2. Cliquez sur **"Create a new app"**
3. Sélectionnez **"Orange Money"**
4. Remplissez :
   - **App Name** : "SmartShop"
   - **Description** : "Mobile commerce platform"
   - **Website** : "https://shopcam237.com"
   - **Redirect URI** : "https://shopcam237.com/api/payments/callback"
5. Cliquez sur **"Create"**

### Étape 3 : Récupérer les credentials

```
Client ID: [App ID]
Client Secret: [Secret Key]
Access Token URL: https://api.orange.com/oauth/v2/token
API Base URL: https://api.orange.com/orange-money-webpay/cm/v1 (PROD)
Sandbox URL: https://sandbox-api.orange.com/orange-money-webpay/cm/v1 (TEST)
```

### Étape 4 : Configuration spécifique Cameroun

1. Sélectionnez **"Cameroon"** dans les paramètres
2. Vérifiez le **Merchant ID** (fourni par Orange)
3. Prenez note du **Merchant PIN** (pour les requêtes)
4. Currency : `XAF` (Franc CFA)

### Étape 5 : Approuver l'application

- Orange doit approuver votre app (délai: 24-72h)
- Vérifiez régulièrement votre email pour les mises à jour
- Une fois approuvée, vous pouvez basculer en PROD

---

## Intégration dans SmartShop

### 1. Variables d'environnement (.env)

```bash
# MTN MoMo
MTN_API_KEY=your_mtn_api_key
MTN_PRIMARY_KEY=your_mtn_primary_key
MTN_SUBSCRIPTION_KEY=your_mtn_subscription_key
MTN_BASE_URL=https://sandbox.momodeveloper.mtn.com
MTN_MERCHANT_ID=your_mtn_merchant_id

# Orange Money
ORANGE_CLIENT_ID=your_orange_client_id
ORANGE_CLIENT_SECRET=your_orange_client_secret
ORANGE_MERCHANT_ID=your_orange_merchant_id
ORANGE_MERCHANT_PIN=your_orange_merchant_pin
ORANGE_BASE_URL=https://sandbox-api.orange.com/orange-money-webpay/cm/v1

# Mode (sandbox ou production)
PAYMENT_MODE=sandbox
```

### 2. Code d'intégration (Python/FastAPI)

```python
# app/routers/payments_integration.py

import requests
import uuid
from datetime import datetime

class MTNMoMoPayment:
    def __init__(self):
        self.api_key = os.getenv("MTN_API_KEY")
        self.subscription_key = os.getenv("MTN_SUBSCRIPTION_KEY")
        self.base_url = os.getenv("MTN_BASE_URL")
    
    def request_payment(self, phone: str, amount: int, reference: str):
        """
        Demande un paiement via MTN MoMo
        
        Args:
            phone: Numéro de téléphone (ex: 237695123456)
            amount: Montant en XAF
            reference: Référence unique
        """
        url = f"{self.base_url}/collection/v1_0/requesttopay"
        
        headers = {
            "X-Reference-Id": str(uuid.uuid4()),
            "X-Target-Environment": "sandbox",
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "externalId": reference,
            "amount": str(amount),
            "currency": "XAF",
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": phone
            },
            "payerMessage": "Paiement SmartShop",
            "payeeNote": f"Paiement pour commande {reference}"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()

class OrangeMoneyPayment:
    def __init__(self):
        self.client_id = os.getenv("ORANGE_CLIENT_ID")
        self.client_secret = os.getenv("ORANGE_CLIENT_SECRET")
        self.base_url = os.getenv("ORANGE_BASE_URL")
        self.merchant_id = os.getenv("ORANGE_MERCHANT_ID")
    
    def get_access_token(self):
        """Récupère un token d'accès"""
        url = "https://api.orange.com/oauth/v2/token"
        
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        response = requests.post(url, data=payload)
        data = response.json()
        return data.get("access_token")
    
    def request_payment(self, phone: str, amount: int, reference: str):
        """
        Demande un paiement via Orange Money
        
        Args:
            phone: Numéro de téléphone (ex: 237695123456)
            amount: Montant en XAF
            reference: Référence unique
        """
        token = self.get_access_token()
        
        url = f"{self.base_url}/transactions/pay"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": amount,
            "currency": "XAF",
            "merchant_id": self.merchant_id,
            "msisdn": phone,
            "transaction_id": reference,
            "description": f"Paiement SmartShop {reference}",
            "notif_url": "https://shopcam237.com/api/payments/callback/orange"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
```

### 3. Endpoint FastAPI pour tester

```python
@router.post("/api/payments/initiate")
async def initiate_payment(
    phone: str,
    amount: int,
    plan: str,  # "starter", "business", "premium"
    provider: str,  # "mtn" ou "orange"
    db: Session = Depends(get_db)
):
    """Initie un paiement"""
    
    # Valider le montant
    from app.routers.billing import PLAN_PRICES
    
    if plan not in PLAN_PRICES:
        raise HTTPException(400, "Plan invalide")
    
    required_amount = PLAN_PRICES[plan]
    if amount != required_amount:
        raise HTTPException(400, f"Montant incorrect. Attendu: {required_amount}")
    
    # Créer une référence unique
    reference = f"SHOP_{uuid.uuid4().hex[:12].upper()}"
    
    if provider == "mtn":
        mtn = MTNMoMoPayment()
        result = mtn.request_payment(phone, amount, reference)
    elif provider == "orange":
        orange = OrangeMoneyPayment()
        result = orange.request_payment(phone, amount, reference)
    else:
        raise HTTPException(400, "Provider invalide")
    
    # Sauvegarder dans la base de données
    payment = Payment(
        shop_id=shop_id,
        amount=amount,
        currency="XAF",
        provider=provider,
        reference=reference,
        status="pending"
    )
    db.add(payment)
    db.commit()
    
    return {"success": True, "reference": reference, "redirect_url": f"https://wa.me/237{phone[3:]}"}
```

---

## Test et Déploiement

### Phase 1 : Test en Sandbox

1. **Utiliser des numéros de test** :
   - MTN : `237688000000` (sandbox)
   - Orange : `237688000001` (sandbox)

2. **Tester les endpoints** :
```bash
curl -X POST https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay \
  -H "X-Reference-Id: 12345" \
  -H "Ocp-Apim-Subscription-Key: YOUR_KEY" \
  -d '{...}'
```

3. **Vérifier les webhooks** : Les callbacks arrivent sur `/api/payments/webhook`

### Phase 2 : Passer en Production

1. **Demander l'approbation** auprès de MTN et Orange
2. **Changer les URLs** dans `.env` :
   ```
   MTN_BASE_URL=https://api.mtn.com
   ORANGE_BASE_URL=https://api.orange.com/orange-money-webpay/cm/v1
   PAYMENT_MODE=production
   ```
3. **Utiliser les vrais numéros** de téléphone Cameroun
4. **Activer les webhooks** en production

---

## Liens utiles

| Service | Lien | Notes |
|---------|------|-------|
| **MTN Developer** | https://momodeveloper.mtn.com | API MoMo |
| **Orange Developer** | https://developer.orange.com | API Money |
| **Documentation MTN** | https://momodeveloper.mtn.com/docs | Complet |
| **Documentation Orange** | https://developer.orange.com/docs | Complet |
| **Code Pays Cameroun** | +237 | Important pour les requêtes |
| **Currency XAF** | 1 EUR ≈ 655 XAF | Taux de change |

---

## Support & Contact

- **MTN Support** : support@momodeveloper.mtn.com
- **Orange Support** : developer-support@orange.com
- **SmartShop Support** : +237 690088572

---

**Statut actuel** :
- [x] APIs configurées en Sandbox
- [ ] Webhooks testés
- [ ] Approbation production MTN
- [ ] Approbation production Orange
- [ ] Migration vers production

