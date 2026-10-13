"""Interface commune des modules de jeu.

Chaque jeu (CS2, Geometry Dash, LoL, TFT) est un module qui sait reconnaître ses fichiers et
en tirer une fiche de partie. Les analyseurs (mesures) s'ajoutent aux lots suivants derrière
la même interface, pour qu'ajouter un jeu ne touche pas au reste.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from postgame.config import Config
from postgame.mesures import ResultatAnalyse


@dataclass
class Fiche:
    """Ce qu'un module de jeu extrait d'un fichier (COM-02)."""

    date_partie: str
    mode: str
    carte: str
    resultat: str  # victoire, defaite, nul, sans_objet, inconnu
    score_joueur: int | None = None
    score_adverse: int | None = None
    duree_s: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ErreurLecture(Exception):
    """Le fichier n'a pas pu être lu (corrompu, incomplet, format inconnu)."""


class ModuleJeu(Protocol):
    nom: str  # identifiant court : 'cs2', 'gd'…
    libelle: str  # nom affiché
    extensions: tuple[str, ...]  # extensions de fichiers importables, en minuscules

    def dossiers_surveilles(self, cfg: Config) -> list[Path]: ...

    def lire_fiche(self, chemin: Path, cfg: Config) -> Fiche: ...

    def analyser(self, chemin: Path, cfg: Config) -> ResultatAnalyse: ...
