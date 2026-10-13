"""Références de haut classement par patch (CTX-01, TFT-03), calculées avec l'API Riot.

LoL : on prend les parties classées récentes de joueurs Challenger, on applique à **chacun
des 10 joueurs** de ces parties les mêmes analyses qu'à Mathieu, et on garde la médiane de
chaque mesure par (champion, rôle, minute…) et par patch, ainsi qu'au niveau du rôle seul
(repli quand le champion est trop peu joué). Résultat : la cible d'un constat devient
« ce que fait le haut classement avec ce champion, à ce poste, sur ce patch ».

TFT : statistiques par set et patch des 8 joueurs de parties Challenger (tft/stats.py).

Budget : clé personnelle à 100 requêtes / 2 min ; une partie LoL coûte 2 requêtes (match +
chronologie), mise en cache. 100 parties ≈ 4 à 5 minutes. À relancer à chaque patch.
"""

from __future__ import annotations

import json
import logging
import statistics
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from postgame.db import Base
from postgame.debrief.constats import contexte_discriminant
from postgame.games.lol.analyse import analyser_lol, patch_de
from postgame.games.riot.client import ClientRiot, ErreurRiot
from postgame.games.tft.stats import observations, statistiques

journal = logging.getLogger(__name__)

FILE_CLASSEE_SOLO = 420
MIN_ECHANTILLON = 5


def echantillons_lol(
    match: dict[str, Any], chrono: dict[str, Any], classes: dict[str, list[str]] | None = None
) -> list[tuple[str, dict, str, float]]:
    """(mesure, contexte discriminant, patch, valeur) pour chacun des 10 joueurs."""
    patch = patch_de(match["info"].get("gameVersion"))
    sortie = []
    for joueur in match["info"]["participants"]:
        try:
            r = analyser_lol(match, chrono, joueur["puuid"], classes)
        except (KeyError, StopIteration):
            continue
        for m in r.mesures:
            if m.valeur is None:
                continue
            contexte = contexte_discriminant(m.contexte)
            sortie.append((m.nom, contexte, patch, float(m.valeur)))
            if "champion" in contexte:  # repli : même rôle, tous champions
                sortie.append(
                    (
                        m.nom,
                        {k: v for k, v in contexte.items() if k != "champion"},
                        patch,
                        float(m.valeur),
                    )
                )
    return sortie


def agreger(
    echantillons: list[tuple[str, dict, str, float]],
    source: str,
    jeu: str = "lol",
    minimum: int = MIN_ECHANTILLON,
) -> list[dict[str, Any]]:
    groupes: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for nom, contexte, patch, valeur in echantillons:
        groupes[(nom, json.dumps(contexte, sort_keys=True), patch)].append(valeur)
    return [
        {
            "jeu": jeu,
            "nom": nom,
            "contexte": json.loads(contexte),
            "patch": patch,
            "valeur": statistics.median(valeurs),
            "n": len(valeurs),
            "source": source,
        }
        for (nom, contexte, patch), valeurs in groupes.items()
        if len(valeurs) >= minimum
    ]


def joueurs_challenger(ligue: dict[str, Any], nombre: int) -> list[str]:
    entrees = sorted(ligue.get("entries", []), key=lambda e: -int(e.get("leaguePoints", 0)))
    return [e["puuid"] for e in entrees if e.get("puuid")][:nombre]


def construire_meta_lol(
    client: ClientRiot,
    base: Base,
    joueurs: int = 10,
    parties: int = 5,
    classes: Callable[[str], dict[str, list[str]]] | None = None,
) -> dict[str, int]:
    vus: set[str] = set()
    echantillons = []
    for puuid in joueurs_challenger(client.challengers_lol(), joueurs):
        try:
            identifiants = client.parties_lol(puuid, parties, file=FILE_CLASSEE_SOLO)
        except ErreurRiot as exc:
            journal.warning("méta LoL : %s", exc)
            continue
        for match_id in identifiants:
            if match_id in vus:
                continue
            vus.add(match_id)
            try:
                match, chrono = client.partie_lol(match_id), client.chronologie_lol(match_id)
            except ErreurRiot as exc:
                journal.warning("méta LoL %s : %s", match_id, exc)
                continue
            patch = patch_de(match["info"].get("gameVersion"))
            echantillons += echantillons_lol(match, chrono, classes(patch) if classes else None)
    lignes = agreger(echantillons, f"haut classement {client.plateforme.upper()}")
    base.enregistrer_references(lignes)
    return {"parties": len(vus), "references": len(lignes)}


def construire_meta_tft(
    client: ClientRiot, dossier: Path, joueurs: int = 10, parties: int = 5
) -> dict[str, int]:
    vus: set[str] = set()
    obs = []
    for puuid in joueurs_challenger(client.challengers_tft(), joueurs):
        try:
            identifiants = client.parties_tft(puuid, parties)
        except ErreurRiot as exc:
            journal.warning("méta TFT : %s", exc)
            continue
        for match_id in identifiants:
            if match_id in vus:
                continue
            vus.add(match_id)
            try:
                obs += observations(client.partie_tft(match_id))
            except ErreurRiot as exc:
                journal.warning("méta TFT %s : %s", match_id, exc)
    reference = statistiques(obs, minimum=MIN_ECHANTILLON)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "tft_reference.json").write_text(
        json.dumps(reference, ensure_ascii=False), encoding="utf-8"
    )
    return {"parties": len(vus), "patchs": len(reference)}


def lire_reference_tft(dossier: Path) -> dict[str, Any]:
    fichier = dossier / "tft_reference.json"
    return json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else {}
