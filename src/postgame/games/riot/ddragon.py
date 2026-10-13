"""Data Dragon (données statiques officielles de Riot) : champions par version du jeu.

Donne, pour un patch (« 15.20 »), le nom français et les classes de chaque champion
(« Mage », « Marksman », « Support »…). Les fichiers sont mis en cache dans data/ddragon :
une version n'est téléchargée qu'une fois.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

URL = "https://ddragon.leagueoflegends.com"
CLASSES_FR = {
    "Assassin": "assassin",
    "Fighter": "combattant",
    "Mage": "mage",
    "Marksman": "tireur",
    "Support": "support",
    "Tank": "tank",
}


class DataDragon:
    def __init__(self, dossier_cache: Path, client: httpx.Client | None = None):
        self.dossier = dossier_cache
        self.client = client or httpx.Client(timeout=20)

    def _json(self, chemin: str, fichier: str) -> Any:
        cache = self.dossier / fichier
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        r = self.client.get(f"{URL}{chemin}")
        r.raise_for_status()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(r.text, encoding="utf-8")
        return r.json()

    def version_pour(self, patch: str) -> str | None:
        """Version Data Dragon d'un patch (« 15.20 » → « 15.20.1 »)."""
        versions = self._json("/api/versions.json", "versions.json")
        return next((v for v in versions if v == patch or v.startswith(patch + ".")), None)

    def champions(self, patch: str) -> dict[str, dict[str, Any]]:
        """championName (identifiant Riot, ex. « MonkeyKing ») → {nom, classes}."""
        version = self.version_pour(patch)
        if version is None:
            return {}
        donnees = self._json(f"/cdn/{version}/data/fr_FR/champion.json", f"champion_{version}.json")
        return {
            cle: {
                "nom": c.get("name", cle),
                "classes": [CLASSES_FR.get(tag, tag.lower()) for tag in c.get("tags", [])],
            }
            for cle, c in donnees.get("data", {}).items()
        }

    def noms_tft(self, patch: str | None = None) -> dict[str, str]:
        """Identifiant TFT (unité, trait, objet, augment) → nom officiel français, pour le
        patch donné (ou le plus récent). Couvre l'ancien format (« TFT15_Ahri ») comme celui
        du set 18 sous Unreal Engine (« DA_CrimsonRaptor18 »)."""
        versions = self._json("/api/versions.json", "versions.json")
        version = (self.version_pour(patch) if patch else None) or versions[0]
        noms: dict[str, str] = {}
        for type_ in ("tft-champion", "tft-trait", "tft-item", "tft-augments"):
            donnees = self._json(
                f"/cdn/{version}/data/fr_FR/{type_}.json", f"{type_}_{version}.json"
            )
            for cle, v in donnees.get("data", {}).items():
                identifiant = v.get("id") or cle
                if v.get("name"):
                    noms.setdefault(str(identifiant), str(v["name"]))
        return noms

    def classes(self, patch: str) -> dict[str, list[str]]:
        try:
            return {cle: c["classes"] for cle, c in self.champions(patch).items()}
        except (httpx.HTTPError, ValueError, OSError):
            return {}  # hors ligne : les mesures n'auront simplement pas de classe
