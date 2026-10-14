"""Extrait d'une démo pro : tout ce qui sert à apprendre, en quelques Mo au lieu de centaines.

Une démo pro pèse 150 à 500 Mo par carte. Pour apprendre les stuffs et les placements, on
en tire ici, une fois pour toutes, tout ce qui est réellement enregistré dans la démo :

- chaque grenade lancée : lanceur, technique, vrai lâcher, état complet sur la seconde qui
  précède (position, regard, vitesse, touches), trajectoire réelle en vol, éclatement,
  timing dans le round, pose de bombe qui suit, effet (joueurs aveuglés, dégâts) ;
- les positions de tous les joueurs 4 fois par seconde pendant les rounds (placements,
  rotations, armes en main) ;
- les éliminations et les dégâts (positions, arme, tête, à travers la smoke, aveuglé…) ;
- les rounds, la bombe et l'économie ;
- les observations et mesures déjà utilisées par Postgame (catalogue, cibles par arme).

Rien n'est calculé ni « reconstitué » : ce sont les valeurs de la démo, échantillonnées.
Le fichier (JSON compressé zstd, extension .pgpro) s'importe sur le PC de jeu sans la démo ;
la démo complète reste nécessaire pour revoir le moment dans CS2 (même empreinte).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import zstandard

from postgame.games.base import ErreurLecture

journal = logging.getLogger(__name__)

FORMAT = 1
VERSION_EXTRACTION = 3  # à augmenter quand la lecture des démos change (relecture)
EXTENSION = ".pgpro"
PAS_POSITIONS = 16  # ticks : 4 positions par seconde
TICKS_AVANT_LACHER = 64  # 1 s d'état complet avant chaque lancer

EVENEMENTS = [
    "round_freeze_end",
    "round_end",
    "round_officially_ended",
    "player_death",
    "player_hurt",
    "player_blind",
    "grenade_thrown",
    "smokegrenade_detonate",
    "smokegrenade_expired",
    "flashbang_detonate",
    "hegrenade_detonate",
    "molotov_detonate",
    "inferno_startburn",
    "inferno_expire",
    "decoy_started",
    "bomb_planted",
    "bomb_defused",
    "bomb_exploded",
    "bomb_pickup",
    "bomb_dropped",
    "item_purchase",
]
PROPS_POSITIONS = [
    "X",
    "Y",
    "Z",
    "pitch",
    "yaw",
    "team_num",
    "is_alive",
    "health",
    "armor_value",
    "active_weapon_name",
    "last_place_name",
    "current_equip_value",
    "balance",
    "is_scoped",
    "ducked",
    "is_airborne",
]
PROPS_LACHER = [
    "X",
    "Y",
    "Z",
    "pitch",
    "yaw",
    "velocity_X",
    "velocity_Y",
    "velocity_Z",
    "is_airborne",
    "ducked",
    "active_weapon_name",
]
BOUTONS = ["FIRE", "RIGHTCLICK", "JUMP", "FORWARD", "BACK", "LEFT", "RIGHT", "WALK", "DUCK"]


def _tableau(df: pd.DataFrame | None, colonnes: list[str] | None = None) -> dict[str, list]:
    """DataFrame → {colonne: valeurs} (format compact, NaN → None)."""
    if df is None or not len(df):
        return {c: [] for c in (colonnes or [])}
    if colonnes:
        df = df[[c for c in colonnes if c in df.columns]]
    sortie = {}
    for c in df.columns:
        serie = df[c]
        if pd.api.types.is_float_dtype(serie):
            serie = serie.round(2)
        valeurs = serie.astype(object).where(serie.notna(), None).tolist()
        sortie[str(c)] = [v.item() if isinstance(v, np.generic) else v for v in valeurs]
    return sortie


def vers_dataframe(tableau: dict[str, list]) -> pd.DataFrame:
    return pd.DataFrame(tableau)


def _steamids(serie: pd.Series) -> pd.Series:
    return serie.astype(str).str.replace(r"\.0$", "", regex=True)


def _ticks_rounds(rounds: pd.DataFrame, pas: int) -> list[int]:
    ticks: set[int] = set()
    for _, r in rounds.iterrows():
        fin = int(min(r["fin"], r["debut"] + 180 * 64))
        ticks |= set(range(int(r["debut"]), fin, pas))
    return sorted(ticks)


def _parse_ticks(parser: Any, props: list[str], ticks: list[int]) -> pd.DataFrame:
    """parse_ticks en écartant les props absentes de cette démo."""
    if not ticks:
        return pd.DataFrame()
    try:
        return parser.parse_ticks(props, ticks=ticks)
    except Exception:
        utiles = []
        for p in props:
            try:
                parser.parse_ticks([p], ticks=ticks[:1])
                utiles.append(p)
            except Exception:
                journal.info("prop absente de la démo : %s", p)
        return parser.parse_ticks(utiles, ticks=ticks) if utiles else pd.DataFrame()


def extraire(chemin: Path) -> dict[str, Any]:
    """Lit la démo une fois et renvoie l'extrait complet (dict sérialisable)."""
    from demoparser2 import DemoParser

    from postgame.games.cs2.donnees import construire_rounds, equipe_gagnante
    from postgame.games.cs2.references import extraire_observations, mesures_des_joueurs
    from postgame.importation import empreinte_fichier

    try:
        parser = DemoParser(str(chemin))
        entete = parser.parse_header()
        presents = set(parser.list_game_events())
        evts = dict(parser.parse_events([e for e in EVENEMENTS if e in presents]))
        infos = parser.parse_player_info()
    except Exception as exc:
        raise ErreurLecture(f"démo pro illisible : {exc}") from exc

    vide = pd.DataFrame(columns=["tick"])
    debuts = sorted(evts.get("round_freeze_end", vide)["tick"].astype(int).tolist())
    fins_df = evts.get("round_end", vide)
    fins = sorted(fins_df["tick"].astype(int).tolist())
    gagnants = {}
    if "winner" in fins_df:
        gagnants = {
            int(t): equipe_gagnante(w)
            for t, w in zip(fins_df["tick"], fins_df["winner"], strict=True)
        }
    rounds = construire_rounds(debuts, fins, gagnants)
    if "reason" in fins_df:
        raisons = dict(zip(fins_df["tick"].astype(int), fins_df["reason"].astype(str), strict=True))
        rounds["raison"] = [raisons.get(int(f)) for f in rounds["fin"]]

    positions = _parse_ticks(parser, PROPS_POSITIONS, _ticks_rounds(rounds, PAS_POSITIONS))
    if len(positions):
        positions["steamid"] = _steamids(positions["steamid"])
        positions = positions.drop(columns=[c for c in ("name",) if c in positions.columns])

    jets = evts.get("grenade_thrown")
    lacher = pd.DataFrame()
    if jets is not None and len(jets):
        ticks = sorted(
            {int(t) - k for t in jets["tick"] for k in range(TICKS_AVANT_LACHER + 1) if t - k >= 0}
        )
        lacher = _parse_ticks(parser, PROPS_LACHER + BOUTONS, ticks)
        if len(lacher):
            lacher["steamid"] = _steamids(lacher["steamid"])
            # Seulement le lanceur, pas les 9 autres joueurs.
            couples = {
                (str(s).removesuffix(".0"), int(t) - k)
                for s, t in zip(jets["user_steamid"], jets["tick"], strict=True)
                for k in range(TICKS_AVANT_LACHER + 1)
            }
            garde = [
                (s, int(t)) in couples
                for s, t in zip(lacher["steamid"], lacher["tick"], strict=True)
            ]
            lacher = lacher[garde].drop(columns=[c for c in ("name",) if c in lacher.columns])

    observations = extraire_observations(chemin)
    try:
        mesures = mesures_des_joueurs(chemin)
    except ErreurLecture as exc:
        journal.warning("mesures pros : %s", exc)
        mesures = []

    evenements = {}
    for nom, df in evts.items():
        if nom in ("round_freeze_end",):
            continue
        df = df.copy()
        for c in [c for c in df.columns if c.endswith("steamid")]:
            df[c] = _steamids(df[c])
        evenements[nom] = _tableau(df)

    return {
        "format": FORMAT,
        "version": VERSION_EXTRACTION,
        "empreinte": empreinte_fichier(chemin),
        "fichier": chemin.name,
        "carte": str(entete.get("map_name", "")),
        "serveur": str(entete.get("server_name", "")),
        "extrait_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "joueurs": [
            {
                "steamid": str(s).removesuffix(".0"),
                "nom": str(n),
                "equipe": int(e) if pd.notna(e) else None,
            }
            for s, n, e in zip(
                infos["steamid"],
                infos["name"],
                infos.get("team_number", pd.Series([None] * len(infos))),
                strict=True,
            )
        ],
        "rounds": _tableau(rounds),
        "positions": _tableau(positions),
        "lacher": _tableau(lacher),
        "evenements": evenements,
        "observations": _tableau(observations),
        "mesures": [
            {"joueur": j, "nom": nom, "contexte": ctx, "valeur": v, "n": n}
            for j, nom, ctx, v, n in mesures
        ],
    }


def ecrire(extrait: dict[str, Any], dossier: Path) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    nom = f"{Path(extrait['fichier']).stem}{EXTENSION}"
    cible = dossier / nom
    brut = json.dumps(extrait, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cible.write_bytes(zstandard.ZstdCompressor(level=12).compress(brut))
    return cible


def lire(fichier: Path) -> dict[str, Any]:
    brut = zstandard.ZstdDecompressor().decompress(fichier.read_bytes(), max_output_size=2**31)
    extrait = json.loads(brut)
    if extrait.get("format") != FORMAT:
        raise ErreurLecture(f"format d'extrait inconnu : {extrait.get('format')}")
    return extrait
