"""Module Counter-Strike 2 : démos (.dem) lues par demoparser2."""

from __future__ import annotations

from pathlib import Path

from postgame.config import Config
from postgame.games.base import Fiche
from postgame.games.cs2.analyse import analyser_match
from postgame.games.cs2.demo import construire_fiche, extraire
from postgame.games.cs2.donnees import extraire_match
from postgame.games.cs2.references import catalogue_pour
from postgame.mesures import ResultatAnalyse


class ModuleCS2:
    nom = "cs2"
    libelle = "Counter-Strike 2"
    extensions = (".dem",)

    def dossiers_surveilles(self, cfg: Config) -> list[Path]:
        return list(cfg.dossiers_cs2)

    def lire_fiche(self, chemin: Path, cfg: Config) -> Fiche:
        return construire_fiche(extraire(chemin), cfg.steamid)

    def analyser(self, chemin: Path, cfg: Config) -> ResultatAnalyse:
        donnees = extraire_match(chemin, cfg.steamid)
        return analyser_match(donnees, catalogue_pour(cfg.chemin_base, donnees.carte))
