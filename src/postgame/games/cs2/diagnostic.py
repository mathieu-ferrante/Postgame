"""Diagnostic d'une démo CS2 : ce que demoparser2 y trouve réellement.

Sert à valider les hypothèses de lecture sur les vraies démos de Mathieu sans avoir besoin
de copier la démo elle-même : le rapport JSON est petit et suffit à ajuster le code.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from postgame.games.cs2.demo import construire_fiche, extraire


def _apercu(df: pd.DataFrame, lignes: int = 3) -> dict[str, Any]:
    return {
        "lignes": len(df),
        "colonnes": list(map(str, df.columns)),
        "exemple": df.head(lignes).astype(str).to_dict(orient="records"),
    }


def diagnostiquer(chemin: Path, steamid: str = "") -> dict[str, Any]:
    from demoparser2 import DemoParser

    debut = time.perf_counter()
    rapport: dict[str, Any] = {"fichier": chemin.name, "taille_octets": chemin.stat().st_size}
    parser = DemoParser(str(chemin))
    rapport["entete"] = parser.parse_header()
    evenements = parser.list_game_events()
    rapport["evenements_presents"] = sorted(evenements)
    rapport["evenements"] = {}
    for nom, df in parser.parse_events(sorted(evenements)):
        rapport["evenements"][nom] = _apercu(df)
    try:
        rapport["joueurs"] = _apercu(parser.parse_player_info(), lignes=12)
    except Exception as exc:
        rapport["joueurs"] = f"erreur : {exc}"

    donnees = extraire(chemin)
    rapport["etat_final"] = _apercu(donnees.etat_final, lignes=12)
    rapport["avertissements"] = donnees.avertissements
    rapport["fiche"] = asdict(construire_fiche(donnees, steamid))
    rapport["duree_diagnostic_s"] = round(time.perf_counter() - debut, 2)
    return rapport
