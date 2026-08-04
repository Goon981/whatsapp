#!/bin/bash
# Script pour créer un ZIP prêt pour Hostinger

echo "🔧 Création du ZIP de déploiement..."

# Créer dossier temporaire
mkdir -p /tmp/smartshop-deploy
cd /tmp/smartshop-deploy

# Copier le repo (exclure dossiers volumineux)
rsync -av --exclude='.venv' --exclude='node_modules' --exclude='.git' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='.pytest_cache' --exclude='app/frontend/dist' \
  --exclude='*.db' --exclude='.DS_Store' \
  /opt/smartshop/ ./smartshop/

echo "📦 Création du ZIP..."
zip -r smartshop-deploy.zip smartshop/ -q

# Afficher taille
SIZE=$(du -h smartshop-deploy.zip | cut -f1)
echo "✅ ZIP créé : smartshop-deploy.zip ($SIZE)"

# Copier sur le bureau
cp smartshop-deploy.zip ~/Desktop/
echo "📁 Fichier copié : ~/Desktop/smartshop-deploy.zip"

# Nettoyage
rm -rf /tmp/smartshop-deploy

echo "🎉 Prêt pour Hostinger !"
