"""Outils de test communs.

`ModuleFactice` est un faux jeu (extension .factice) : il permet de tester l'import, la
surveillance et l'API sans vraie démo. Le contenu du fichier décide du résultat :
une ligne « carte=… » donne la carte, « illisible » simule un fichier corrompu.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from postgame.config import Config
from postgame.db import Base, Mesure
from postgame.games import MODULES, enregistrer
from postgame.games.base import ErreurLecture, Fiche

DOSSIER_DONNEES_TEST = Path(__file__).parent / "donnees"


class ModuleFactice:
    nom = "factice"
    libelle = "Jeu factice"
    extensions = (".factice",)

    def __init__(self) -> None:
        self.dossiers: list[Path] = []

    def dossiers_surveilles(self, cfg: Config) -> list[Path]:
        return self.dossiers

    def lire_fiche(self, chemin: Path, cfg: Config) -> Fiche:
        texte = chemin.read_text(encoding="utf-8")
        if "illisible" in texte:
            raise ErreurLecture("fichier factice illisible")
        carte = "de_test"
        for ligne in texte.splitlines():
            if ligne.startswith("carte="):
                carte = ligne.split("=", 1)[1]
        return Fiche(
            date_partie="2026-10-01T20:00:00+00:00",
            mode="competitif",
            carte=carte,
            resultat="victoire",
            score_joueur=13,
            score_adverse=7,
            duree_s=1800.0,
        )

    def analyser(self, chemin: Path, cfg: Config) -> list[Mesure]:
        return [Mesure("factice.taille", 1, float(chemin.stat().st_size), "octets")]


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return Config(dossier_donnees=tmp_path / "data", dossiers_cs2=[], delai_stabilite_s=0.0)


@pytest.fixture
def base(cfg: Config):
    b = Base(cfg.chemin_base)
    yield b
    b.fermer()


@pytest.fixture
def factice():
    module = ModuleFactice()
    enregistrer(module)
    yield module
    MODULES.pop(module.nom, None)
