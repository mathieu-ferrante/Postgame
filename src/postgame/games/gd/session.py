"""Lecture d'un journal de séance Geometry Dash écrit par le mod Geode (format 1).

Voir mods/gd-journal/LISEZMOI.md pour le format. Une séance = un passage dans un niveau.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from postgame.games.base import ErreurLecture


@dataclass
class Clic:
    t: float  # ms depuis l'entrée dans le niveau
    x: float
    appui: bool
    joueur: int = 1
    tn: float | None = None  # temps du niveau selon le jeu (s)
    frame: int | None = None


@dataclass
class Essai:
    numero: int
    mode: str  # normal, practice
    t_debut: float
    x_debut: float
    clics: list[Clic] = field(default_factory=list)
    positions: list[tuple[float, float]] = field(default_factory=list)  # (t, x)
    t_fin: float | None = None
    x_fin: float | None = None
    pct_fin: float | None = None
    mort: bool = False
    complete: bool = False
    objet: int | None = None  # objet touché à la mort

    @property
    def appuis(self) -> list[Clic]:
        return [c for c in self.clics if c.appui and c.joueur == 1]

    def instant_a(self, x: float) -> float | None:
        """Instant (ms) où l'essai atteint la position x, par interpolation linéaire."""
        points = sorted(self.positions + [(c.t, c.x) for c in self.clics])
        if not points or x < points[0][1] or x > points[-1][1]:
            return None
        for (t0, x0), (t1, x1) in zip(points, points[1:], strict=False):
            if x0 <= x <= x1:
                return t0 if x1 == x0 else t0 + (t1 - t0) * (x - x0) / (x1 - x0)
        return None


@dataclass
class Session:
    niveau_id: int
    niveau: str
    createur: str
    debut: datetime
    plateforme: bool
    essais: list[Essai]
    duree_ms: float
    version_mod: str = ""
    avertissements: list[str] = field(default_factory=list)


def lire_session(chemin: Path) -> Session:
    try:
        lignes = chemin.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ErreurLecture(f"journal GD illisible : {exc}") from exc
    return analyser_lignes(lignes)


def analyser_lignes(lignes: list[str]) -> Session:
    entete: dict[str, Any] | None = None
    essais: list[Essai] = []
    courant: Essai | None = None
    dernier_t = 0.0
    avertissements: list[str] = []
    for numero, ligne in enumerate(lignes, start=1):
        if not ligne.strip():
            continue
        try:
            ev = json.loads(ligne)
        except json.JSONDecodeError:
            avertissements.append(f"ligne {numero} illisible")
            continue
        type_ = ev.get("type")
        dernier_t = float(ev.get("t", dernier_t))
        if type_ == "session":
            entete = ev
        elif type_ == "essai":
            if courant is not None and courant.t_fin is None:
                courant.t_fin = dernier_t  # recommencé sans mourir (pause → recommencer)
            courant = Essai(
                numero=int(ev.get("n", len(essais) + 1)),
                mode=str(ev.get("mode", "normal")),
                t_debut=float(ev["t"]),
                x_debut=float(ev.get("x", 0.0)),
            )
            essais.append(courant)
        elif courant is None:
            continue
        elif type_ == "input":
            courant.clics.append(
                Clic(
                    t=float(ev["t"]),
                    x=float(ev["x"]),
                    appui=bool(ev["appui"]),
                    joueur=int(ev.get("j", 1)),
                    tn=ev.get("tn"),
                    frame=ev.get("f"),
                )
            )
        elif type_ == "pos":
            courant.positions.append((float(ev["t"]), float(ev["x"])))
        elif type_ == "mort":
            courant.mort, courant.t_fin = True, float(ev["t"])
            courant.x_fin, courant.pct_fin = float(ev["x"]), float(ev.get("pct", 0.0))
            courant.objet = ev.get("objet")
        elif type_ == "fin":
            courant.complete, courant.t_fin, courant.pct_fin = True, float(ev["t"]), 100.0
            courant.x_fin = max(
                [x for _, x in courant.positions] + [c.x for c in courant.clics] + [courant.x_debut]
            )
    if entete is None:
        raise ErreurLecture("journal GD sans en-tête de séance")
    niveau = entete.get("niveau", {})
    try:
        debut = datetime.fromisoformat(str(entete.get("debut"))).astimezone()
    except ValueError:
        debut = datetime.now().astimezone()
        avertissements.append("date de séance illisible")
    return Session(
        niveau_id=int(niveau.get("id", 0)),
        niveau=str(niveau.get("nom", "inconnu")),
        createur=str(niveau.get("createur", "")),
        debut=debut,
        plateforme=bool(entete.get("plateforme", False)),
        essais=[e for e in essais if e.t_fin is not None or e.clics],
        duree_ms=dernier_t,
        version_mod=str(entete.get("mod", "")),
        avertissements=avertissements,
    )
