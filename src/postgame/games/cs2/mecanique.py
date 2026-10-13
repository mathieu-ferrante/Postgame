"""Mesures de mécanique CS2 (lot L1, exigences CS-AIM-01 à 06), par arme (CTX-01).

Une valeur de mécanique ne se juge qu'avec l'arme qui l'a produite : on ne vise ni ne se
déplace pareil avec une AWP, une AK ou un MP9. Toutes les mesures sont donc émises **par
catégorie d'arme** (contexte {categorie}) et **par arme** (contexte {categorie, arme}),
jamais mélangées. Les attentes propres à chaque catégorie (armes.STYLES) en découlent :
- précision maximale sous 34 % de la vitesse max de l'arme, **lunette ouverte comprise**
  (AWP lunette : 100 u/s × 34 % = 34 u/s) ; un tir en l'air n'est jamais précis ;
- headshots non jugés pour les snipers (l'AWP tue au corps) : à la place, part des
  premières balles mortelles et usage de la lunette ;
- spray : par arme (chaque arme a son motif de recul) ;
- placement du viseur et réaction : par catégorie de l'arme en main à l'apparition.

Les versions des mesures dont le calcul a changé sont passées à 2 (COM-08) : toutes
restent `fiable=False` jusqu'à vérification à la main sur une vraie démo.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
import pandas as pd

from postgame.games.cs2.armes import (
    arme,
    est_arme_a_feu,
    est_arme_de_precision_balle,
    est_arme_de_rafale,
)
from postgame.games.cs2.donnees import TICKS_PAR_SECONDE, DonneesMatch
from postgame.games.cs2.donnees import Positions as _Positions
from postgame.games.cs2.geometrie import (
    ECHELLE_RECUL,
    angle_entre,
    direction,
    ecart_angulaire,
    hauteur_yeux,
)
from postgame.mesures import Preuve, ResultatAnalyse, definir, mesure

# --- Paramètres ---------------------------------------------------------------------------

ECART_ENGAGEMENT_TICKS = 32  # 0,5 s sans tirer : le tir suivant ouvre un nouvel engagement
FENETRE_TOUCHE_TICKS = 2  # un player_hurt est rattaché au tir des 2 ticks précédents
MIN_BALLES_RAFALE = 5
ECART_NOUVELLE_APPARITION_TICKS = 32  # 0,5 s invisible : la réapparition est un nouvel épisode
FENETRE_REACTION_TICKS = 2 * TICKS_PAR_SECONDE
FENETRE_TTK_TICKS = 5 * TICKS_PAR_SECONDE
ANGLE_TIR_SUR_CIBLE = 8.0  # degrés : un tir vise cet adversaire
DISTANCE_MAX_EPISODE = 4000.0
VITESSE_DEPLACEMENT = 150.0  # au-delà, le joueur se déplace (hauteur du viseur en mouvement)
NB_PREUVES = 5

# --- Définitions --------------------------------------------------------------------------

D_CS_PRECIS = definir(
    "cs2.contre_strafe.part_tirs_precis",
    2,
    "%",
    "Part des tirs à précision maximale : vitesse sous 34 % de la vitesse max de l'arme "
    "(lunette comprise) et pieds au sol.",
)
D_CS_PREMIERES = definir(
    "cs2.contre_strafe.part_premieres_balles_precises",
    2,
    "%",
    "Part des premières balles d'engagement tirées à précision maximale (contre-strafe "
    "réussi, lunette comprise, pieds au sol).",
)
D_CS_VITESSE = definir(
    "cs2.contre_strafe.vitesse_mediane_premiere_balle",
    2,
    "u/s",
    "Vitesse médiane du joueur à la première balle d'un engagement.",
    sens="bas",
)
D_CS_AIR = definir(
    "cs2.contre_strafe.part_tirs_en_l_air",
    1,
    "%",
    "Part des tirs effectués en l'air (saut, chute) : jamais précis.",
    sens="bas",
)
D_PB_PRECISION = definir(
    "cs2.premiere_balle.precision",
    2,
    "%",
    "Part des premières balles d'engagement qui touchent un joueur.",
)
D_PB_HS = definir(
    "cs2.premiere_balle.headshot",
    2,
    "%",
    "Part des premières balles d'engagement qui touchent la tête (hors snipers).",
)
D_PB_MORTELLE = definir(
    "cs2.sniper.part_premiere_balle_mortelle",
    1,
    "%",
    "Snipers : part des premières balles d'engagement qui tuent.",
)
D_SNIPER_LUNETTE = definir(
    "cs2.sniper.part_tirs_lunette",
    1,
    "%",
    "Snipers : part des tirs lunette ouverte (le tir sans lunette est très imprécis).",
)
D_SNIPER_DELAI = definir(
    "cs2.sniper.delai_lunette_tir_median",
    1,
    "ms",
    "Snipers : délai médian entre l'ouverture de la lunette et le tir.",
    sens="neutre",
)
D_SPRAY_DECROCHE = definir(
    "cs2.spray.balle_decrochage",
    2,
    "balle",
    "Rang de la balle à partir duquel l'erreur de visée (recul compris) dépasse 1,5° et le "
    "double de celle des 3 premières balles, deux balles de suite (par arme).",
)
D_SPRAY_TOUCHE = definir(
    "cs2.spray.touche_par_tranche",
    2,
    "%",
    "Part des balles qui touchent, par tranche de rang dans la rafale (rafales de 5+, par arme).",
)
D_SPRAY_ERREUR = definir(
    "cs2.spray.erreur_mediane_par_tranche",
    2,
    "°",
    "Erreur angulaire médiane entre le tir (vue + recul) et la tête visée, par tranche et "
    "par arme.",
    sens="bas",
)
D_REACTION = definir(
    "cs2.reaction.delai_median",
    2,
    "ms",
    "Délai médian entre l'apparition d'un adversaire (indicateur « repéré ») et le premier "
    "tir dirigé vers lui, selon l'arme en main.",
    sens="bas",
)
D_TTK = definir(
    "cs2.ttk.median",
    2,
    "ms",
    "Délai médian entre le premier tir sur un adversaire apparu et sa mort, par arme.",
    sens="bas",
)
D_VISEUR_ECART = definir(
    "cs2.viseur.ecart_median",
    2,
    "°",
    "Écart angulaire médian entre le viseur et la tête d'un adversaire au moment où il "
    "devient visible (toutes armes, et par catégorie de l'arme en main).",
    sens="bas",
)
D_VISEUR_SOUS_5 = definir(
    "cs2.viseur.part_ecart_sous_5deg",
    2,
    "%",
    "Part des apparitions d'adversaires avec le viseur à moins de 5° de la tête.",
)
D_VISEUR_VERTICAL = definir(
    "cs2.viseur.ecart_vertical_moyen",
    2,
    "°",
    "Écart vertical moyen viseur − tête à l'apparition ; positif = viseur trop bas.",
    sens="neutre",
)
D_VISEUR_HORIZONTAL = definir(
    "cs2.viseur.ecart_horizontal_moyen",
    2,
    "°",
    "Écart horizontal moyen viseur − tête à l'apparition ; positif = viseur trop à gauche.",
    sens="neutre",
)
D_VISEUR_DEPLACEMENT = definir(
    "cs2.viseur.pitch_median_deplacement",
    1,
    "°",
    "Inclinaison médiane du regard en déplacement sans adversaire visible ; 0 = horizon, "
    "positif = vers le sol.",
    sens="neutre",
)
D_ARME_KILLS = definir("cs2.armes.kills", 1, "kills", "Kills par arme.", sens="neutre")
D_ARME_HS = definir(
    "cs2.armes.headshot",
    2,
    "%",
    "Part des kills à la tête, par arme et par catégorie (hors snipers).",
)
D_ARME_PRECISION = definir(
    "cs2.armes.precision",
    2,
    "%",
    "Part des balles qui touchent un joueur, par arme et par catégorie.",
)
D_ARME_DEGATS = definir("cs2.armes.degats", 1, "PV", "Dégâts infligés par arme.", sens="neutre")


# --- Préparation --------------------------------------------------------------------------


def _pct(n: float, total: float) -> float | None:
    return 100.0 * n / total if total else None


def contexte_arme(code: str) -> dict[str, str]:
    return {"categorie": arme(code).categorie, "arme": code}


def par_categorie_et_arme(t: pd.DataFrame) -> Iterator[tuple[dict[str, str], pd.DataFrame]]:
    """Chaque catégorie (contexte {categorie}) puis chaque arme ({categorie, arme})."""
    if not len(t):
        return
    for categorie, g in t.groupby("categorie"):
        yield {"categorie": categorie}, g
    for code, g in t.groupby("arme"):
        yield contexte_arme(code), g


def preparer_tirs(d: DonneesMatch) -> pd.DataFrame:
    """Tirs du joueur suivi, avec son état au moment du tir (vitesse, lunette, en l'air),
    l'engagement, la rafale, le rang de la balle et la touche éventuelle."""
    tirs = d.tirs[(d.tirs["steamid"] == d.moi) & d.tirs["arme"].map(est_arme_a_feu)]
    tirs = tirs.sort_values("tick").reset_index(drop=True)
    colonnes = [
        "vitesse",
        "premiere",
        "rafale",
        "balle",
        "touche",
        "victime",
        "zone",
        "categorie",
        "lunette",
        "en_l_air",
        "precis",
    ]
    if not len(tirs):
        return tirs.assign(**{c: [] for c in colonnes})
    mes = d.mes_ticks()
    for colonne in ("lunette", "en_l_air"):
        if colonne not in mes:
            mes = mes.assign(**{colonne: False})
    etats = mes[
        [
            "tick",
            "x",
            "y",
            "z",
            "vx",
            "vy",
            "pitch",
            "yaw",
            "accroupi",
            "punch_pitch",
            "punch_yaw",
            "lunette",
            "en_l_air",
        ]
    ].sort_values("tick")
    t = pd.merge_asof(tirs, etats, on="tick", direction="backward")
    t["vitesse"] = np.hypot(t["vx"].fillna(0.0), t["vy"].fillna(0.0))
    t["lunette"] = t["lunette"].fillna(False).astype(bool)
    t["en_l_air"] = t["en_l_air"].fillna(False).astype(bool)
    t["categorie"] = t["arme"].map(lambda a: arme(a).categorie)
    t["precis"] = [
        v <= arme(a).seuil_precis(lun) and not air
        for v, a, lun, air in zip(t["vitesse"], t["arme"], t["lunette"], t["en_l_air"], strict=True)
    ]

    ecart = t["tick"].diff()
    meme_arme = t["arme"].eq(t["arme"].shift())
    t["premiere"] = ~((ecart <= ECART_ENGAGEMENT_TICKS) & meme_arme)
    seuil = t["arme"].map(lambda a: arme(a).cadence * TICKS_PAR_SECONDE * 1.6 + 1)
    t["rafale"] = (~((ecart <= seuil) & meme_arme)).cumsum()
    t["balle"] = t.groupby("rafale").cumcount() + 1

    # Rattachement des dégâts au dernier tir des FENETRE_TOUCHE_TICKS ticks précédents.
    mes_degats = d.degats[
        (d.degats["attaquant"] == d.moi) & d.degats["arme"].map(est_arme_a_feu)
    ].sort_values("tick")
    t["touche"], t["victime"], t["zone"] = False, None, None
    if len(mes_degats):
        lien = pd.merge_asof(
            mes_degats[["tick", "victime", "zone"]],
            t[["tick"]].assign(i_tir=t.index).rename(columns={"tick": "tick_tir"}),
            left_on="tick",
            right_on="tick_tir",
            direction="backward",
            tolerance=FENETRE_TOUCHE_TICKS,
        ).dropna(subset=["i_tir"])
        for i_tir, groupe in lien.groupby("i_tir"):
            i = int(i_tir)
            t.at[i, "touche"] = True
            t.at[i, "victime"] = groupe["victime"].iloc[0]
            t.at[i, "zone"] = "tete" if (groupe["zone"] == "tete").any() else groupe["zone"].iloc[0]
    t["touche"] = t["touche"].astype(bool)
    return t


def _visee_vers(tireur: pd.Series, cible: pd.Series) -> tuple[float, float, float]:
    """(yaw, pitch, distance) de l'œil du tireur vers la tête de la cible."""
    dx = cible["x"] - tireur["x"]
    dy = cible["y"] - tireur["y"]
    dz = (cible["z"] + hauteur_yeux(bool(cible["accroupi"]))) - (
        tireur["z"] + hauteur_yeux(bool(tireur["accroupi"]))
    )
    yaw, pitch = direction(dx, dy, dz)
    return yaw, pitch, math.sqrt(dx * dx + dy * dy + dz * dz)


# --- CS-AIM-01 : contre-strafe ------------------------------------------------------------


def contre_strafe(d: DonneesMatch, tirs: pd.DataFrame) -> ResultatAnalyse:
    r = ResultatAnalyse()
    t = tirs[tirs["arme"].map(est_arme_de_precision_balle)] if len(tirs) else tirs
    for ctx, g in par_categorie_et_arme(t):
        r.mesures.append(mesure(D_CS_PRECIS, _pct(g["precis"].sum(), len(g)), **ctx, n=len(g)))
        p = g[g["premiere"]]
        if len(p):
            r.mesures.append(
                mesure(D_CS_PREMIERES, _pct(p["precis"].sum(), len(p)), **ctx, n=len(p))
            )
        if "arme" not in ctx:
            r.mesures.append(mesure(D_CS_AIR, _pct(g["en_l_air"].sum(), len(g)), **ctx, n=len(g)))
            if len(p):
                r.mesures.append(mesure(D_CS_VITESSE, p["vitesse"].median(), **ctx, n=len(p)))
    if not len(t):
        return r
    premieres = t[t["premiere"] & ~t["precis"]]
    for _, s in premieres.nlargest(NB_PREUVES, "vitesse").iterrows():
        a = arme(s["arme"])
        seuil = a.seuil_precis(bool(s["lunette"]))
        detail = "en l'air" if s["en_l_air"] else f"précis sous {seuil:.0f} u/s"
        lunette = " lunette ouverte" if s["lunette"] else ""
        r.preuves.append(
            Preuve(
                D_CS_PREMIERES.nom,
                int(s["tick"]),
                f"Première balle à {s['vitesse']:.0f} u/s avec {a.libelle}{lunette} ({detail})",
                d.numero_round(int(s["tick"])),
                {"vitesse": round(float(s["vitesse"]), 1), "arme": s["arme"]},
            )
        )
    return r


# --- CS-AIM-02 : première balle (et snipers) ----------------------------------------------


def premiere_balle(d: DonneesMatch, tirs: pd.DataFrame) -> ResultatAnalyse:
    r = ResultatAnalyse()
    if not len(tirs):
        return r
    p = tirs[tirs["premiere"] & tirs["arme"].map(est_arme_de_precision_balle)]
    kills = d.morts[d.morts["attaquant"] == d.moi]
    for ctx, g in par_categorie_et_arme(p):
        r.mesures.append(mesure(D_PB_PRECISION, _pct(g["touche"].sum(), len(g)), **ctx, n=len(g)))
        if ctx["categorie"] == "sniper":
            mortelles = sum(
                bool(
                    (
                        (kills["tick"] >= s.tick)
                        & (kills["tick"] <= s.tick + FENETRE_TOUCHE_TICKS)
                        & (kills["victime"] == s.victime)
                    ).any()
                )
                for s in g.itertuples()
                if s.touche
            )
            r.mesures.append(mesure(D_PB_MORTELLE, _pct(mortelles, len(g)), **ctx, n=len(g)))
        else:
            r.mesures.append(
                mesure(D_PB_HS, _pct((g["zone"] == "tete").sum(), len(g)), **ctx, n=len(g))
            )
    for _, s in p[~p["touche"]].head(NB_PREUVES).iterrows():
        r.preuves.append(
            Preuve(
                D_PB_PRECISION.nom,
                int(s["tick"]),
                f"Première balle manquée ({arme(s['arme']).libelle}, {s['vitesse']:.0f} u/s"
                + (", lunette ouverte" if s["lunette"] else "")
                + ")",
                d.numero_round(int(s["tick"])),
                {"arme": s["arme"]},
            )
        )
    return r


def snipers(d: DonneesMatch, tirs: pd.DataFrame) -> ResultatAnalyse:
    """Usage de la lunette et délai entre ouverture de la lunette et tir (snipers)."""
    r = ResultatAnalyse()
    if not len(tirs):
        return r
    s = tirs[tirs["categorie"] == "sniper"]
    if not len(s):
        return r
    mes = d.mes_ticks().sort_values("tick")
    ticks = mes["tick"].to_numpy()
    lunette = mes["lunette"].to_numpy() if "lunette" in mes else np.zeros(len(mes), bool)
    for code, g in s.groupby("arme"):
        ctx = contexte_arme(code)
        r.mesures.append(
            mesure(D_SNIPER_LUNETTE, _pct(g["lunette"].sum(), len(g)), **ctx, n=len(g))
        )
        delais = []
        for tir in g[g["lunette"]].itertuples():
            i = int(np.searchsorted(ticks, tir.tick, side="right")) - 1
            j = i
            while j > 0 and lunette[j - 1]:
                j -= 1
            if j > 0:  # ouverture observée dans la démo
                delais.append((tir.tick - ticks[j]) * 1000 / TICKS_PAR_SECONDE)
        if delais:
            r.mesures.append(mesure(D_SNIPER_DELAI, float(np.median(delais)), **ctx, n=len(delais)))
        for tir in g[~g["lunette"]].head(NB_PREUVES).itertuples():
            r.preuves.append(
                Preuve(
                    D_SNIPER_LUNETTE.nom,
                    int(tir.tick),
                    f"Tir sans lunette avec {arme(code).libelle}",
                    d.numero_round(int(tir.tick)),
                    {"arme": code},
                )
            )
    return r


# --- CS-AIM-03 : spray --------------------------------------------------------------------

TRANCHES = [(1, 1, "1"), (2, 5, "2-5"), (6, 10, "6-10"), (11, 999, "11+")]


def _tranche(balle: int) -> str:
    return next(nom for debut, fin, nom in TRANCHES if debut <= balle <= fin)


def erreurs_spray(d: DonneesMatch, tirs: pd.DataFrame, positions: _Positions) -> pd.DataFrame:
    """Une ligne par balle de rafale longue : rang, touche, erreur angulaire vers la cible."""
    if not len(tirs):
        return pd.DataFrame(columns=["rafale", "balle", "touche", "erreur", "tick"])
    auto = tirs[tirs["arme"].map(est_arme_de_rafale)]
    tailles = auto.groupby("rafale")["balle"].transform("max")
    longues = auto[tailles >= MIN_BALLES_RAFALE]
    lignes = []
    for rafale, g in longues.groupby("rafale"):
        victimes = g["victime"].dropna()
        cible = victimes.mode().iloc[0] if len(victimes) else None
        if cible is None:
            cible = _cible_la_plus_proche(d, g.iloc[0], positions)
        for _, s in g.iterrows():
            erreur = None
            if cible is not None:
                etat_cible = positions.etat(cible, int(s["tick"]))
                if etat_cible is not None and bool(etat_cible["vivant"]):
                    yaw_c, pitch_c, _ = _visee_vers(s, etat_cible)
                    yaw_t = s["yaw"] + ECHELLE_RECUL * s["punch_yaw"]
                    pitch_t = s["pitch"] + ECHELLE_RECUL * s["punch_pitch"]
                    erreur = angle_entre(yaw_t, pitch_t, yaw_c, pitch_c)
                    if erreur != erreur:  # NaN : recul absent de la démo
                        erreur = None
            lignes.append(
                {
                    "rafale": rafale,
                    "balle": int(s["balle"]),
                    "touche": bool(s["touche"]),
                    "erreur": erreur,
                    "tick": int(s["tick"]),
                    "arme": s["arme"],
                }
            )
    return pd.DataFrame(lignes, columns=["rafale", "balle", "touche", "erreur", "tick", "arme"])


def _cible_la_plus_proche(
    d: DonneesMatch, tir: pd.Series, positions: _Positions, angle_max: float = 10.0
) -> str | None:
    """Adversaire vivant le plus proche du viseur au moment du tir (à moins de angle_max)."""
    a_ce_tick = d.ticks[
        (d.ticks["tick"] == tir["tick"]) & (d.ticks["steamid"] != d.moi) & d.ticks["vivant"]
    ]
    meilleur, meilleur_angle = None, angle_max
    for _, cible in a_ce_tick.iterrows():
        yaw_c, pitch_c, _ = _visee_vers(tir, cible)
        angle = angle_entre(tir["yaw"], tir["pitch"], yaw_c, pitch_c)
        if angle < meilleur_angle:
            meilleur, meilleur_angle = cible["steamid"], angle
    return meilleur


def balle_de_decrochage(erreurs: pd.DataFrame, min_echantillons: int = 3) -> int | None:
    e = erreurs.dropna(subset=["erreur"])
    if not len(e):
        return None
    par_balle = e.groupby("balle")["erreur"].agg(["median", "count"])
    par_balle = par_balle[par_balle["count"] >= min_echantillons]
    debut = e[e["balle"] <= 3]["erreur"]
    if not len(debut) or not len(par_balle):
        return None
    seuil = max(1.5, 2 * float(debut.median()))
    au_dessus = [int(b) for b, ligne in par_balle.iterrows() if b >= 4 and ligne["median"] > seuil]
    for b in au_dessus:
        if b + 1 in au_dessus or b == par_balle.index.max():
            return b
    return None


def spray(d: DonneesMatch, tirs: pd.DataFrame, positions: _Positions) -> ResultatAnalyse:
    """Spray par arme : chaque arme a son propre motif de recul."""
    r = ResultatAnalyse()
    toutes = erreurs_spray(d, tirs, positions)
    if not len(toutes):
        return r
    toutes["erreur"] = pd.to_numeric(toutes["erreur"], errors="coerce")
    for code, e in toutes.groupby("arme"):
        ctx = contexte_arme(code)
        r.mesures.append(
            mesure(
                D_SPRAY_DECROCHE, balle_de_decrochage(e), **ctx, rafales=int(e["rafale"].nunique())
            )
        )
        e = e.assign(tranche=e["balle"].map(_tranche))
        for _debut, _fin, nom in TRANCHES:
            g = e[e["tranche"] == nom]
            if not len(g):
                continue
            r.mesures.append(
                mesure(
                    D_SPRAY_TOUCHE, _pct(g["touche"].sum(), len(g)), **ctx, tranche=nom, n=len(g)
                )
            )
            erreurs = g["erreur"].dropna()
            if len(erreurs):
                r.mesures.append(
                    mesure(D_SPRAY_ERREUR, erreurs.median(), **ctx, tranche=nom, n=len(erreurs))
                )
    pires = (
        toutes.dropna(subset=["erreur"])
        .groupby("rafale")
        .agg(
            tick=("tick", "min"),
            erreur=("erreur", "median"),
            balles=("balle", "max"),
            arme=("arme", "first"),
        )
        .nlargest(NB_PREUVES, "erreur")
    )
    for _, s in pires.iterrows():
        r.preuves.append(
            Preuve(
                D_SPRAY_ERREUR.nom,
                int(s["tick"]),
                f"Rafale de {int(s['balles'])} balles ({arme(s['arme']).libelle}) : erreur médiane "
                f"{s['erreur']:.1f}°",
                d.numero_round(int(s["tick"])),
                {"erreur": round(float(s["erreur"]), 2), "arme": s["arme"]},
            )
        )
    return r


# --- CS-AIM-04 et 05 : apparitions, placement du viseur, réaction, TTK -----------------------


@dataclass
class Apparition:
    tick: int
    adversaire: str
    nom: str
    distance: float
    ecart: float  # angle total viseur → tête
    ecart_vertical: float  # > 0 : viseur trop bas
    ecart_horizontal: float  # > 0 : viseur trop à gauche
    reaction_ms: float | None = None
    ttk_ms: float | None = None
    arme: str = ""  # arme en main à l'apparition
    categorie: str | None = None
    arme_tir: str | None = None  # arme du premier tir sur cet adversaire


def apparitions(d: DonneesMatch, tirs: pd.DataFrame, positions: _Positions) -> list[Apparition]:
    """Chaque moment où un adversaire devient « repéré » par le joueur suivi."""
    moi = d.mes_ticks()[["tick", "equipe", "vivant"]].rename(
        columns={"equipe": "mon_equipe", "vivant": "moi_vivant"}
    )
    autres = d.ticks[(d.ticks["steamid"] != d.moi) & d.ticks["vu_par_moi"] & d.ticks["vivant"]]
    autres = autres.merge(moi, on="tick", how="inner")
    autres = autres[autres["moi_vivant"]]
    if not d.est_deathmatch():
        autres = autres[autres["equipe"] != autres["mon_equipe"]]

    mes_morts = d.morts[d.morts["attaquant"] == d.moi]
    resultat: list[Apparition] = []
    for adversaire, g in autres.sort_values("tick").groupby("steamid"):
        ticks = g["tick"].to_numpy()
        debuts = ticks[np.concatenate(([True], np.diff(ticks) > ECART_NOUVELLE_APPARITION_TICKS))]
        for tick in debuts:
            tick = int(tick)
            etat_moi = positions.etat(d.moi, tick)
            etat_adv = positions.etat(adversaire, tick)
            if etat_moi is None or etat_adv is None:
                continue
            yaw_c, pitch_c, distance = _visee_vers(etat_moi, etat_adv)
            if distance > DISTANCE_MAX_EPISODE:
                continue
            app = Apparition(
                tick=tick,
                adversaire=adversaire,
                nom=str(etat_adv["nom"]),
                distance=distance,
                ecart=angle_entre(etat_moi["yaw"], etat_moi["pitch"], yaw_c, pitch_c),
                ecart_vertical=float(etat_moi["pitch"] - pitch_c),
                ecart_horizontal=ecart_angulaire(float(etat_moi["yaw"]), yaw_c),
                arme=str(etat_moi["arme"]),
                categorie=arme(etat_moi["arme"]).categorie if arme(etat_moi["arme"]) else None,
            )
            _reaction_et_ttk(app, tirs, positions, mes_morts)
            resultat.append(app)
    return sorted(resultat, key=lambda a: a.tick)


def _reaction_et_ttk(
    app: Apparition, tirs: pd.DataFrame, positions: _Positions, mes_morts: pd.DataFrame
) -> None:
    if not len(tirs):
        return
    fenetre = tirs[(tirs["tick"] >= app.tick) & (tirs["tick"] <= app.tick + FENETRE_REACTION_TICKS)]
    for _, tir in fenetre.iterrows():
        cible = positions.etat(app.adversaire, int(tir["tick"]))
        if cible is None or not bool(cible["vivant"]):
            break
        yaw_c, pitch_c, _ = _visee_vers(tir, cible)
        # Recul absent de la démo : la première balle n'en a pas, on le compte nul.
        visee = angle_entre(
            tir["yaw"] + ECHELLE_RECUL * _ou_zero(tir["punch_yaw"]),
            tir["pitch"] + ECHELLE_RECUL * _ou_zero(tir["punch_pitch"]),
            yaw_c,
            pitch_c,
        )
        if visee <= ANGLE_TIR_SUR_CIBLE:
            app.reaction_ms = (int(tir["tick"]) - app.tick) * 1000 / TICKS_PAR_SECONDE
            app.arme_tir = str(tir["arme"])
            kill = mes_morts[
                (mes_morts["victime"] == app.adversaire)
                & (mes_morts["tick"] >= tir["tick"])
                & (mes_morts["tick"] <= tir["tick"] + FENETRE_TTK_TICKS)
            ]
            if len(kill):
                app.ttk_ms = (
                    (int(kill["tick"].iloc[0]) - int(tir["tick"])) * 1000 / TICKS_PAR_SECONDE
                )
            return


def _ou_zero(v: float) -> float:
    return 0.0 if v is None or v != v else float(v)


def _cote(valeur: float, positif: str, negatif: str) -> str:
    return f"{abs(valeur):.1f}° {positif if valeur > 0 else negatif}"


def _mesures_viseur(apps: list[Apparition], **ctx) -> list:
    ecarts = np.array([a.ecart for a in apps])
    n = len(apps)
    sortie = [
        mesure(D_VISEUR_ECART, float(np.median(ecarts)), **ctx, n=n),
        mesure(D_VISEUR_SOUS_5, _pct((ecarts < 5).sum(), n), **ctx, n=n),
        mesure(D_VISEUR_VERTICAL, float(np.mean([a.ecart_vertical for a in apps])), **ctx, n=n),
        mesure(D_VISEUR_HORIZONTAL, float(np.mean([a.ecart_horizontal for a in apps])), **ctx, n=n),
    ]
    reactions = [a.reaction_ms for a in apps if a.reaction_ms is not None]
    if reactions:
        sortie.append(mesure(D_REACTION, float(np.median(reactions)), **ctx, n=len(reactions)))
    return sortie


def viseur_et_reaction(
    d: DonneesMatch, tirs: pd.DataFrame, positions: _Positions
) -> ResultatAnalyse:
    r = ResultatAnalyse()
    apps = apparitions(d, tirs, positions)
    if apps:
        # Toutes armes confondues (le placement du viseur se travaille en général), puis par
        # catégorie de l'arme en main : on ne tient pas un angle à l'AWP comme au fusil.
        r.mesures += _mesures_viseur(apps)
        for categorie in sorted({a.categorie for a in apps if a.categorie}):
            r.mesures += _mesures_viseur(
                [a for a in apps if a.categorie == categorie], categorie=categorie
            )
        for a in sorted(apps, key=lambda a: a.ecart, reverse=True)[:NB_PREUVES]:
            r.preuves.append(
                Preuve(
                    D_VISEUR_ECART.nom,
                    a.tick,
                    f"{a.nom} apparaît à {a.ecart:.0f}° du viseur "
                    f"({_cote(a.ecart_horizontal, 'à gauche', 'à droite')}, "
                    f"{_cote(a.ecart_vertical, 'trop bas', 'trop haut')}), à {a.distance:.0f} u"
                    + (f", arme en main : {arme(a.arme).libelle}" if arme(a.arme) else ""),
                    d.numero_round(a.tick),
                    {
                        "ecart": round(a.ecart, 2),
                        "vertical": round(a.ecart_vertical, 2),
                        "horizontal": round(a.ecart_horizontal, 2),
                        "adversaire": a.adversaire,
                        "arme": a.arme,
                    },
                )
            )
        reactions = [a for a in apps if a.reaction_ms is not None]
        for a in sorted(reactions, key=lambda a: a.reaction_ms, reverse=True)[:NB_PREUVES]:
            r.preuves.append(
                Preuve(
                    D_REACTION.nom,
                    a.tick,
                    f"{a.reaction_ms:.0f} ms avant de tirer sur {a.nom}",
                    d.numero_round(a.tick),
                    {"reaction_ms": a.reaction_ms, "arme": a.arme},
                )
            )
        par_arme_ttk: dict[str, list[float]] = {}
        for a in apps:
            if a.ttk_ms is not None and a.arme_tir:
                par_arme_ttk.setdefault(a.arme_tir, []).append(a.ttk_ms)
        for code, valeurs in sorted(par_arme_ttk.items()):
            r.mesures.append(
                mesure(D_TTK, float(np.median(valeurs)), **contexte_arme(code), n=len(valeurs))
            )

    mes = d.mes_ticks()
    if len(mes):
        vus = set(d.ticks.loc[d.ticks["vu_par_moi"], "tick"])
        deplacement = mes[
            mes["vivant"]
            & (np.hypot(mes["vx"], mes["vy"]) > VITESSE_DEPLACEMENT)
            & ~mes["tick"].isin(vus)
        ]
        if len(deplacement):
            r.mesures.append(
                mesure(
                    D_VISEUR_DEPLACEMENT, float(deplacement["pitch"].median()), n=len(deplacement)
                )
            )
    return r


# --- CS-AIM-06 : statistiques par arme ---------------------------------------------------


def par_arme(d: DonneesMatch, tirs: pd.DataFrame) -> ResultatAnalyse:
    r = ResultatAnalyse()
    kills = d.morts[(d.morts["attaquant"] == d.moi) & (d.morts["victime"] != d.moi)]
    kills = kills[kills["arme"].map(est_arme_a_feu).astype(bool)]
    kills = kills.assign(categorie=kills["arme"].map(lambda a: arme(a).categorie))
    degats = d.degats[(d.degats["attaquant"] == d.moi) & (d.degats["victime"] != d.moi)]
    codes = set(tirs["arme"]) if len(tirs) else set()
    codes |= set(kills["arme"])
    for code in sorted(codes):
        ctx = contexte_arme(code)
        k = kills[kills["arme"] == code]
        t = tirs[tirs["arme"] == code] if len(tirs) else tirs
        r.mesures.append(mesure(D_ARME_KILLS, len(k), **ctx))
        if len(k) and ctx["categorie"] != "sniper":
            r.mesures.append(mesure(D_ARME_HS, _pct(k["headshot"].sum(), len(k)), **ctx, n=len(k)))
        if len(t):
            r.mesures.append(
                mesure(D_ARME_PRECISION, _pct(t["touche"].sum(), len(t)), **ctx, n=len(t))
            )
        r.mesures.append(
            mesure(D_ARME_DEGATS, degats.loc[degats["arme"] == code, "degats"].sum(), **ctx)
        )
    for categorie, k in kills.groupby("categorie"):
        if categorie != "sniper":
            r.mesures.append(
                mesure(D_ARME_HS, _pct(k["headshot"].sum(), len(k)), categorie=categorie, n=len(k))
            )
    if len(tirs):
        for categorie, t in tirs.groupby("categorie"):
            r.mesures.append(
                mesure(
                    D_ARME_PRECISION, _pct(t["touche"].sum(), len(t)), categorie=categorie, n=len(t)
                )
            )
    return r


# --- Point d'entrée -----------------------------------------------------------------------


def analyser_mecanique(d: DonneesMatch) -> ResultatAnalyse:
    tirs = preparer_tirs(d)
    positions = _Positions(d.ticks)
    r = ResultatAnalyse()
    r.etendre(contre_strafe(d, tirs))
    r.etendre(premiere_balle(d, tirs))
    r.etendre(snipers(d, tirs))
    r.etendre(spray(d, tirs, positions))
    r.etendre(viseur_et_reaction(d, tirs, positions))
    r.etendre(par_arme(d, tirs))
    return r
