"""Module Teamfight Tactics : parties récupérées par l'API Riot (TFT-01).

Fichier .tft (JSON) : {"format": 1, "puuid": …, "match": tft-match-v1}. Le set et le patch
accompagnent chaque mesure : une composition ne se juge que dans la méta de son patch.

Limite de l'API : elle ne donne que l'état final de chaque joueur (plateau, traits, objets,
augments, niveau, dernier round) ; le déroulé étape par étape (TFT-04) n'est pas disponible.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from postgame.config import Config
from postgame.games.base import ErreurLecture, Fiche
from postgame.mesures import Preuve, ResultatAnalyse, definir, mesure

FILES_TFT = {1100: "classée", 1090: "normale", 1130: "hyper roll", 1160: "double up"}

D_PLACEMENT = definir("tft.placement", 1, "place", "Place finale (1 = victoire).", sens="bas")
D_TOP4 = definir("tft.top4", 1, "%", "Partie finie dans les 4 premiers (100) ou non (0).")
D_DEGATS = definir("tft.degats_joueurs", 1, "PV", "Dégâts infligés aux autres joueurs.")
D_NIVEAU = definir("tft.niveau_final", 1, "niveau", "Niveau atteint.", sens="neutre")
D_OR = definir("tft.or_restant", 1, "or", "Or non dépensé à l'élimination.", sens="bas")
D_ROUND = definir("tft.dernier_round", 1, "round", "Dernier round joué.")


def patch_tft(version: str | None) -> str:
    """« Version 15.20.712.3456 (Oct 10 2025/…) [PUBLIC] » → « 15.20 »."""
    m = re.search(r"(\d+)\.(\d+)", str(version or ""))
    return f"{m.group(1)}.{m.group(2)}" if m else "inconnu"


def nom_court(identifiant: str) -> str:
    """« TFT15_Ahri » → « Ahri » ; « TFT15_Bastion » → « Bastion »."""
    return re.sub(r"^(TFT\d*_|Set\d+_)", "", str(identifiant)).replace("_", " ")


def lire_fichier(chemin: Path) -> dict[str, Any]:
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        moi(donnees)
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        raise ErreurLecture(f"partie TFT illisible : {exc}") from exc
    return donnees


def moi(donnees: dict[str, Any]) -> dict[str, Any]:
    return next(
        p for p in donnees["match"]["info"]["participants"] if p["puuid"] == donnees["puuid"]
    )


def cadre(donnees: dict[str, Any]) -> dict[str, Any]:
    info = donnees["match"]["info"]
    return {"set": info.get("tft_set_number"), "patch": patch_tft(info.get("game_version"))}


def composition(joueur: dict[str, Any]) -> dict[str, Any]:
    traits = sorted(
        (t for t in joueur.get("traits", []) if int(t.get("style", 0)) > 0),
        key=lambda t: (-int(t.get("style", 0)), -int(t.get("num_units", 0))),
    )
    return {
        "traits": [
            {
                "nom": nom_court(t["name"]),
                "unites": t.get("num_units"),
                "palier": t.get("tier_current"),
                "style": t.get("style"),
            }
            for t in traits
        ],
        "unites": [
            {
                "nom": nom_court(u["character_id"]),
                "etoiles": u.get("tier"),
                "objets": [nom_court(o) for o in u.get("itemNames", [])],
            }
            for u in joueur.get("units", [])
        ],
        "augments": [nom_court(a) for a in joueur.get("augments", [])],
    }


def construire_fiche(donnees: dict[str, Any]) -> Fiche:
    info = donnees["match"]["info"]
    j = moi(donnees)
    c = cadre(donnees)
    compo = composition(j)
    principal = compo["traits"][0]["nom"] if compo["traits"] else "?"
    return Fiche(
        date_partie=datetime.fromtimestamp(info.get("game_datetime", 0) / 1000, UTC).isoformat(
            timespec="seconds"
        ),
        mode=FILES_TFT.get(int(info.get("queue_id", 0)), f"file {info.get('queue_id')}"),
        carte=f"Set {c['set']} — {principal}",
        resultat="victoire" if int(j["placement"]) <= 4 else "defaite",
        score_joueur=int(j["placement"]),
        duree_s=round(float(info.get("game_length", 0)), 1),
        details={
            **c,
            "composition": compo,
            "niveau": j.get("level"),
            "match_id": donnees["match"]["metadata"].get("match_id"),
        },
    )


def analyser_tft(donnees: dict[str, Any]) -> ResultatAnalyse:
    j = moi(donnees)
    c = cadre(donnees)
    r = ResultatAnalyse()
    place = int(j["placement"])
    r.mesures += [
        mesure(D_PLACEMENT, place, **c),
        mesure(D_TOP4, 100.0 if place <= 4 else 0.0, **c),
        mesure(D_DEGATS, j.get("total_damage_to_players", 0), **c),
        mesure(D_NIVEAU, j.get("level", 0), **c),
        mesure(D_OR, j.get("gold_left", 0), **c),
        mesure(D_ROUND, j.get("last_round", 0), **c),
    ]
    compo = composition(j)
    traits = ", ".join(f"{t['nom']} {t['unites']}" for t in compo["traits"][:4])
    r.preuves.append(
        Preuve(
            D_PLACEMENT.nom,
            None,
            f"{place}e avec {traits or 'aucun trait actif'} (niveau "
            f"{j.get('level')}, {j.get('gold_left', 0)} or restant)",
            None,
            compo,
        )
    )
    return r


class ModuleTFT:
    nom = "tft"
    libelle = "Teamfight Tactics"
    extensions = (".tft",)
    cout = "leger"

    def dossiers_surveilles(self, cfg: Config) -> list[Path]:
        return []

    def lire_fiche(self, chemin: Path, cfg: Config) -> Fiche:
        return construire_fiche(lire_fichier(chemin))

    def analyser(self, chemin: Path, cfg: Config) -> ResultatAnalyse:
        return analyser_tft(lire_fichier(chemin))
