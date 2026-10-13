"""Comptes de Mathieu (CPT-01) : Steam / CS2, Riot (LoL, TFT), FACEIT.

- Les identifiants viennent de postgame.toml ; ceux que Postgame découvre seul (SteamID64
  retrouvé grâce au pseudo dans une démo, identifiants FACEIT et Riot) sont gardés dans
  data/comptes.json et réutilisés automatiquement.
- La progression des classements est tirée des parties elles-mêmes : CS Rating Premier,
  rang compétitif par carte, rang LoL au moment de chaque partie.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from postgame.config import Config
from postgame.db import Base


def fichier_comptes(dossier_donnees: Path) -> Path:
    return dossier_donnees / "comptes.json"


def lire(dossier_donnees: Path) -> dict[str, Any]:
    f = fichier_comptes(dossier_donnees)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def memoriser(dossier_donnees: Path, **valeurs: Any) -> None:
    donnees = {**lire(dossier_donnees), **{k: v for k, v in valeurs.items() if v}}
    f = fichier_comptes(dossier_donnees)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")


def appliquer(cfg: Config) -> None:
    """Complète la configuration avec ce que Postgame a appris (SteamID64…)."""
    appris = lire(cfg.dossier_donnees)
    if not cfg.steamid and appris.get("steamid"):
        cfg.steamid = str(appris["steamid"])


def apprendre_de_la_partie(cfg: Config, details: dict[str, Any]) -> None:
    """Après une démo CS2 : si Mathieu y a été reconnu par son pseudo, retenir son SteamID64."""
    steamid = details.get("steamid_joueur")
    if steamid and not cfg.steamid:
        memoriser(cfg.dossier_donnees, steamid=str(steamid))
        cfg.steamid = str(steamid)


def classements(base: Base) -> dict[str, list[dict[str, Any]]]:
    """Séries chronologiques : CS Rating Premier, rang compétitif (par carte), rang LoL."""
    series: dict[str, list[dict[str, Any]]] = {"premier": [], "competitif": [], "lol": []}
    with base.transaction() as cx:
        lignes = cx.execute(
            "SELECT id, jeu, date_partie, mode, carte, details FROM parties "
            "WHERE jeu IN ('cs2', 'lol') ORDER BY date_partie"
        ).fetchall()
    for lg in lignes:
        details = json.loads(lg["details"])
        if lg["jeu"] == "cs2" and details.get("classement"):
            cle = "premier" if lg["mode"] == "premier" else "competitif"
            if lg["mode"] in ("premier", "competitif"):
                series[cle].append(
                    {
                        "partie_id": lg["id"],
                        "date_partie": lg["date_partie"],
                        "carte": lg["carte"],
                        "valeur": details["classement"],
                        "contexte": {"carte": lg["carte"]} if cle == "competitif" else {},
                    }
                )
        elif lg["jeu"] == "lol" and details.get("rang"):
            solo = next(
                (r for r in details["rang"] if r.get("queueType") == "RANKED_SOLO_5x5"), None
            )
            if solo:
                series["lol"].append(
                    {
                        "partie_id": lg["id"],
                        "date_partie": lg["date_partie"],
                        "carte": lg["carte"],
                        "valeur": solo.get("leaguePoints"),
                        "contexte": {"palier": f"{solo.get('tier')} {solo.get('rank')}"},
                    }
                )
    return series


def resume(cfg: Config, base: Base) -> dict[str, Any]:
    appris = lire(cfg.dossier_donnees)
    return {
        "steam": {
            "steamid": cfg.steamid or None,
            "pseudos": cfg.noms_joueur,
            "appris": bool(appris.get("steamid")) and cfg.steamid == appris.get("steamid"),
            "profil": f"https://steamcommunity.com/profiles/{cfg.steamid}" if cfg.steamid else None,
            "codes_partage": bool(cfg.steam_code_connu),
        },
        "riot": {
            "riot_id": cfg.riot_id or None,
            "plateforme": cfg.riot_plateforme,
            "cle_presente": bool(cfg.secret("riot", "cle", "RIOT_API_KEY")),
        },
        "faceit": {
            "pseudo": cfg.faceit_pseudo or None,
            "cle_presente": bool(cfg.secret("faceit", "cle", "FACEIT_API_KEY")),
            "telechargement": bool(
                cfg.secret("faceit", "jeton_telechargement", "FACEIT_DOWNLOAD_TOKEN")
            ),
        },
        "classements": classements(base),
    }
