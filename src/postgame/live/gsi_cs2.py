"""Réception du flux Game State Integration de CS2 (CS-LIVE-01).

CS2 envoie en HTTP POST, à chaque changement (et au moins toutes les `heartbeat` s), un JSON
décrit dans la config gamestate_integration_postgame.cfg. On garde le dernier état, on en
tire un résumé lisible pour le téléphone, et on journalise le flux brut (risque du cahier
des charges : vérifier ce que GSI expose vraiment à un joueur).

Fonction officielle de Valve, en lecture seule : rien n'est envoyé au jeu.
"""

from __future__ import annotations

import json
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from postgame.live.economie_cs2 import recommander

CONFIG_GSI = """"Postgame"
{{
    "uri"       "{uri}"
    "timeout"   "1.0"
    "buffer"    "0.1"
    "throttle"  "0.1"
    "heartbeat" "10.0"
    "auth"
    {{
        "token" "{jeton}"
    }}
    "data"
    {{
        "provider"            "1"
        "map"                 "1"
        "round"               "1"
        "player_id"           "1"
        "player_state"        "1"
        "player_weapons"      "1"
        "player_match_stats"  "1"
        "map_round_wins"      "1"
        "allplayers_id"       "1"
        "allplayers_state"    "1"
        "allplayers_match_stats" "1"
        "phase_countdowns"    "1"
        "bomb"                "1"
    }}
}}
"""


def jeton_gsi(dossier_donnees: Path) -> str:
    """Jeton partagé avec la config du jeu, créé au premier besoin (data/ est ignoré par git)."""
    fichier = dossier_donnees / "gsi_jeton.txt"
    if fichier.exists():
        return fichier.read_text(encoding="utf-8").strip()
    fichier.parent.mkdir(parents=True, exist_ok=True)
    jeton = secrets.token_hex(16)
    fichier.write_text(jeton, encoding="utf-8")
    return jeton


def texte_config(uri: str, jeton: str) -> str:
    """Contenu de gamestate_integration_postgame.cfg (ASCII, sans BOM : sinon CS2 l'ignore)."""
    return CONFIG_GSI.format(uri=uri, jeton=jeton)


# Occasionnel (casual) : autre économie, pas de conseil.
MODES_ECONOMIE = (None, "competitive", "premier", "scrimcomp2v2")


def _int(valeur: Any, defaut: int = 0) -> int:
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return defaut


def resumer(etat: dict[str, Any]) -> dict[str, Any]:
    """Ce que le second écran affiche, à partir du dernier état GSI."""
    fournisseur = etat.get("provider", {})
    carte = etat.get("map", {})
    rnd = etat.get("round", {})
    joueur = etat.get("player", {})
    moi = str(fournisseur.get("steamid", ""))
    c_est_moi = str(joueur.get("steamid", "")) == moi if moi else True
    state = joueur.get("state", {})
    stats = joueur.get("match_stats", {})
    camp = str(joueur.get("team", "")).upper()
    equipes = {"CT": carte.get("team_ct", {}), "T": carte.get("team_t", {})}
    adverse = "T" if camp == "CT" else "CT"
    score_nous = _int(equipes.get(camp, {}).get("score"))
    score_eux = _int(equipes.get(adverse, {}).get("score"))
    # map.round = nombre de rounds joués ; pendant le freeze, c'est le round à venir.
    numero = _int(carte.get("round")) + 1
    phase_round = rnd.get("phase", "")

    resume: dict[str, Any] = {
        "actif": bool(carte),
        "recu_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "carte": carte.get("name"),
        "mode": carte.get("mode"),
        "phase_match": carte.get("phase"),
        "phase_round": phase_round,
        "round": numero,
        "camp": camp or None,
        "score": {"nous": score_nous, "eux": score_eux},
        "bombe": rnd.get("bomb"),
        "observe": None if c_est_moi else joueur.get("name"),
        "joueur": None,
        "recommandation": None,
        "coequipiers": None,
    }
    if c_est_moi and state:
        armes = [
            {
                "nom": str(a.get("name", "")).removeprefix("weapon_"),
                "type": a.get("type"),
                "active": a.get("state") == "active",
                "munitions": a.get("ammo_clip"),
                "reserve": a.get("ammo_reserve"),
            }
            for a in joueur.get("weapons", {}).values()
        ]
        resume["joueur"] = {
            "nom": joueur.get("name"),
            "vie": _int(state.get("health")),
            "armure": _int(state.get("armor")),
            "casque": bool(state.get("helmet")),
            "argent": _int(state.get("money")),
            "valeur_equipement": _int(state.get("equip_value")),
            "kills_round": _int(state.get("round_kills")),
            "hs_round": _int(state.get("round_killhs")),
            "aveugle": _int(state.get("flashed")),
            "kills": _int(stats.get("kills")),
            "assistances": _int(stats.get("assists")),
            "morts": _int(stats.get("deaths")),
            "mvps": _int(stats.get("mvps")),
            "armes": armes,
        }
        if camp in ("CT", "T") and carte.get("mode") in MODES_ECONOMIE:
            defaites = _int(equipes[camp].get("consecutive_round_losses"))
            reco = recommander(
                _int(state.get("money")),
                camp,
                numero,
                defaites,
                score_nous,
                score_eux,
                carte.get("mode"),
            )
            resume["joueur"]["argent_si_defaite"] = reco.argent_round_suivant_si_defaite
            # Le conseil d'achat ne vaut que pendant la phase d'achat du round à venir.
            if phase_round in ("freezetime", ""):
                resume["recommandation"] = reco.en_dict()
    # Argent des coéquipiers : seulement si GSI le fournit (spectateur, GOTV).
    tous = etat.get("allplayers")
    if isinstance(tous, dict) and camp:
        resume["coequipiers"] = [
            {
                "nom": j.get("name"),
                "argent": _int(j.get("state", {}).get("money")),
                "vie": _int(j.get("state", {}).get("health")),
            }
            for sid, j in tous.items()
            if str(j.get("team", "")).upper() == camp and sid != moi
        ]
    return resume


class RecepteurGSI:
    """Garde le dernier état, journalise le flux brut et prévient les abonnés."""

    def __init__(self, dossier_donnees: Path, jeton: str, journaliser: bool = True):
        self.dossier = dossier_donnees / "gsi"
        self.jeton = jeton
        self.journaliser = journaliser
        self.etat: dict[str, Any] = {}
        self.resume: dict[str, Any] = {"actif": False}
        self.dernier_recu: float | None = None

    def recevoir(self, charge: dict[str, Any]) -> bool:
        """Intègre un message ; False si le jeton ne correspond pas (message ignoré)."""
        jeton = charge.get("auth", {}).get("token")
        if not secrets.compare_digest(str(jeton or ""), self.jeton):
            return False
        sans_auth = {k: v for k, v in charge.items() if k != "auth"}
        if self.journaliser:
            self.dossier.mkdir(parents=True, exist_ok=True)
            fichier = self.dossier / f"journal_{datetime.now():%Y%m%d}.jsonl"
            with fichier.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.time(), **sans_auth}, ensure_ascii=False) + "\n")
        # Chaque message GSI est un état complet des sections demandées : on remplace.
        self.etat = {k: v for k, v in sans_auth.items() if k not in ("previously", "added")}
        self.resume = resumer(self.etat)
        self.dernier_recu = time.time()
        return True
