"""Registre des modules de jeu."""

from __future__ import annotations

from pathlib import Path

from postgame.games.base import ModuleJeu
from postgame.games.cs2 import ModuleCS2
from postgame.games.gd import ModuleGD
from postgame.games.lol import ModuleLoL
from postgame.games.tft import ModuleTFT

MODULES: dict[str, ModuleJeu] = {}


def enregistrer(module: ModuleJeu) -> None:
    MODULES[module.nom] = module


def module_pour(chemin: Path) -> ModuleJeu | None:
    """Module capable d'importer ce fichier, d'après son extension."""
    ext = chemin.suffix.lower()
    for module in MODULES.values():
        if ext in module.extensions:
            return module
    return None


enregistrer(ModuleCS2())
enregistrer(ModuleGD())
enregistrer(ModuleLoL())
enregistrer(ModuleTFT())
