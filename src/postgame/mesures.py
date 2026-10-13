"""Registre des mesures et des preuves.

Chaque mesure a un nom, une version, une unité et une description (cahier des charges §6),
plus un statut de fiabilité : seule une mesure `fiable` peut alimenter le débrief (NF-06).
Une mesure passe fiable quand elle a été vérifiée à la main sur données réelles.

Une preuve rattache un constat à un moment précis (partie, round, tick) pour COM-04.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from postgame.db import Mesure


@dataclass(frozen=True)
class DefinitionMesure:
    nom: str
    version: int
    unite: str
    description: str
    sens: str = "haut"  # « haut » : plus c'est haut mieux c'est ; « bas » ; « neutre »
    fiable: bool = False  # vérifiée à la main sur données réelles


@dataclass
class Preuve:
    """Moment du replay qui illustre une mesure."""

    mesure: str
    tick: int | None
    texte: str
    round: int | None = None
    donnees: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultatAnalyse:
    mesures: list[Mesure] = field(default_factory=list)
    preuves: list[Preuve] = field(default_factory=list)

    def etendre(self, autre: ResultatAnalyse) -> None:
        self.mesures.extend(autre.mesures)
        self.preuves.extend(autre.preuves)


DEFINITIONS: dict[str, DefinitionMesure] = {}


def definir(
    nom: str, version: int, unite: str, description: str, sens: str = "haut", fiable: bool = False
) -> DefinitionMesure:
    d = DefinitionMesure(nom, version, unite, description, sens, fiable)
    DEFINITIONS[nom] = d
    return d


def mesure(definition: DefinitionMesure, valeur: float | None, **contexte: Any) -> Mesure:
    """Instancie une mesure à partir de sa définition (nom, version et unité cohérents)."""
    if valeur is not None:
        valeur = round(float(valeur), 4)
    return Mesure(definition.nom, definition.version, valeur, definition.unite, contexte)
