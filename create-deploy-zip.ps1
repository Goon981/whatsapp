# Script PowerShell pour créer le ZIP de déploiement (Windows)

Write-Host "🔧 Création du ZIP de déploiement..." -ForegroundColor Green

$sourceDir = "C:\Users\Administrateur\OneDrive\Desktop\whatsapp"
$tempDir = "$env:TEMP\smartshop-deploy"
$zipPath = "$env:USERPROFILE\Desktop\smartshop-deploy.zip"

# Créer dossier temporaire
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# Copier les fichiers (exclure les gros dossiers)
$exclude = @(
    '.venv',
    'node_modules',
    '.git',
    '__pycache__',
    '.pytest_cache',
    'app/frontend/dist',
    'smartshop-whatsapp',
    '*.db',
    '.DS_Store'
)

Write-Host "📋 Copie des fichiers..." -ForegroundColor Cyan
Copy-Item -Path "$sourceDir\*" -Destination "$tempDir\smartshop\" -Recurse -Force -Exclude $exclude

# Créer le ZIP
Write-Host "📦 Compression en ZIP..." -ForegroundColor Cyan
Add-Type -AssemblyName "System.IO.Compression.FileSystem"
[System.IO.Compression.ZipFile]::CreateFromDirectory("$tempDir\smartshop", $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

# Afficher la taille
$size = (Get-Item $zipPath).Length / 1MB
Write-Host "✅ ZIP créé : $zipPath ($([math]::Round($size, 2)) MB)" -ForegroundColor Green

# Nettoyage
Remove-Item $tempDir -Recurse -Force

Write-Host "🎉 Prêt pour Hostinger !" -ForegroundColor Green
Write-Host ""
Write-Host "📥 Instructions Hostinger:" -ForegroundColor Yellow
Write-Host "1. Ouvrir File Manager dans votre panel Hostinger"
Write-Host "2. Créer dossier /opt/smartshop"
Write-Host "3. Uploader $zipPath"
Write-Host "4. Dézipper : unzip smartshop-deploy.zip"
Write-Host "5. Suivre DEPLOY_HOSTINGER.md"
