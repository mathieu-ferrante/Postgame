# Lance le service Postgame (API sur le port 8765 + surveillance des dossiers de démos).
# Usage :  powershell -ExecutionPolicy Bypass -File scripts\lancer.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
.\.venv\Scripts\python -m postgame serve
