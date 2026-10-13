"""Second écran League of Legends (LOL-07) : API locale officielle du client (Live Client
Data API), disponible seulement pendant une partie, sur https://127.0.0.1:2999.

Lecture seule, prévue par Riot pour les outils tiers. Le certificat est celui du client
LoL (racine Riot) : on ne vérifie pas le certificat de cette adresse locale uniquement.

Le résumé compare le farm en cours à la moyenne de Mathieu sur le même champion et à la
référence de haut classement du patch quand elle existe.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import httpx

from postgame.db import Base

journal = logging.getLogger(__name__)

URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"


CHAMPS_NOM = ("riotId", "riotIdGameName", "summonerName")


def _noms(joueur: dict[str, Any]) -> set[str]:
    """Toutes les façons dont le client nomme un joueur : Riot ID complet (« Nom#TAG »),
    nom de jeu seul, ancien nom d'invocateur (en cours de retrait chez Riot)."""
    noms = {str(joueur[c]).strip() for c in CHAMPS_NOM if joueur.get(c)}
    if joueur.get("riotIdGameName") and joueur.get("riotIdTagLine"):
        noms.add(f"{joueur['riotIdGameName']}#{joueur['riotIdTagLine']}")
    return {n.lower() for n in noms}


def trouver_moi(actif: dict[str, Any], joueurs: list[dict[str, Any]]) -> dict[str, Any] | None:
    mes_noms = _noms(actif)
    return next((j for j in joueurs if mes_noms & _noms(j)), None) if mes_noms else None


def resumer(
    donnees: dict[str, Any], references: dict[str, float | None] | None = None
) -> dict[str, Any]:
    actif = donnees.get("activePlayer", {})
    joueurs = donnees.get("allPlayers", [])
    moi = trouver_moi(actif, joueurs)
    temps = float(donnees.get("gameData", {}).get("gameTime", 0.0))
    minutes = temps / 60
    resume: dict[str, Any] = {
        "actif": True,
        "temps": round(temps),
        "niveau": actif.get("level"),
        "or": round(float(actif.get("currentGold", 0))),
    }
    if moi:
        scores = moi.get("scores", {})
        cs = int(scores.get("creepScore", 0))
        resume.update(
            champion=moi.get("championName"),
            equipe=moi.get("team"),
            kills=scores.get("kills", 0),
            morts=scores.get("deaths", 0),
            assistances=scores.get("assists", 0),
            cs=cs,
            cs_par_minute=round(cs / minutes, 1) if minutes >= 1 else None,
            vision=round(float(scores.get("wardScore", 0)), 1),
            objets=[o.get("displayName") for o in moi.get("items", [])],
        )
        adverse = [
            j
            for j in joueurs
            if j.get("team") != moi.get("team")
            and j.get("position")
            and j.get("position") == moi.get("position")
        ]
        if adverse:
            a = adverse[0]
            resume["adversaire"] = {
                "champion": a.get("championName"),
                "cs": int(a.get("scores", {}).get("creepScore", 0)),
                "niveau": a.get("level"),
            }
    resume["reperes"] = references or {}
    return resume


def reperes(base: Base, champion: str | None) -> dict[str, float | None]:
    """Farm moyen de Mathieu sur ce champion (10 dernières parties) et référence méta."""
    if not champion:
        return {}
    serie = [
        p["valeur"]
        for p in base.serie_mesure("lol.farm.cs_par_minute")
        if p["contexte"].get("champion") == champion and p["valeur"] is not None
    ][-10:]
    ref = [r for r in base.references("lol.farm.cs_par_minute", {"champion": champion})]
    return {
        "cs_par_minute_moyen": round(sum(serie) / len(serie), 1) if serie else None,
        "cs_par_minute_meta": round(ref[0]["valeur"], 1) if ref else None,
    }


class ScruteurLoL:
    def __init__(self, base: Base, intervalle: float = 0.5, client: httpx.Client | None = None):
        self.base, self.intervalle = base, intervalle
        self.client = client or httpx.Client(timeout=1.0, verify=False)  # 127.0.0.1 seulement
        self.resume: dict[str, Any] = {"actif": False}
        self._arret = threading.Event()
        self._fil: threading.Thread | None = None
        self._champion: str | None = None
        self._reperes: dict[str, float | None] = {}

    def passe(self) -> None:
        try:
            r = self.client.get(URL)
            r.raise_for_status()
            donnees = r.json()
        except (httpx.HTTPError, ValueError):
            self.resume = {"actif": False}  # pas de partie en cours
            return
        resume = resumer(donnees, self._reperes)
        if resume.get("champion") != self._champion:
            self._champion = resume.get("champion")
            self._reperes = reperes(self.base, self._champion)
            resume["reperes"] = self._reperes
        self.resume = resume

    def demarrer(self) -> None:
        if self._fil and self._fil.is_alive():
            return
        self._arret.clear()
        self._fil = threading.Thread(target=self._boucle, name="live-lol", daemon=True)
        self._fil.start()

    def arreter(self) -> None:
        self._arret.set()

    def _boucle(self) -> None:
        while not self._arret.is_set():
            self.passe()
            # Hors partie, inutile d'interroger deux fois par seconde.
            self._arret.wait(self.intervalle if self.resume.get("actif") else 5.0)
