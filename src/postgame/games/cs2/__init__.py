"""Module Counter-Strike 2 : démos (.dem) lues par demoparser2."""

from __future__ import annotations

from pathlib import Path

from postgame.config import Config
from postgame.db import Mesure
from postgame.games.base import Fiche
from postgame.games.cs2.demo import construire_fiche, extraire


class ModuleCS2:
    nom = "cs2"
    libelle = "Counter-Strike 2"
    extensions = (".dem",)

    def dossiers_surveilles(self, cfg: Config) -> list[Path]:
        return list(cfg.dossiers_cs2)

    def lire_fiche(self, chemin: Path, cfg: Config) -> Fiche:
        return construire_fiche(extraire(chemin), cfg.steamid)

    def analyser(self, chemin: Path, cfg: Config) -> list[Mesure]:
        # Les mesures arrivent au lot L1 (mécanique) et suivants.
        return []
