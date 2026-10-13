"""Débrief structuré : constats chiffrés, priorisés, reliés à leurs preuves (COM-04, COM-06).

Un constat = une mesure de la partie comparée à la moyenne personnelle de Mathieu (même jeu,
même mode, parties précédentes) et, quand elle existe, à une cible. Son impact estimé
combine l'écart à la cible, la dégradation par rapport à l'habitude, le poids de la mesure
et la taille de l'échantillon. Les 3 constats d'impact le plus fort sont les priorités.

Seules les mesures fiables (vérifiées à la main) entrent dans le débrief (NF-06), sauf si
la configuration active les mesures expérimentales — elles sont alors marquées.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from typing import Any

from postgame.db import Base, Partie
from postgame.debrief.objectifs import objectif
from postgame.mesures import DEFINITIONS, DefinitionMesure

NB_PRIORITES = 3
NB_POINTS_FORTS = 2
NB_PREUVES = 5
ECHANTILLON_MIN = 5  # en dessous, la mesure d'une partie est trop bruitée
ECHANTILLON_PLEIN = 20  # à partir de là, confiance totale
SEUIL_IMPACT = 0.3
CLES_TECHNIQUES = {"n", "total"}  # clés de contexte qui ne distinguent pas une mesure


def charger_definitions() -> None:
    """Importe les analyseurs pour que leurs définitions soient enregistrées."""
    import postgame.games.cs2.analyse  # noqa: F401


@dataclass
class Constat:
    id: str
    mesure: str
    libelle: str
    valeur: float
    unite: str
    sens: str
    contexte: dict[str, Any]
    n: int | None
    reference: float | None  # moyenne personnelle
    nb_reference: int
    cible: float | None
    impact: float
    statut: str  # a_corriger, point_fort, neutre
    experimental: bool
    preuves: list[dict[str, Any]] = field(default_factory=list)

    def en_dict(self) -> dict[str, Any]:
        return asdict(self)


def fiabilite_effective(base: Base, definition: DefinitionMesure) -> bool:
    return base.fiabilites().get((definition.nom, definition.version), definition.fiable)


def _contexte_utile(contexte: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in contexte.items() if k not in CLES_TECHNIQUES}


def reference_personnelle(
    base: Base, partie: Partie, nom: str, contexte: dict[str, Any], limite: int
) -> list[float]:
    """Valeurs de la mesure sur les `limite` parties précédentes du même jeu et mode."""
    utile = _contexte_utile(contexte)
    valeurs = []
    for point in reversed(base.serie_mesure(nom)):
        if point["partie_id"] == partie.id or point["date_partie"] >= partie.date_partie:
            continue
        if point["mode"] != partie.mode or point["valeur"] is None:
            continue
        if _contexte_utile(point["contexte"]) != utile:
            continue
        valeurs.append(float(point["valeur"]))
        if len(valeurs) >= limite:
            break
    return valeurs


def estimer_impact(
    valeur: float,
    sens: str,
    reference: float | None,
    cible: float | None,
    echelle: float,
    poids: float,
    n: int | None,
) -> tuple[float, str]:
    """(impact, statut). Positif = à corriger ; un écart dans le bon sens ne compte pas."""
    signe = 1.0 if sens == "haut" else -1.0
    ecart_cible = signe * (cible - valeur) / echelle if cible is not None else 0.0
    ecart_habitude = signe * (reference - valeur) / echelle if reference is not None else 0.0
    confiance = min(1.0, (n or ECHANTILLON_PLEIN) / ECHANTILLON_PLEIN)
    impact = poids * confiance * (max(ecart_cible, 0.0) + 0.5 * max(ecart_habitude, 0.0))
    meilleur_cible = cible is not None and ecart_cible <= 0
    meilleur_habitude = reference is not None and ecart_habitude < -0.5
    if impact > SEUIL_IMPACT:
        statut = "a_corriger"
    elif meilleur_cible and (reference is None or ecart_habitude <= 0) or meilleur_habitude:
        statut = "point_fort"
    else:
        statut = "neutre"
    return round(impact, 3), statut


def lien_preuve(partie: Partie, tick: int | None) -> str:
    return f"/replay/{partie.id}" + (f"?tick={tick}" if tick is not None else "")


def construire_constats(
    base: Base, partie: Partie, historique: int = 10, experimentales: bool = False
) -> tuple[list[Constat], int]:
    """(constats triés par impact décroissant, nombre de mesures écartées car non fiables)."""
    charger_definitions()
    constats: list[Constat] = []
    masquees: set[str] = set()
    for m in base.mesures_partie(partie.id):
        definition = DEFINITIONS.get(m["nom"])
        if definition is None or definition.sens == "neutre" or m["valeur"] is None:
            continue
        fiable = fiabilite_effective(base, definition)
        if not fiable and not experimentales:
            masquees.add(m["nom"])
            continue
        n = m["contexte"].get("n")
        if n is not None and n < ECHANTILLON_MIN:
            continue
        precedentes = reference_personnelle(base, partie, m["nom"], m["contexte"], historique)
        reference = statistics.fmean(precedentes) if precedentes else None
        obj = objectif(m["nom"], m["unite"], reference)
        impact, statut = estimer_impact(
            float(m["valeur"]), definition.sens, reference, obj.cible, obj.echelle, obj.poids, n
        )
        constats.append(
            Constat(
                id="",
                mesure=m["nom"],
                libelle=definition.description,
                valeur=float(m["valeur"]),
                unite=m["unite"],
                sens=definition.sens,
                contexte=_contexte_utile(m["contexte"]),
                n=n,
                reference=None if reference is None else round(reference, 2),
                nb_reference=len(precedentes),
                cible=obj.cible,
                impact=impact,
                statut=statut,
                experimental=not fiable,
            )
        )
    constats.sort(key=lambda c: (-c.impact, c.mesure))
    for i, c in enumerate(constats, start=1):
        c.id = f"C{i}"
        preuves = base.preuves_partie(partie.id, c.mesure)
        if c.contexte.get("arme"):
            preuves = [p for p in preuves if p["donnees"].get("arme") in (None, c.contexte["arme"])]
        c.preuves = [
            {**p, "partie_id": partie.id, "lien": lien_preuve(partie, p["tick"])}
            for p in preuves[:NB_PREUVES]
        ]
    return constats, len(masquees)


def selectionner(constats: list[Constat]) -> dict[str, list[Constat]]:
    """Priorités (3 max, mesures distinctes), points forts, détail."""
    priorites, vues = [], set()
    for c in constats:
        if c.statut == "a_corriger" and c.mesure not in vues and len(priorites) < NB_PRIORITES:
            priorites.append(c)
            vues.add(c.mesure)
    points_forts = [c for c in constats if c.statut == "point_fort"][:NB_POINTS_FORTS]
    choisis = {id(c) for c in priorites + points_forts}
    details = [c for c in constats if id(c) not in choisis]
    return {"priorites": priorites, "points_forts": points_forts, "details": details}
