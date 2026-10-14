"""Client de l'API Riot (LOL-01, TFT-01).

- Clé personnelle de Mathieu : secrets.toml `[riot] cle`, ou RIOT_API_KEY ; jamais commitée.
- Débit : clé personnelle / développement = 20 requêtes par seconde et 100 par 2 minutes.
  Le client attend ce qu'il faut avant chaque requête et respecte `Retry-After` sur 429.
- Cache disque des réponses immuables (matchs, chronologies) : un match n'est demandé
  qu'une fois.

Routage : match-v5, tft-match-v1 et account-v1 passent par la région (`europe`) ;
league-v4 et tft-league-v1 par la plateforme (`euw1`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

journal = logging.getLogger(__name__)

LIMITES = [(20, 1.0), (100, 120.0)]  # (requêtes, fenêtre en secondes)


class ErreurRiot(Exception):
    def __init__(self, message: str, statut: int | None = None):
        super().__init__(message)
        self.statut = statut


class Limiteur:
    """Fenêtres glissantes : avant chaque requête, attend qu'il reste de la place."""

    def __init__(
        self,
        limites=LIMITES,
        horloge: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
    ):
        self.limites = limites
        self.horloge, self.dormir = horloge, dormir
        self.historique: deque[float] = deque()
        self.verrou = threading.Lock()

    def attendre(self) -> None:
        with self.verrou:
            while True:
                maintenant = self.horloge()
                plus_longue = max(f for _, f in self.limites)
                while self.historique and maintenant - self.historique[0] > plus_longue:
                    self.historique.popleft()
                attente = 0.0
                for nombre, fenetre in self.limites:
                    recentes = [t for t in self.historique if maintenant - t < fenetre]
                    if len(recentes) >= nombre:
                        attente = max(attente, fenetre - (maintenant - recentes[-nombre]) + 0.01)
                if attente <= 0:
                    self.historique.append(maintenant)
                    return
                self.dormir(attente)


class ClientRiot:
    def __init__(
        self,
        cle: str,
        plateforme: str = "euw1",
        region: str = "europe",
        dossier_cache: Path | None = None,
        client: httpx.Client | None = None,
        limiteur: Limiteur | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ):
        if not cle:
            raise ErreurRiot("clé API Riot absente (secrets.toml, section [riot])")
        self.cle, self.plateforme, self.region = cle, plateforme, region
        self.dossier_cache = dossier_cache
        self.client = client or httpx.Client(timeout=20)
        self.limiteur = limiteur or Limiteur()
        self.dormir = dormir
        self.requetes = 0

    # --- Bas niveau ----------------------------------------------------------------------

    def _get(
        self, hote: str, chemin: str, params: dict[str, Any] | None = None, cache: bool = False
    ) -> Any:
        url = f"https://{hote}.api.riotgames.com{chemin}"
        fichier = self._fichier_cache(url, params) if cache else None
        if fichier is not None and fichier.exists():
            try:
                return json.loads(fichier.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                fichier.unlink(missing_ok=True)  # cache abîmé : on retélécharge
        for _essai in range(5):
            self.limiteur.attendre()
            self.requetes += 1
            try:
                r = self.client.get(url, params=params, headers={"X-Riot-Token": self.cle})
            except httpx.HTTPError as exc:
                raise ErreurRiot(f"réseau : {exc}") from exc
            if r.status_code == 429:
                attente = float(r.headers.get("Retry-After", "5"))
                journal.info("API Riot : limite atteinte, attente de %s s", attente)
                self.dormir(attente)
                continue
            if r.status_code in (500, 502, 503, 504):
                self.dormir(2)
                continue
            if r.status_code == 403:
                raise ErreurRiot("clé API Riot refusée (expirée ?)", 403)
            if r.status_code == 404:
                raise ErreurRiot("introuvable", 404)
            if r.status_code != 200:
                raise ErreurRiot(f"réponse {r.status_code}", r.status_code)
            try:
                donnees = r.json()
            except ValueError as exc:
                raise ErreurRiot(f"réponse illisible : {exc}") from exc
            if fichier is not None:
                from postgame.games.riot.collecte import ecrire_atomique

                ecrire_atomique(fichier, json.dumps(donnees))
            return donnees
        raise ErreurRiot("API Riot indisponible après plusieurs essais")

    def _fichier_cache(self, url: str, params: dict[str, Any] | None) -> Path | None:
        if self.dossier_cache is None:
            return None
        cle = hashlib.sha1((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
        return self.dossier_cache / f"{cle}.json"

    # --- Compte ---------------------------------------------------------------------------

    def compte(self, riot_id: str) -> dict[str, Any]:
        """« Pseudo#TAG » → {puuid, gameName, tagLine}."""
        if "#" not in riot_id:
            raise ErreurRiot("Riot ID attendu sous la forme Pseudo#TAG")
        nom, tag = riot_id.rsplit("#", 1)
        return self._get(
            self.region, f"/riot/account/v1/accounts/by-riot-id/{quote(nom)}/{quote(tag)}"
        )

    # --- League of Legends ----------------------------------------------------------------

    def parties_lol(
        self, puuid: str, nombre: int = 20, debut: int = 0, file: int | None = None
    ) -> list[str]:
        params: dict[str, Any] = {"start": debut, "count": nombre}
        if file is not None:
            params["queue"] = file
        return self._get(self.region, f"/lol/match/v5/matches/by-puuid/{puuid}/ids", params)

    def challengers_lol(self, file: str = "RANKED_SOLO_5x5") -> dict[str, Any]:
        return self._get(self.plateforme, f"/lol/league/v4/challengerleagues/by-queue/{file}")

    def partie_lol(self, match_id: str) -> dict[str, Any]:
        return self._get(self.region, f"/lol/match/v5/matches/{match_id}", cache=True)

    def chronologie_lol(self, match_id: str) -> dict[str, Any]:
        return self._get(self.region, f"/lol/match/v5/matches/{match_id}/timeline", cache=True)

    def rangs_lol(self, puuid: str) -> list[dict[str, Any]]:
        return self._get(self.plateforme, f"/lol/league/v4/entries/by-puuid/{puuid}")

    # --- Teamfight Tactics -----------------------------------------------------------------

    def parties_tft(self, puuid: str, nombre: int = 20) -> list[str]:
        return self._get(
            self.region, f"/tft/match/v1/matches/by-puuid/{puuid}/ids", {"count": nombre}
        )

    def partie_tft(self, match_id: str) -> dict[str, Any]:
        return self._get(self.region, f"/tft/match/v1/matches/{match_id}", cache=True)

    def challengers_tft(self) -> dict[str, Any]:
        return self._get(self.plateforme, "/tft/league/v1/challenger")
