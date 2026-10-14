"""Collecte automatique des parties LoL et TFT de Mathieu (LOL-01, TFT-01, CPT-01).

Toutes les `riot_synchro_minutes`, le service demande les identifiants des dernières
parties du compte Riot configuré, télécharge celles qu'il n'a pas encore vues (match +
chronologie pour LoL) et les importe comme n'importe quel fichier : archivage, fiche,
mesures, débrief. Le rang (league-v4) est joint à chaque partie LoL.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from postgame.config import Config
from postgame.db import Base
from postgame.games.riot.client import ClientRiot, ErreurRiot
from postgame.importation import importer

journal = logging.getLogger(__name__)


def ecrire_atomique(chemin: Path, texte: str) -> None:
    """Écrit dans un fichier temporaire puis le renomme : jamais de fichier à moitié écrit
    (coupure de courant pendant l'écriture)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(chemin.name + ".tmp")
    temporaire.write_text(texte, encoding="utf-8")
    os.replace(temporaire, chemin)


def client_configure(cfg: Config) -> ClientRiot:
    return ClientRiot(
        cfg.secret("riot", "cle", "RIOT_API_KEY"),
        cfg.riot_plateforme,
        cfg.riot_region,
        cfg.dossier_donnees / "riot" / "cache",
    )


class CollecteurRiot:
    def __init__(self, base: Base, cfg: Config, client: ClientRiot | None = None, garde=None):
        self.base, self.cfg = base, cfg
        self.garde = garde  # PERF-01 : pas de synchronisation pendant une partie
        self._client = client
        self.dossier = cfg.dossier_donnees / "riot"
        self.etat: dict[str, Any] = {"derniere_synchro": None, "erreur": None, "importees": 0}
        self._arret = threading.Event()
        self._fil: threading.Thread | None = None
        self._verrou = threading.Lock()

    @property
    def client(self) -> ClientRiot:
        if self._client is None:
            self._client = client_configure(self.cfg)
        return self._client

    # --- Mémoire locale ---------------------------------------------------------------------

    def _lire(self, nom: str, defaut: Any) -> Any:
        fichier = self.dossier / nom
        if not fichier.exists():
            return defaut
        try:
            return json.loads(fichier.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            journal.warning("fichier Riot abîmé, ignoré : %s", fichier)
            return defaut

    def _ecrire(self, nom: str, valeur: Any) -> None:
        ecrire_atomique(self.dossier / nom, json.dumps(valeur, ensure_ascii=False))

    def compte(self) -> dict[str, Any]:
        """Compte Riot (puuid) du Riot ID configuré, mis en cache."""
        comptes = self._lire("comptes.json", {})
        if self.cfg.riot_id not in comptes:
            comptes[self.cfg.riot_id] = self.client.compte(self.cfg.riot_id)
            self._ecrire("comptes.json", comptes)
        return comptes[self.cfg.riot_id]

    # --- Synchronisation ------------------------------------------------------------------

    def synchroniser(self, nombre: int = 20) -> dict[str, Any]:
        """Une seule synchronisation à la fois (fil de fond et bouton de l'interface)."""
        if not self._verrou.acquire(blocking=False):
            return {"lol": 0, "tft": 0, "erreurs": ["synchronisation déjà en cours"]}
        try:
            return self._synchroniser(nombre)
        finally:
            self._verrou.release()

    def _synchroniser(self, nombre: int) -> dict[str, Any]:
        if not self.cfg.riot_id:
            raise ErreurRiot("Riot ID absent : [riot] riot_id dans postgame.toml")
        puuid = self.compte()["puuid"]
        vus: dict[str, list[str]] = self._lire("vus.json", {"lol": [], "tft": []})
        bilan = {"lol": 0, "tft": 0, "erreurs": []}
        rang = None
        try:
            rang = [
                e
                for e in self.client.rangs_lol(puuid)
                if e.get("queueType") in ("RANKED_SOLO_5x5", "RANKED_FLEX_SR")
            ]
        except ErreurRiot as exc:
            bilan["erreurs"].append(f"rang : {exc}")

        for jeu, lister in (("lol", self.client.parties_lol), ("tft", self.client.parties_tft)):
            try:
                identifiants = lister(puuid, nombre)
            except ErreurRiot as exc:
                bilan["erreurs"].append(f"{jeu} : {exc}")
                continue
            for match_id in reversed(identifiants):  # du plus ancien au plus récent
                if match_id in vus[jeu]:
                    continue
                try:
                    chemin = self._telecharger(jeu, match_id, puuid, rang)
                    resultat = importer(chemin, self.base, self.cfg)
                    if resultat.statut == "erreur":
                        bilan["erreurs"].append(f"{match_id} : {resultat.message}")
                    else:
                        bilan[jeu] += resultat.statut == "importe"
                    vus[jeu].append(match_id)
                    self._ecrire("vus.json", vus)
                except ErreurRiot as exc:
                    bilan["erreurs"].append(f"{match_id} : {exc}")
                except Exception as exc:  # une partie à problème ne bloque pas les suivantes
                    journal.exception("partie Riot %s", match_id)
                    bilan["erreurs"].append(f"{match_id} : {exc}")
        self.etat.update(
            derniere_synchro=_maintenant(),
            erreur=None,
            importees=self.etat["importees"] + bilan["lol"] + bilan["tft"],
        )
        return bilan

    def _telecharger(self, jeu: str, match_id: str, puuid: str, rang: Any) -> Path:
        if jeu == "lol":
            contenu = {
                "format": 1,
                "puuid": puuid,
                "match": self.client.partie_lol(match_id),
                "timeline": self.client.chronologie_lol(match_id),
                "rang": rang,
            }
        else:
            contenu = {"format": 1, "puuid": puuid, "match": self.client.partie_tft(match_id)}
        chemin = self.dossier / "entrants" / f"{match_id}.{jeu}"
        ecrire_atomique(chemin, json.dumps(contenu))
        return chemin

    # --- Tâche de fond ---------------------------------------------------------------------

    def demarrer(self) -> None:
        if not self.cfg.riot_id or self._fil and self._fil.is_alive():
            return
        self._arret.clear()
        self._fil = threading.Thread(target=self._boucle, name="collecte-riot", daemon=True)
        self._fil.start()

    def arreter(self) -> None:
        self._arret.set()

    def _boucle(self) -> None:
        while not self._arret.is_set():
            if self.garde is not None and self.garde.doit_attendre("leger"):
                self._arret.wait(60)
                continue
            try:
                bilan = self.synchroniser()
                journal.info(
                    "Riot : %s partie(s) LoL, %s TFT importée(s)", bilan["lol"], bilan["tft"]
                )
            except Exception as exc:  # clé expirée, réseau… : on réessaiera plus tard
                self.etat["erreur"] = str(exc)
                journal.warning("collecte Riot en échec : %s", exc)
            self._arret.wait(self.cfg.riot_synchro_minutes * 60)


def _maintenant() -> str:
    from postgame.db import maintenant

    return maintenant()
