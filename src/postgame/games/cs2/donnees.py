"""Extraction des données de match utiles aux analyses CS2, dans un schéma stable.

Les analyseurs ne voient jamais demoparser2 : ils travaillent sur `DonneesMatch`, dont les
colonnes sont décrites ci-dessous. Les tests fabriquent des `DonneesMatch` à la main.

ticks   : tick, steamid (str), nom, equipe, x, y, z, vx, vy, pitch, yaw, vivant (bool),
          accroupi (bool), arme (code), vu_par_moi (bool : l'adversaire est « repéré » par
          le joueur suivi), punch_pitch, punch_yaw
tirs    : tick, steamid, arme                                  (weapon_fire)
degats  : tick, attaquant, victime, arme, degats, zone         (player_hurt ; zone 'tete'…)
morts   : tick, attaquant, victime, arme, headshot (bool)      (player_death)
rounds  : numero, debut, fin, gagnant (2 = T, 3 = CT, ou None)  (fin du freeze → fin du round)
aveuglements : tick, attaquant (lanceur), victime, duree (s)  (player_blind)
grenades : tick, lanceur, type, x, y, z, entite, fin           (éclatement ; fin = fin d'effet)
lancers  : tick, steamid, type                                 (grenade_thrown)
inventaires : tick, steamid, grenades (liste de codes)         (début/fin de round, avant mort)
lieux    : tick, steamid, lieu (nom de zone de la carte)       (installation, lancers, pose)
bombe    : tick, evenement (pose, desamorcee, explosee), steamid
economie : tick, steamid, argent, valeur_equipement, depense_round
           (fin des achats = installation, avant chaque mort, fin de round)

Types de grenade : flash, he, smoke, molotov (incendiaire comprise), decoy.
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
# Moment où l'on relève les positions « installées » de chaque round (CS-POS-04).
DELAI_INSTALLATION_TICKS = 20 * TICKS_PAR_SECONDE

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
        default_factory=lambda: pd.DataFrame(columns=["numero", "debut", "fin", "gagnant"])
    )
    carte: str = ""
    aveuglements: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["tick", "attaquant", "victime", "duree"])
    )
    grenades: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            columns=["tick", "lanceur", "type", "x", "y", "z", "entite", "fin"]
        )
    )
    lancers: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["tick", "steamid", "type"])
    )
    inventaires: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["tick", "steamid", "grenades"])
    )
    lieux: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["tick", "steamid", "lieu"])
    )
    bombe: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["tick", "evenement", "steamid"])
    )
    economie: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            columns=["tick", "steamid", "argent", "valeur_equipement", "depense_round"]
        )
    )

    def numero_round(self, tick: int) -> int | None:
        if not len(self.rounds):
            return None
        avant = self.rounds[self.rounds["debut"] <= tick]
        return int(avant["numero"].iloc[-1]) if len(avant) else None

    def mes_ticks(self) -> pd.DataFrame:
        return self.ticks[self.ticks["steamid"] == self.moi]

    def round_de(self, tick: int) -> pd.Series | None:
        """Ligne du round en cours à ce tick (entre fin du freeze et fin du round)."""
        if not len(self.rounds):
            return None
        dedans = self.rounds[(self.rounds["debut"] <= tick) & (self.rounds["fin"] >= tick)]
        return dedans.iloc[0] if len(dedans) else None

    def est_deathmatch(self) -> bool:
        return len(self.rounds) <= 1


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


EVENEMENTS = [
    "weapon_fire",
    "player_hurt",
    "player_death",
    "round_freeze_end",
    "round_end",
    "player_blind",
    "grenade_thrown",
    "flashbang_detonate",
    "hegrenade_detonate",
    "smokegrenade_detonate",
    "smokegrenade_expired",
    "molotov_detonate",
    "inferno_startburn",
    "inferno_expire",
    "decoy_started",
    "bomb_planted",
    "bomb_defused",
    "bomb_exploded",
]

# Noms d'inventaire (propriété « inventory ») et d'évènements → code de grenade.
GRENADES = {
    "flashbang": "flash",
    "smoke grenade": "smoke",
    "smokegrenade": "smoke",
    "high explosive grenade": "he",
    "hegrenade": "he",
    "molotov": "molotov",
    "incendiary grenade": "molotov",
    "incgrenade": "molotov",
    "decoy grenade": "decoy",
    "decoy": "decoy",
}
PRIX_GRENADES = {"flash": 200, "smoke": 300, "he": 300, "molotov": 400, "decoy": 50}


def code_grenade(nom: object) -> str | None:
    texte = str(nom or "").strip().lower()
    if texte.startswith("weapon_"):
        texte = texte[len("weapon_") :]
    return GRENADES.get(texte)


def _col(df: pd.DataFrame, nom: str, defaut: Any = None) -> pd.Series:
    return df[nom] if nom in df else pd.Series(defaut, index=df.index)


def _cadre(colonnes: list[str], df: pd.DataFrame | None, **series) -> pd.DataFrame:
    """DataFrame au schéma `colonnes`, vide si l'évènement est absent de la démo."""
    if df is None or not len(df):
        return pd.DataFrame(columns=colonnes)
    return pd.DataFrame({c: series[c](df) for c in colonnes})


def _tick(df: pd.DataFrame) -> pd.Series:
    return df["tick"].astype("int64")


def _grenades_inventaire(valeur: Any) -> list[str]:
    if valeur is None or isinstance(valeur, float):
        return []
    return [c for c in (code_grenade(x) for x in valeur) if c]


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
        voulus = [e for e in EVENEMENTS if e in presents]
        evts = dict(parser.parse_events(voulus)) if voulus else {}
    except ErreurLecture:
        raise
    except Exception as exc:
        raise ErreurLecture(f"extraction impossible : {exc}") from exc

    tirs = _cadre(
        ["tick", "steamid", "arme"],
        evts.get("weapon_fire"),
        tick=_tick,
        steamid=lambda df: _steamid(df["user_steamid"]),
        arme=lambda df: df["weapon"].map(normaliser),
    )
    degats = _cadre(
        ["tick", "attaquant", "victime", "arme", "degats", "zone"],
        evts.get("player_hurt"),
        tick=_tick,
        attaquant=lambda df: _steamid(df["attacker_steamid"]),
        victime=lambda df: _steamid(df["user_steamid"]),
        arme=lambda df: df["weapon"].map(normaliser),
        degats=lambda df: df["dmg_health"].astype(float),
        zone=lambda df: df["hitgroup"].map(_zone),
    )
    morts = _cadre(
        ["tick", "attaquant", "victime", "arme", "headshot"],
        evts.get("player_death"),
        tick=_tick,
        attaquant=lambda df: _steamid(df["attacker_steamid"]),
        victime=lambda df: _steamid(df["user_steamid"]),
        arme=lambda df: df["weapon"].map(normaliser),
        headshot=lambda df: df["headshot"].fillna(False).astype(bool),
    )
    aveuglements = _cadre(
        ["tick", "attaquant", "victime", "duree"],
        evts.get("player_blind"),
        tick=_tick,
        attaquant=lambda df: _steamid(df["attacker_steamid"]),
        victime=lambda df: _steamid(df["user_steamid"]),
        duree=lambda df: df["blind_duration"].astype(float),
    )
    lancers = _cadre(
        ["tick", "steamid", "type"],
        evts.get("grenade_thrown"),
        tick=_tick,
        steamid=lambda df: _steamid(df["user_steamid"]),
        type=lambda df: df["weapon"].map(code_grenade),
    )
    grenades = extraire_grenades(evts)

    vide = pd.DataFrame(columns=["tick"])
    debuts = sorted(evts.get("round_freeze_end", vide)["tick"].astype(int).tolist())
    fins_df = evts.get("round_end", vide)
    fins = sorted(fins_df["tick"].astype(int).tolist())
    gagnants = (
        {int(r["tick"]): equipe_gagnante(r["winner"]) for _, r in fins_df.iterrows()}
        if "winner" in fins_df
        else {}
    )
    rounds = construire_rounds(debuts, fins, gagnants)
    bombe = extraire_bombe(evts)

    # Inventaires aux moments utiles : début et fin de round, juste avant chaque mort.
    moments = set(debuts) | set(fins) | {max(0, int(t) - 1) for t in morts["tick"]}
    inventaires = pd.DataFrame(columns=["tick", "steamid", "grenades"])
    if moments:
        try:
            inv = parser.parse_ticks(["inventory"], ticks=sorted(moments))
            inventaires = pd.DataFrame(
                {
                    "tick": inv["tick"].astype("int64"),
                    "steamid": _steamid(inv["steamid"]),
                    "grenades": inv["inventory"].map(_grenades_inventaire),
                }
            )
        except Exception:
            pass  # inventaire indisponible : les mesures de gaspillage seront absentes

    # Noms de lieux (callouts de la carte) à l'installation de chaque round et aux lancers.
    instants = (
        {t + DELAI_INSTALLATION_TICKS for t in debuts}
        | set(lancers["tick"].astype(int))
        | set(bombe["tick"].astype(int))
    )
    lieux = pd.DataFrame(columns=["tick", "steamid", "lieu"])
    if instants:
        try:
            brut_lieux = parser.parse_ticks(["last_place_name"], ticks=sorted(instants))
            lieux = pd.DataFrame(
                {
                    "tick": brut_lieux["tick"].astype("int64"),
                    "steamid": _steamid(brut_lieux["steamid"]),
                    "lieu": brut_lieux["last_place_name"].fillna("").astype(str),
                }
            )
        except Exception:
            pass  # lieux indisponibles : positions de référence non calculées

    # Économie : après la période d'achat, juste avant chaque mort, en fin de round.
    moments_eco = (
        {t + DELAI_INSTALLATION_TICKS for t in debuts}
        | set(fins)
        | {max(0, int(t) - 1) for t in morts["tick"]}
    )
    economie = pd.DataFrame(columns=COLONNES_ECONOMIE)
    if moments_eco:
        try:
            brut_eco = parser.parse_ticks(PROPS_ECONOMIE, ticks=sorted(moments_eco))
            economie = pd.DataFrame(
                {
                    "tick": brut_eco["tick"].astype("int64"),
                    "steamid": _steamid(brut_eco["steamid"]),
                    "argent": brut_eco["balance"].fillna(0).astype(int),
                    "valeur_equipement": brut_eco["current_equip_value"].fillna(0).astype(int),
                    "depense_round": brut_eco["cash_spent_this_round"].fillna(0).astype(int),
                }
            )
        except Exception:
            pass  # économie indisponible : mesures d'économie absentes

    return DonneesMatch(
        moi=moi,
        ticks=normaliser_ticks(brut, moi),
        tirs=tirs,
        degats=degats,
        morts=morts,
        rounds=rounds,
        carte=str(entete.get("map_name", "")),
        aveuglements=aveuglements,
        grenades=grenades,
        lancers=lancers,
        inventaires=inventaires,
        lieux=lieux,
        bombe=bombe,
        economie=economie,
    )


PROPS_ECONOMIE = ["balance", "current_equip_value", "cash_spent_this_round"]
COLONNES_ECONOMIE = ["tick", "steamid", "argent", "valeur_equipement", "depense_round"]
COLONNES_BOMBE = ["tick", "evenement", "steamid"]


def extraire_bombe(evts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Évènements de la bombe : pose, désamorçage, explosion (avec le joueur concerné)."""
    morceaux = []
    for nom, evenement in (
        ("bomb_planted", "pose"),
        ("bomb_defused", "desamorcee"),
        ("bomb_exploded", "explosee"),
    ):
        df = evts.get(nom)
        if df is None or not len(df):
            continue
        morceaux.append(
            pd.DataFrame(
                {
                    "tick": _tick(df),
                    "evenement": evenement,
                    "steamid": _steamid(_col(df, "user_steamid", "")),
                }
            )
        )
    if not morceaux:
        return pd.DataFrame(columns=COLONNES_BOMBE)
    return pd.concat(morceaux, ignore_index=True).sort_values("tick").reset_index(drop=True)


COLONNES_GRENADES = ["tick", "lanceur", "type", "x", "y", "z", "entite", "fin"]
DUREE_MOLOTOV_DEFAUT = 7 * TICKS_PAR_SECONDE


def extraire_grenades(evts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Une ligne par grenade qui a éclaté : où, quand, par qui, et jusqu'à quand elle agit
    (smoke : jusqu'à sa dissipation ; molotov : jusqu'à l'extinction ; sinon = tick)."""
    morceaux = []
    for nom, type_ in (
        ("flashbang_detonate", "flash"),
        ("hegrenade_detonate", "he"),
        ("smokegrenade_detonate", "smoke"),
        ("decoy_started", "decoy"),
    ):
        df = evts.get(nom)
        if df is None or not len(df):
            continue
        morceaux.append(
            pd.DataFrame(
                {
                    "tick": _tick(df),
                    "lanceur": _steamid(_col(df, "user_steamid", "")),
                    "type": type_,
                    "x": _col(df, "x", np.nan).astype(float),
                    "y": _col(df, "y", np.nan).astype(float),
                    "z": _col(df, "z", np.nan).astype(float),
                    "entite": _col(df, "entityid", -1),
                    "fin": _tick(df),
                }
            )
        )
    grenades = (
        pd.concat(morceaux, ignore_index=True)
        if morceaux
        else pd.DataFrame(columns=COLONNES_GRENADES)
    )

    # Durée des smokes : smokegrenade_expired porte le même entityid.
    expirations = evts.get("smokegrenade_expired")
    if expirations is not None and len(expirations) and "entityid" in expirations:
        fins = expirations.groupby("entityid")["tick"].max()
        masque = grenades["type"] == "smoke"
        grenades.loc[masque, "fin"] = (
            grenades.loc[masque, "entite"].map(fins).fillna(grenades.loc[masque, "tick"])
        ).astype("int64")

    # Molotovs : le feu (inferno_*) n'a pas toujours de lanceur ; on le rattache au
    # molotov_detonate le plus proche (même tick à 2 près, moins de 300 u).
    feux = evts.get("inferno_startburn")
    if feux is not None and len(feux):
        detonations = evts.get("molotov_detonate", pd.DataFrame(columns=["tick"]))
        extinctions = evts.get("inferno_expire", pd.DataFrame(columns=["tick"]))
        fin_par_entite = (
            extinctions.groupby("entityid")["tick"].max()
            if len(extinctions) and "entityid" in extinctions
            else pd.Series(dtype="int64")
        )
        molotovs = []
        for _, feu in feux.iterrows():
            lanceur = ""
            if "user_steamid" in feu and pd.notna(feu["user_steamid"]):
                lanceur = str(feu["user_steamid"]).removesuffix(".0")
            if not lanceur and len(detonations):
                proches = detonations[(detonations["tick"] - feu["tick"]).abs() <= 2]
                if len(proches):
                    d2 = (proches["x"] - feu["x"]) ** 2 + (proches["y"] - feu["y"]) ** 2
                    if d2.min() <= 300**2:
                        lanceur = str(proches.loc[d2.idxmin(), "user_steamid"]).removesuffix(".0")
            entite = feu.get("entityid", -1)
            molotovs.append(
                {
                    "tick": int(feu["tick"]),
                    "lanceur": lanceur,
                    "type": "molotov",
                    "x": float(feu["x"]),
                    "y": float(feu["y"]),
                    "z": float(feu["z"]),
                    "entite": entite,
                    "fin": int(fin_par_entite.get(entite, feu["tick"] + DUREE_MOLOTOV_DEFAUT)),
                }
            )
        grenades = pd.concat([grenades, pd.DataFrame(molotovs)], ignore_index=True)
    return grenades[COLONNES_GRENADES].sort_values("tick").reset_index(drop=True)


def construire_rounds(
    debuts: list[int], fins: list[int], gagnants: dict[int, int] | None = None
) -> pd.DataFrame:
    """Associe chaque fin de freeze à la fin de round suivante. Un round sans fin connue
    (deathmatch, démo coupée) court jusqu'au début suivant, ou à l'infini.
    `gagnants` : équipe gagnante (2 = T, 3 = CT) par tick de fin de round."""
    gagnants = gagnants or {}
    lignes = []
    for i, debut in enumerate(debuts):
        suivant = debuts[i + 1] if i + 1 < len(debuts) else None
        fin = next((f for f in fins if f > debut and (suivant is None or f <= suivant)), None)
        gagnant = gagnants.get(fin) if fin is not None else None
        if fin is None:
            fin = suivant if suivant is not None else np.iinfo(np.int64).max
        lignes.append({"numero": i + 1, "debut": debut, "fin": fin, "gagnant": gagnant})
    return pd.DataFrame(lignes, columns=["numero", "debut", "fin", "gagnant"])


def equipe_gagnante(valeur: Any) -> int | None:
    """round_end.winner : 2 / 3, ou « T » / « CT » selon les versions."""
    if valeur is None or (isinstance(valeur, float) and np.isnan(valeur)):
        return None
    texte = str(valeur).strip().upper()
    if texte in ("T", "TERRORIST", "2"):
        return 2
    if texte in ("CT", "3"):
        return 3
    return None


class Positions:
    """Accès rapide à l'état de n'importe quel joueur à un tick donné."""

    def __init__(self, ticks: pd.DataFrame):
        self._par_joueur = {
            sid: (g["tick"].to_numpy(), g.reset_index(drop=True))
            for sid, g in ticks.sort_values("tick").groupby("steamid")
        }

    def etat(self, steamid: str, tick: int) -> pd.Series | None:
        """Dernier état connu du joueur à ce tick (ou avant)."""
        entree = self._par_joueur.get(steamid)
        if entree is None:
            return None
        ticks, lignes = entree
        pos = int(np.searchsorted(ticks, tick, side="right")) - 1
        return lignes.iloc[pos] if pos >= 0 else None

    def equipe(self, steamid: str, tick: int) -> int | None:
        etat = self.etat(steamid, tick)
        return int(etat["equipe"]) if etat is not None else None

    def joueurs(self) -> list[str]:
        return list(self._par_joueur)
