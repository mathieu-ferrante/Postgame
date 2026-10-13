"""Module League of Legends : parties récupérées par l'API Riot (LOL-01).

Le collecteur (games/riot/collecte.py) écrit chaque partie dans un fichier .lol (JSON) :
{"format": 1, "puuid": …, "match": match-v5, "timeline": chronologie, "rang": …},
importé ensuite comme n'importe quelle démo (archivage, fiche, mesures, débrief).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from postgame.config import Config
from postgame.games.base import ErreurLecture, Fiche
from postgame.games.lol.analyse import POSTES, Contexte, analyser_lol, patch_de
from postgame.games.riot.ddragon import DataDragon
from postgame.mesures import ResultatAnalyse

FILES = {
    420: "classée solo",
    440: "classée flexible",
    400: "normale (draft)",
    430: "normale (aveugle)",
    490: "partie rapide",
    450: "ARAM",
    700: "Clash",
    1700: "Arena",
    1900: "URF",
}


def lire_fichier(chemin: Path) -> dict[str, Any]:
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        donnees["match"]["info"]["participants"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ErreurLecture(f"partie LoL illisible : {exc}") from exc
    return donnees


def construire_fiche(donnees: dict[str, Any]) -> Fiche:
    c = Contexte(donnees["match"], donnees.get("timeline", {}), donnees["puuid"])
    info = donnees["match"]["info"]
    debut_ms = info.get("gameStartTimestamp") or info.get("gameCreation") or 0
    moi = c.moi
    return Fiche(
        date_partie=datetime.fromtimestamp(debut_ms / 1000, UTC).isoformat(timespec="seconds"),
        mode=FILES.get(int(info.get("queueId", 0)), f"file {info.get('queueId')}"),
        carte=f"{moi['championName']} — {POSTES.get(c.poste, c.poste.lower() or '?')}",
        resultat="victoire" if moi.get("win") else "defaite",
        duree_s=round(c.minutes * 60, 1),
        details={
            "champion": moi["championName"],
            "role": c.poste,
            "patch": patch_de(info.get("gameVersion")),
            "kda": f"{moi.get('kills', 0)}/{moi.get('deaths', 0)}/{moi.get('assists', 0)}",
            "adversaire": c.adversaire["championName"] if c.adversaire else None,
            "match_id": donnees["match"]["metadata"].get("matchId"),
            "rang": donnees.get("rang"),
        },
    )


def donnees_replay(donnees: dict[str, Any]) -> dict[str, Any]:
    """Carte minute par minute (LOL-06) : positions des 10 joueurs, kills et objectifs."""
    info = donnees["match"]["info"]
    joueurs = [
        {
            "id": int(p["participantId"]),
            "champion": p["championName"],
            "equipe": int(p["teamId"]),
            "moi": p["puuid"] == donnees["puuid"],
            "role": p.get("teamPosition", ""),
        }
        for p in info["participants"]
    ]
    frames = donnees.get("timeline", {}).get("info", {}).get("frames", [])
    minutes = [
        {
            "t": f.get("timestamp", 0),
            "positions": {
                pid: [e["position"]["x"], e["position"]["y"]]
                for pid, e in f.get("participantFrames", {}).items()
                if "position" in e
            },
        }
        for f in frames
    ]
    evenements = [
        {
            "type": e["type"],
            "t": e["timestamp"],
            "x": e.get("position", {}).get("x"),
            "y": e.get("position", {}).get("y"),
            "tueur": e.get("killerId"),
            "victime": e.get("victimId"),
            "assistants": e.get("assistingParticipantIds", []),
            "monstre": e.get("monsterType"),
            "equipe": e.get("killerTeamId") or e.get("teamId"),
        }
        for f in frames
        for e in f.get("events", [])
        if e.get("type") in ("CHAMPION_KILL", "ELITE_MONSTER_KILL", "BUILDING_KILL")
    ]
    return {
        "joueurs": joueurs,
        "minutes": minutes,
        "evenements": evenements,
        "patch": patch_de(info.get("gameVersion")),
    }


class ModuleLoL:
    nom = "lol"
    libelle = "League of Legends"
    extensions = (".lol",)

    def dossiers_surveilles(self, cfg: Config) -> list[Path]:
        return []  # les parties arrivent par l'API Riot, pas par un dossier du jeu

    def lire_fiche(self, chemin: Path, cfg: Config) -> Fiche:
        return construire_fiche(lire_fichier(chemin))

    def analyser(self, chemin: Path, cfg: Config) -> ResultatAnalyse:
        donnees = lire_fichier(chemin)
        patch = patch_de(donnees["match"]["info"].get("gameVersion"))
        classes = (
            {} if cfg.hors_ligne else DataDragon(cfg.dossier_donnees / "ddragon").classes(patch)
        )
        return analyser_lol(
            donnees["match"], donnees.get("timeline", {}), donnees["puuid"], classes
        )
