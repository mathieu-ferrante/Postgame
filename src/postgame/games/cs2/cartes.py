"""Cartes de CS2 : pool actif (Premier / compétitif classé) tenu à jour automatiquement.

Point de départ vérifié : notes de mise à jour officielles du 9 juillet 2026 (début de la
saison 5 de Premier) — « Added Cache to the Active Duty Map Pool », « Removed Overpass from
the Active Duty Map Pool ». Ensuite, le service relit les actualités officielles de CS2 sur
Steam (appid 730) et applique chaque ajout / retrait du pool qu'elles annoncent : la liste
suit le jeu sans modifier le code.

Hors pool actif, les cartes réellement jouées par Mathieu (vues dans ses démos) restent
disponibles partout dans l'interface.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

journal = logging.getLogger(__name__)

URL_ACTUALITES = (
    "https://store.steampowered.com/events/ajaxgetadjacentpartnerevents/"
    "?appid=730&count_before=0&count_after=100&lang_list=0"
)

BASE = {
    "date": "2026-07-09",
    "source": "Notes de mise à jour officielles de CS2 du 9 juillet 2026 (Premier, saison 5)",
    "pool": [
        "de_ancient",
        "de_anubis",
        "de_cache",
        "de_dust2",
        "de_inferno",
        "de_mirage",
        "de_nuke",
    ],
    # Annoncées le même jour, hors pool actif (codes internes à confirmer par les démos).
    "autres_modes": {
        "competitif_occasionnel_dm": [
            "Boulder",
            "Fachwerk",
            "Shelter",
            "Overpass",
            "Train",
            "Vertigo",
        ],
        "wingman": ["Debris", "El Dorado"],
    },
}

AJOUT = re.compile(r"Added ([A-Z][\w' ]+?) to the Active Duty Map Pool", re.IGNORECASE)
RETRAIT = re.compile(r"Removed ([A-Z][\w' ]+?) from the Active Duty Map Pool", re.IGNORECASE)
NOMS_SPECIAUX = {"dust ii": "de_dust2", "dust 2": "de_dust2", "dust2": "de_dust2"}


def code_carte(nom: str) -> str:
    """« Dust II » → « de_dust2 », « Cache » → « de_cache »."""
    cle = nom.strip().lower()
    if cle in NOMS_SPECIAUX:
        return NOMS_SPECIAUX[cle]
    if re.match(r"^(de|cs|ar)_", cle):
        return cle
    return "de_" + re.sub(r"[^a-z0-9]+", "", cle)


def nom_affiche(code: str) -> str:
    nom = re.sub(r"^(de|cs|ar)_", "", code)
    return {"dust2": "Dust II"}.get(nom, nom.replace("_", " ").title())


def appliquer_actualites(etat: dict[str, Any], evenements: list[dict[str, Any]]) -> dict[str, Any]:
    """Applique, dans l'ordre chronologique, les changements de pool publiés après la date
    de l'état. Chaque évènement : {date: « AAAA-MM-JJ », titre, texte}."""
    pool = list(etat["pool"])
    date, source = etat["date"], etat["source"]
    for ev in sorted(evenements, key=lambda e: e["date"]):
        if ev["date"] <= etat["date"]:
            continue
        ajouts = [code_carte(n) for n in AJOUT.findall(ev["texte"])]
        retraits = [code_carte(n) for n in RETRAIT.findall(ev["texte"])]
        if not ajouts and not retraits:
            continue
        pool = sorted({c for c in pool if c not in retraits} | set(ajouts))
        date, source = ev["date"], f"Notes de mise à jour officielles de CS2 du {ev['date']}"
    return {**etat, "pool": pool, "date": date, "source": source}


def lire_actualites(client: httpx.Client | None = None) -> list[dict[str, Any]]:
    client = client or httpx.Client(timeout=20)
    r = client.get(URL_ACTUALITES)
    r.raise_for_status()
    sortie = []
    for e in r.json().get("events", []):
        texte = re.sub(r"\[[^\]]+\]", " ", e.get("announcement_body", {}).get("body", ""))
        horodatage = e.get("rtime32_start_time") or 0
        sortie.append(
            {
                "date": datetime.fromtimestamp(horodatage, UTC).date().isoformat(),
                "titre": e.get("event_name", ""),
                "texte": texte,
            }
        )
    return sortie


def chemin_etat(dossier_donnees: Path) -> Path:
    return dossier_donnees / "cs2_cartes.json"


def etat_cartes(dossier_donnees: Path) -> dict[str, Any]:
    fichier = chemin_etat(dossier_donnees)
    if fichier.exists():
        return json.loads(fichier.read_text(encoding="utf-8"))
    return dict(BASE)


def actualiser(dossier_donnees: Path, client: httpx.Client | None = None) -> dict[str, Any]:
    """Relit les actualités officielles et met à jour le pool ; garde l'état connu en cas
    d'échec réseau."""
    etat = etat_cartes(dossier_donnees)
    try:
        etat = appliquer_actualites(etat, lire_actualites(client))
        etat["verifie_le"] = datetime.now(UTC).isoformat(timespec="seconds")
    except (httpx.HTTPError, ValueError) as exc:
        journal.warning("actualités CS2 inaccessibles : %s", exc)
        etat["erreur"] = str(exc)
        return etat
    fichier = chemin_etat(dossier_donnees)
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    return etat
