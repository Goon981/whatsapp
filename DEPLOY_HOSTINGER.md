# 🚀 Guide Déploiement SmartShop sur Hostinger

**Plateforme :** Hostinger VPS/Hébergement Partagé  
**OS :** Ubuntu 22.04 LTS  
**Estimated Time :** 1-2 heures  
**Coût :** ~€3-8/mois (plan Hostinger VPS basic)

---

## 📋 Checklist Avant de Commencer

- [ ] Compte Hostinger créé et VPS provisionné
- [ ] Domaine réservé (ex: smartshop.cm) et pointant vers Hostinger
- [ ] SSH accès à votre serveur
- [ ] Code du projet prêt à pusher

---

## PARTIE 1 : Configuration Initiale du Serveur

### 1. Connecter à Hostinger en SSH

**Dans votre terminal local :**
```bash
ssh root@votre_ip_hostinger
# Entrez le mot de passe Hostinger (fourni dans panel)
```

**Exemple :**
```bash
ssh root@195.154.12.34
root@195.154.12.34's password: ****
Welcome to Ubuntu 22.04.1 LTS...
```

### 2. Mettre à jour le système

```bash
apt update && apt upgrade -y
apt install -y curl wget git build-essential
```

### 3. Installer Node.js (pour frontend build)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
apt install -y nodejs npm
node --version  # Vérifie (devrait être v20.x)
npm --version
```

### 4. Installer Python 3.13

```bash
apt install -y python3.13 python3.13-venv python3-pip
python3.13 --version
```

### 5. Installer PostgreSQL

```bash
apt install -y postgresql postgresql-contrib
sudo service postgresql start
sudo -u postgres createuser smartshop -P  # Vous demande mot de passe
# Entrez un mot de passe fort (ex: "ChangeMe12345!")

sudo -u postgres createdb smartshop -O smartshop
```

### 6. Installer Nginx (reverse proxy)

```bash
apt install -y nginx
systemctl start nginx
systemctl enable nginx  # Auto-start après reboot

# Arrêtez le default site
rm /etc/nginx/sites-enabled/default
```

### 7. Installer Supervisor (pour gérer uvicorn)

```bash
apt install -y supervisor
```

---

## PARTIE 2 : Déployer le Code

### 1. Cloner le repo

```bash
cd /opt
git clone https://github.com/VOTRE_USERNAME/smartshop-whatsapp.git smartshop
cd smartshop
```

**Note :** Si dépôt privé, générez une SSH key :
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# Copier la clé publique dans GitHub → Settings → Deploy Keys
```

### 2. Setup Python venv

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Setup Frontend build

```bash
cd app/frontend
npm install
npm run build  # Génère dist/client/ → copie vers ../static/dist/
cd ../..
```

### 4. Configurer secrets (.env)

```bash
nano .env
```

**Contenu :**
```bash
# === SMARTSHOP CONFIG ===
SMARTSHOP_ENV=production
SMARTSHOP_SECRET_KEY=your-super-secret-key-min-32-chars-ChangeMe1234567890
SMARTSHOP_DATABASE_URL=postgresql://smartshop:ChangeMe12345!@localhost:5432/smartshop
SMARTSHOP_PAYMENT_WEBHOOK_SECRET=your-webhook-secret-ChangeMe1234567890
SMARTSHOP_PUBLIC_BASE_URL=https://smartshop.cm
SMARTSHOP_CRON_SECRET=your-cron-secret-ChangeMe123456
SMARTSHOP_SUPPORT_WHATSAPP=237670000000
SMARTSHOP_COOKIE_SECURE=true
```

**Générer clés fortes :**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Remplacez "your-super-secret-key-..." par le résultat
```

### 5. Migrer la base de données

```bash
source .venv/bin/activate
python -m alembic upgrade head  # Si vous avez Alembic
# OU simplement laisser la DB se créer au premier démarrage
```

---

## PARTIE 3 : Configurer le Service Systemd (Auto-run)

### Créer fichier service Systemd

```bash
nano /etc/systemd/system/smartshop.service
```

**Contenu :**
```ini
[Unit]
Description=SmartShop WhatsApp FastAPI
After=network.target postgresql.service

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/smartshop
Environment="PATH=/opt/smartshop/.venv/bin"
ExecStart=/opt/smartshop/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Activer le service :**
```bash
systemctl daemon-reload
systemctl enable smartshop
systemctl start smartshop
systemctl status smartshop  # Vérifie (devrait être "active (running)")
```

---

## PARTIE 4 : Configurer Nginx (Reverse Proxy + SSL)

### Créer config Nginx

```bash
nano /etc/nginx/sites-available/smartshop.cm
```

**Contenu :**
```nginx
server {
    listen 80;
    listen [::]:80;
    server_name smartshop.cm www.smartshop.cm;

    # Rediriger HTTP → HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name smartshop.cm www.smartshop.cm;

    # SSL (à installer ci-dessous)
    ssl_certificate /etc/letsencrypt/live/smartshop.cm/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/smartshop.cm/privkey.pem;

    # Optimisation SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Logs
    access_log /var/log/nginx/smartshop-access.log;
    error_log /var/log/nginx/smartshop-error.log;

    # Max upload 10MB
    client_max_body_size 10M;

    # Proxy vers FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Cache static files (images, CSS, JS)
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|woff|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

**Activer le site :**
```bash
ln -s /etc/nginx/sites-available/smartshop.cm /etc/nginx/sites-enabled/
nginx -t  # Test config
systemctl reload nginx
```

### Installer SSL (Let's Encrypt)

```bash
apt install -y certbot python3-certbot-nginx
certbot certonly --nginx -d smartshop.cm -d www.smartshop.cm
# Entrez votre email, acceptez les termes
```

**Vérifier :**
```bash
curl https://smartshop.cm
# Devrait afficher le HTML du frontend React
```

---

## PARTIE 5 : Configuration PostgreSQL

### Créer utilisateur et base de données

```bash
sudo -u postgres psql
```

**Dans la console postgres :**
```sql
CREATE USER smartshop WITH PASSWORD 'ChangeMe12345!';
CREATE DATABASE smartshop OWNER smartshop;
GRANT ALL PRIVILEGES ON DATABASE smartshop TO smartshop;
\q
```

### Tester la connexion

```bash
PGPASSWORD=ChangeMe12345! psql -h localhost -U smartshop -d smartshop -c "\dt"
# Devrait afficher les tables (d'abord vide)
```

---

## PARTIE 6 : Tester le Déploiement

### Test 1 : Service FastAPI

```bash
systemctl status smartshop
# Devrait être "active (running)"

curl http://127.0.0.1:8000/health
# {"status":"ok","version":"1.0.0"}
```

### Test 2 : Nginx + SSL

```bash
curl -I https://smartshop.cm
# Devrait afficher 200 OK
```

### Test 3 : Frontend React

Ouvrez navigateur :
```
https://smartshop.cm/app
```

Devrait afficher le formulaire de login.

### Test 4 : API REST

```bash
curl -X POST https://smartshop.cm/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"demo@boutique.cm","password":"demo123456"}'
# Retourne token JWT
```

---

## PARTIE 7 : Monitoring & Backups

### 1. Monitoring Logs

**Logs FastAPI :**
```bash
journalctl -u smartshop -f  # Suivi temps réel
```

**Logs Nginx :**
```bash
tail -f /var/log/nginx/smartshop-error.log
```

### 2. Backup Automatique PostgreSQL (Quotidien)

**Créer script :**
```bash
nano /opt/smartshop/backup-db.sh
```

**Contenu :**
```bash
#!/bin/bash
BACKUP_DIR="/opt/smartshop/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

PGPASSWORD=ChangeMe12345! pg_dump -h localhost -U smartshop smartshop | gzip > $BACKUP_DIR/smartshop_$DATE.sql.gz

# Garder que les 7 derniers jours
find $BACKUP_DIR -name "smartshop_*.sql.gz" -mtime +7 -delete

echo "Backup créé: $BACKUP_DIR/smartshop_$DATE.sql.gz"
```

**Rendre exécutable :**
```bash
chmod +x /opt/smartshop/backup-db.sh
```

**Ajouter à crontab (quotidien 2h du matin) :**
```bash
crontab -e
# Ajouter:
0 2 * * * /opt/smartshop/backup-db.sh >> /var/log/smartshop-backup.log 2>&1
```

### 3. Monitoring CPU/RAM

**Vérifier usage :**
```bash
free -h  # Mémoire
df -h    # Disque
top      # Processus actifs
```

---

## PARTIE 8 : Mise à Jour du Code

**Quand vous poussez une nouvelle version :**

```bash
cd /opt/smartshop
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt  # Si dépendances changent
cd app/frontend
npm install  # Si dépendances front changent
npm run build
cd ../..

# Redémarrer le service
systemctl restart smartshop

# Vérifier
systemctl status smartshop
```

---

## ✅ CHECKLIST POST-DEPLOYMENT

- [ ] Site accessible sur https://smartshop.cm
- [ ] Login fonctionne (demo@boutique.cm / demo123456)
- [ ] Dashboard affiche boutique démo
- [ ] Produits visibles sur /s/demo-fashion
- [ ] Logs vérifient (journalctl -u smartshop)
- [ ] SSL valide (curl https://smartshop.cm)
- [ ] Backups tournent (check cron)
- [ ] Monitoring actif (logs, CPU)

---

## 🆘 Dépannage Hostinger

### "Connection refused" à PostgreSQL

```bash
# Vérifier service
sudo service postgresql status

# Redémarrer
sudo service postgresql restart

# Vérifier credentials dans .env
PGPASSWORD=ChangeMe12345! psql -h localhost -U smartshop -d smartshop -c "SELECT 1"
```

### "502 Bad Gateway" Nginx

```bash
# Vérifier FastAPI
systemctl status smartshop

# Logs
journalctl -u smartshop -n 20

# Redémarrer
systemctl restart smartshop
```

### "SSL certificate not found"

```bash
# Renouveler
certbot renew

# Ou créer nouveau
certbot certonly --nginx -d smartshop.cm
```

### "Disk full"

```bash
df -h  # Voir usage
# Supprimer anciens backups
rm /opt/smartshop/backups/smartshop_*.sql.gz
```

---

## 💡 Conseils Production

1. **Changer les passwords par défaut** ✅
2. **Mettre SMARTSHOP_COOKIE_SECURE=true** ✅
3. **Configurer rate limiting** (futur update)
4. **Backups quotidiens** ✅
5. **Monitoring logs** ✅
6. **Certificat SSL auto-renew** : `certbot renew --dry-run` (test)
7. **Firewall** : Ouvrir juste 80 (HTTP) et 443 (HTTPS)

---

## 📞 Support Hostinger

Si problème Hostinger :
- **Chat support** : Dans le panel Hostinger
- **Email** : support@hostinger.com
- **Docs** : https://support.hostinger.com

---

**🎉 Votre SmartShop est en ligne !**

Visitez `https://smartshop.cm` et commencez à vendre. 🚀

Pour des mises à jour du code, faites juste `git pull && npm run build && systemctl restart smartshop`.
