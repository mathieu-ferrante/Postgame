"""Envoie des messages Game State Integration au service, comme le ferait CS2.

- sans fichier : une petite séquence SIMULÉE (achat, round, kill) — données de substitution ;
- avec un journal enregistré (data/gsi/journal_AAAAMMJJ.jsonl) : le rejoue au rythme réel.

Usage : .venv\\Scripts\\python scripts\\simuler_gsi.py [--config postgame.toml] [journal.jsonl]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx

from postgame.config import charger_config
from postgame.live.gsi_cs2 import jeton_gsi


def sequence_simulee() -> list[dict]:
    base = {
        "provider": {"name": "Counter-Strike 2", "appid": 730, "steamid": "76561190000000000"},
        "map": {
            "mode": "competitive",
            "name": "de_mirage",
            "phase": "live",
            "round": 5,
            "team_ct": {"score": 3, "consecutive_round_losses": 0},
            "team_t": {"score": 2, "consecutive_round_losses": 2},
        },
        "round": {"phase": "freezetime"},
        "player": {
            "steamid": "76561190000000000",
            "name": "Mathieu (simulé)",
            "team": "T",
            "state": {
                "health": 100,
                "armor": 0,
                "helmet": False,
                "money": 3150,
                "round_kills": 0,
                "round_killhs": 0,
                "equip_value": 200,
            },
            "weapons": {
                "weapon_1": {
                    "name": "weapon_glock",
                    "type": "Pistol",
                    "ammo_clip": 20,
                    "ammo_reserve": 120,
                    "state": "active",
                }
            },
            "match_stats": {"kills": 6, "assists": 2, "deaths": 4, "mvps": 1},
        },
    }
    etapes = [base]
    achat = json.loads(json.dumps(base))
    achat["player"]["state"].update(money=350, armor=100, equip_value=2800)
    achat["player"]["weapons"]["weapon_2"] = {
        "name": "weapon_galilar",
        "type": "Rifle",
        "ammo_clip": 35,
        "ammo_reserve": 90,
        "state": "active",
    }
    achat["player"]["weapons"]["weapon_1"]["state"] = "holstered"
    etapes.append(achat)
    live = json.loads(json.dumps(achat))
    live["round"]["phase"] = "live"
    etapes.append(live)
    kill = json.loads(json.dumps(live))
    kill["player"]["state"].update(round_kills=1, health=64)
    kill["player"]["match_stats"]["kills"] = 7
    etapes.append(kill)
    return etapes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("journal", nargs="?", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--pause", type=float, default=1.5, help="secondes entre deux messages")
    args = parser.parse_args()
    cfg = charger_config(args.config)
    jeton = jeton_gsi(cfg.dossier_donnees)
    url = f"http://127.0.0.1:{cfg.port}/api/cs2/gsi"
    if args.journal:
        contenu = args.journal.read_text(encoding="utf-8")
        lignes = [json.loads(texte) for texte in contenu.splitlines()]
    else:
        lignes = sequence_simulee()
    precedent = None
    for ligne in lignes:
        t = ligne.pop("t", None)
        if precedent is not None and t is not None:
            time.sleep(max(0.0, t - precedent))
        elif precedent is not None or t is None:
            time.sleep(args.pause)
        precedent = t
        r = httpx.post(url, json={**ligne, "auth": {"token": jeton}}, timeout=5)
        print(r.status_code, ligne.get("round", {}).get("phase"))


if __name__ == "__main__":
    main()
