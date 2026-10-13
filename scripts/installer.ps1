# Installe Postgame sur le PC de jeu (Windows, Python 3.13 requis).
# Usage, depuis la racine du dépôt :  powershell -ExecutionPolicy Bypass -File scripts\installer.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) {
    Write-Host "Création de l'environnement Python (.venv)…"
    py -3.13 -m venv .venv
}
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[dev]"

# Interface web : construite avec Node.js (https://nodejs.org, version LTS).
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location web
    npm ci
    npm run build
    Pop-Location
} else {
    Write-Host "Node.js absent : l'API fonctionne, mais l'interface web ne sera pas construite."
}

if (-not (Test-Path postgame.toml)) {
    Copy-Item postgame.exemple.toml postgame.toml
    Write-Host "postgame.toml créé : y renseigner le SteamID64 et vérifier les dossiers CS2."
}
Write-Host "Installation terminée. Lancer le service : scripts\lancer.ps1"
