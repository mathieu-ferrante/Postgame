"""Extraction des données de match utiles aux analyses CS2, dans un schéma stable.

Les analyseurs ne voient jamais demoparser2 : ils travaillent sur `DonneesMatch`, dont les
colonnes sont décrites ci-dessous. Les tests fabriquent des `DonneesMatch` à la main.

ticks   : tick, steamid (str), nom, equipe, x, y, z, vx, vy, pitch, yaw, vivant (bool),
          accroupi (bool), arme (code), vu_par_moi (bool : l'adversaire est « repéré » par
          le joueur suivi), punch_pitch, punch_yaw
tirs    : tick, steamid, arme                                  (weapon_fire)
degats  : tick, attaquant, victime, arme, degats, zone         (player_hurt ; zone 'tete'…)
morts   : tick, attaquant, victime, arme, headshot (bool)      (player_death)
rounds  : numero, debut, fin                                   (fin du freeze → fin du round)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from postgame.games.base import ErreurLecture
from postgame.games.cs2.armes import normaliser

TICKS_PAR_SECONDE = 64

PROPS_TICKS = [
    "X",
    "Y",
    "Z",
    "velocity_X",
    "velocity_Y",
    "pitch",
    "yaw",
    "team_num",
    "is_alive",
    "ducked",
    "active_weapon_name",
    "approximate_spotted_by",
    "aim_punch_angle",
]

COLONNES_TICKS = [
    "tick",
    "steamid",
    "nom",
    "equipe",
    "x",
    "y",
    "z",
    "vx",
    "vy",
    "pitch",
    "yaw",
    "vivant",
    "accroupi",
    "arme",
    "vu_par_moi",
    "punch_pitch",
    "punch_yaw",
]

ZONES = {
    1: "tete",
    2: "torse",
    3: "ventre",
    4: "bras_g",
    5: "bras_d",
    6: "jambe_g",
    7: "jambe_d",
    8: "cou",
    0: "generique",
}
ZONES_TEXTE = {
    "head": "tete",
    "chest": "torse",
    "stomach": "ventre",
    "left_arm": "bras_g",
    "right_arm": "bras_d",
    "left_leg": "jambe_g",
    "right_leg": "jambe_d",
    "neck": "cou",
    "generic": "generique",
}


@dataclass
class DonneesMatch:
    moi: str
    ticks: pd.DataFrame
    tirs: pd.DataFrame
    degats: pd.DataFrame
    morts: pd.DataFrame
    rounds: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["numero", "debut", "fin"])
    )
    carte: str = ""

    def numero_round(self, tick: int) -> int | None:
        if not len(self.rounds):
            return None
        avant = self.rounds[self.rounds["debut"] <= tick]
        return int(avant["numero"].iloc[-1]) if len(avant) else None

    def mes_ticks(self) -> pd.DataFrame:
        return self.ticks[self.ticks["steamid"] == self.moi]


def _zone(valeur: Any) -> str:
    if isinstance(valeur, str):
        if valeur.isdigit():
            return ZONES.get(int(valeur), valeur)
        return ZONES_TEXTE.get(valeur.lower(), valeur.lower())
    try:
        return ZONES.get(int(valeur), str(valeur))
    except (TypeError, ValueError):
        return "generique"


def _composante(valeur: Any, i: int) -> float:
    """Composante i d'un angle vectoriel renvoyé par demoparser2 (liste, tableau ou None)."""
    if valeur is None:
        return 0.0
    try:
        return float(valeur[i])
    except (TypeError, IndexError, ValueError):
        return 0.0


def _steamid(serie: pd.Series) -> pd.Series:
    return serie.astype("string").fillna("").str.replace(r"\.0$", "", regex=True)


def identifier_moi(joueurs: pd.DataFrame, steamid: str, client: str) -> str:
    """SteamID du joueur suivi : celui de la config, sinon celui dont le nom est le client
    qui a enregistré la démo."""
    if steamid:
        return str(steamid)
    if client and len(joueurs):
        lignes = joueurs[joueurs["nom"] == client]
        if len(lignes):
            return str(lignes["steamid"].iloc[0])
    raise ErreurLecture("joueur suivi introuvable : renseigner [joueur] steamid dans postgame.toml")


def normaliser_ticks(brut: pd.DataFrame, moi: str) -> pd.DataFrame:
    """Passe du DataFrame demoparser2 au schéma `ticks`."""
    df = pd.DataFrame(
        {
            "tick": brut["tick"].astype("int64"),
            "steamid": _steamid(brut["steamid"]),
            "nom": brut.get("name", pd.Series("", index=brut.index)).astype(str),
            "equipe": brut["team_num"].fillna(0).astype("int64"),
            "x": brut["X"].astype(float),
            "y": brut["Y"].astype(float),
            "z": brut["Z"].astype(float),
            "vx": brut["velocity_X"].astype(float).fillna(0.0),
            "vy": brut["velocity_Y"].astype(float).fillna(0.0),
            "pitch": brut["pitch"].astype(float),
            "yaw": brut["yaw"].astype(float),
            "vivant": brut["is_alive"].fillna(False).astype(bool),
            "accroupi": brut["ducked"].fillna(False).astype(bool),
            "arme": brut["active_weapon_name"].map(normaliser),
        }
    )
    moi_int = int(moi) if moi.isdigit() else None
    df["vu_par_moi"] = [
        bool(
            v is not None
            and not (isinstance(v, float) and np.isnan(v))
            and any(str(s) == moi or s == moi_int for s in v)
        )
        for v in brut["approximate_spotted_by"]
    ]
    df["punch_pitch"] = [_composante(v, 0) for v in brut["aim_punch_angle"]]
    df["punch_yaw"] = [_composante(v, 1) for v in brut["aim_punch_angle"]]
    return df.sort_values(["tick", "steamid"]).reset_index(drop=True)


def extraire_match(chemin: Path, steamid: str) -> DonneesMatch:
    try:
        from demoparser2 import DemoParser

        parser = DemoParser(str(chemin))
        entete = parser.parse_header()
        infos = parser.parse_player_info()
        joueurs = pd.DataFrame(
            {"steamid": _steamid(infos["steamid"]), "nom": infos["name"].astype(str)}
        )
        moi = identifier_moi(joueurs, steamid, str(entete.get("client_name", "")))
        brut = parser.parse_ticks(PROPS_TICKS)
        presents = set(parser.list_game_events())
        voulus = ["weapon_fire", "player_hurt", "player_death", "round_freeze_end", "round_end"]
        voulus = [e for e in voulus if e in presents]
        evts = dict(parser.parse_events(voulus)) if voulus else {}
    except ErreurLecture:
        raise
    except Exception as exc:
        raise ErreurLecture(f"extraction impossible : {exc}") from exc

    vide = pd.DataFrame(columns=["tick"])
    f = evts.get("weapon_fire", vide)
    tirs = pd.DataFrame(
        {
            "tick": f["tick"].astype("int64") if len(f) else [],
            "steamid": _steamid(f["user_steamid"]) if len(f) else [],
            "arme": f["weapon"].map(normaliser) if len(f) else [],
        }
    )
    h = evts.get("player_hurt", vide)
    degats = pd.DataFrame(
        {
            "tick": h["tick"].astype("int64") if len(h) else [],
            "attaquant": _steamid(h["attacker_steamid"]) if len(h) else [],
            "victime": _steamid(h["user_steamid"]) if len(h) else [],
            "arme": h["weapon"].map(normaliser) if len(h) else [],
            "degats": h["dmg_health"].astype(float) if len(h) else [],
            "zone": h["hitgroup"].map(_zone) if len(h) else [],
        }
    )
    d = evts.get("player_death", vide)
    morts = pd.DataFrame(
        {
            "tick": d["tick"].astype("int64") if len(d) else [],
            "attaquant": _steamid(d["attacker_steamid"]) if len(d) else [],
            "victime": _steamid(d["user_steamid"]) if len(d) else [],
            "arme": d["weapon"].map(normaliser) if len(d) else [],
            "headshot": d["headshot"].fillna(False).astype(bool) if len(d) else [],
        }
    )
    debuts = sorted(evts.get("round_freeze_end", vide)["tick"].astype(int).tolist())
    fins = sorted(evts.get("round_end", vide)["tick"].astype(int).tolist())
    rounds = construire_rounds(debuts, fins)
    return DonneesMatch(
        moi=moi,
        ticks=normaliser_ticks(brut, moi),
        tirs=tirs,
        degats=degats,
        morts=morts,
        rounds=rounds,
        carte=str(entete.get("map_name", "")),
    )


def construire_rounds(debuts: list[int], fins: list[int]) -> pd.DataFrame:
    """Associe chaque fin de freeze à la fin de round suivante. Un round sans fin connue
    (deathmatch, démo coupée) court jusqu'au début suivant, ou à l'infini."""
    lignes = []
    for i, debut in enumerate(debuts):
        suivant = debuts[i + 1] if i + 1 < len(debuts) else None
        fin = next((f for f in fins if f > debut and (suivant is None or f <= suivant)), None)
        if fin is None:
            fin = suivant if suivant is not None else np.iinfo(np.int64).max
        lignes.append({"numero": i + 1, "debut": debut, "fin": fin})
    return pd.DataFrame(lignes, columns=["numero", "debut", "fin"])
