# 📦 Guide Création du ZIP pour Hostinger

**Fichier à envoyer à Hostinger :** `smartshop-deploy.zip`

---

## Option 1 : PowerShell (Windows)

**Copier ce code :**

```powershell
# Ouvrir PowerShell (Admin) et exécuter :

$source = "C:\Users\Administrateur\OneDrive\Desktop\whatsapp"
$dest = "C:\Users\Administrateur\Desktop\smartshop-deploy.zip"

# Inclure ces fichiers/dossiers
$include = @(
    "app",
    "tests",
    "requirements.txt",
    ".env.example",
    "README.md",
    "MISE_EN_LIGNE.md",
    "GUIDE_UTILISATEUR.md",
    "DEPLOY_HOSTINGER.md"
)

# Créer ZIP
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::Open($dest, [System.IO.Compression.ZipArchiveMode]::Create)

foreach ($item in Get-ChildItem $source) {
    if ($item.Name -in $include) {
        if ($item.PSIsContainer) {
            Get-ChildItem $item.FullName -Recurse | ForEach-Object {
                $entryPath = $_.FullName.Substring($source.Length + 1)
                if (!$_.PSIsContainer) {
                    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $entryPath) | Out-Null
                }
            }
        } else {
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $item.FullName, $item.Name) | Out-Null
        }
    }
}

$zip.Dispose()
Write-Host "✅ ZIP créé : $dest"
```

---

## Option 2 : 7-Zip (UI Graphique)

**Si vous avez 7-Zip installé :**

1. Ouvrir l'Explorateur Windows
2. Naviguer vers `C:\Users\Administrateur\OneDrive\Desktop\whatsapp`
3. Sélectionner dossiers + fichiers :
   - ✅ `app/` (tout)
   - ✅ `tests/` (tests)
   - ✅ `requirements.txt`
   - ✅ `README.md`
   - ✅ `MISE_EN_LIGNE.md`
   - ✅ `GUIDE_UTILISATEUR.md`
   - ✅ `DEPLOY_HOSTINGER.md`
   - ✅ `.env.example`
   - ❌ `.venv/` (exclure)
   - ❌ `node_modules/` (exclure)
   - ❌ `.git/` (exclure)
4. Clic droit → 7-Zip → "Ajouter à l'archive..."
5. Nom : `smartshop-deploy.zip`
6. Format : ZIP
7. Cliquer "OK"

---

## Option 3 : Windows Explorer (Built-in)

**Utiliser compresse-dossiers natif :**

1. Créer dossier `smartshop-deploy` sur le Bureau
2. Y copier les dossiers + fichiers ci-dessus
3. Clic droit sur le dossier → "Compresser"
4. Renommer en `smartshop-deploy.zip`

---

## 📥 Envoyer à Hostinger

### Via FTP/SFTP (Filezilla)

```
Serveur: votre-ip-hostinger
Port: 22 (SFTP)
User: root
Mot de passe: [votre password Hostinger]

Uploader smartshop-deploy.zip vers /root/
```

### Via File Manager Hostinger

1. Ouvrir Panel Hostinger
2. File Manager
3. Naviguer vers `/root/`
4. Cliquer "Upload"
5. Sélectionner `smartshop-deploy.zip`
6. Attendre que l'upload finisse

### Via SSH Terminal

```bash
# Sur votre ordinateur, en PowerShell :
scp C:\Users\Administrateur\Desktop\smartshop-deploy.zip root@votre-ip:/root/

# Entrer mot de passe Hostinger
```

---

## 🚀 Après Upload sur Hostinger

**SSH dans votre serveur :**

```bash
ssh root@votre-ip-hostinger
cd /root
unzip smartshop-deploy.zip
cd smartshop
# Continuer avec DEPLOY_HOSTINGER.md
```

---

## ✅ Checklist ZIP

Avant d'envoyer, vérifiez que le ZIP contient :

- [ ] `app/` (backend FastAPI)
- [ ] `tests/` (21 tests)
- [ ] `requirements.txt` (dépendances Python)
- [ ] `README.md`
- [ ] `MISE_EN_LIGNE.md`
- [ ] `GUIDE_UTILISATEUR.md`
- [ ] `DEPLOY_HOSTINGER.md`
- [ ] `.env.example`

**N'inclure PAS :**
- ❌ `.venv/` (trop volumineux)
- ❌ `node_modules/` (trop volumineux)
- ❌ `.git/` (pas nécessaire)
- ❌ `smartshop-whatsapp/` (séparé)

---

## 📊 Taille Attendue

- Avec `app/` + `tests/` : ~5-10 MB
- Avec node_modules : ~500 MB (À EXCLURE)
- Avec .venv : ~200 MB (À EXCLURE)

**Total à envoyer : ~10 MB max**

