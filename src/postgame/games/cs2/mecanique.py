"""Mesures de mécanique CS2 (lot L1, exigences CS-AIM-01 à 06).

Toutes les fonctions prennent un `DonneesMatch` et renvoient un `ResultatAnalyse`
(mesures + preuves). Les définitions (nom, version, unité) sont en tête de fichier :
incrémenter la version d'une mesure dès que son calcul change (COM-08).

Toutes les mesures sont `fiable=False` tant qu'elles n'ont pas été vérifiées à la main sur
5 cas d'une vraie démo (critère de fin de L1, voir A_VALIDER.md).
"""

from __future__ import annotations

import math
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
    1,
    "%",
    "Part des tirs effectués sous 34 % de la vitesse max de l'arme (précision maximale).",
)
D_CS_PREMIERES = definir(
    "cs2.contre_strafe.part_premieres_balles_precises",
    1,
    "%",
    "Part des premières balles d'engagement tirées sous 34 % de la vitesse max de "
    "l'arme (contre-strafe réussi).",
)
D_CS_VITESSE = definir(
    "cs2.contre_strafe.vitesse_mediane_premiere_balle",
    1,
    "u/s",
    "Vitesse médiane du joueur à la première balle d'un engagement.",
    sens="bas",
)
D_PB_PRECISION = definir(
    "cs2.premiere_balle.precision",
    1,
    "%",
    "Part des premières balles d'engagement qui touchent un joueur.",
)
D_PB_HS = definir(
    "cs2.premiere_balle.headshot",
    1,
    "%",
    "Part des premières balles d'engagement qui touchent la tête.",
)
D_SPRAY_DECROCHE = definir(
    "cs2.spray.balle_decrochage",
    1,
    "balle",
    "Rang de la balle à partir duquel l'erreur de visée (recul compris) dépasse 1,5° et le "
    "double de celle des 3 premières balles, deux balles de suite.",
)
D_SPRAY_TOUCHE = definir(
    "cs2.spray.touche_par_tranche",
    1,
    "%",
    "Part des balles qui touchent, par tranche de rang dans la rafale (rafales de 5+).",
)
D_SPRAY_ERREUR = definir(
    "cs2.spray.erreur_mediane_par_tranche",
    1,
    "°",
    "Erreur angulaire médiane entre le tir (vue + recul) et la tête visée, par tranche.",
    sens="bas",
)
D_REACTION = definir(
    "cs2.reaction.delai_median",
    1,
    "ms",
    "Délai médian entre l'apparition d'un adversaire (indicateur « repéré ») et le premier "
    "tir dirigé vers lui.",
    sens="bas",
)
D_TTK = definir(
    "cs2.ttk.median",
    1,
    "ms",
    "Délai médian entre le premier tir sur un adversaire apparu et sa mort.",
    sens="bas",
)
D_VISEUR_ECART = definir(
    "cs2.viseur.ecart_median",
    1,
    "°",
    "Écart angulaire médian entre le viseur et la tête d'un adversaire au moment où il "
    "devient visible.",
    sens="bas",
)
D_VISEUR_SOUS_5 = definir(
    "cs2.viseur.part_ecart_sous_5deg",
    1,
    "%",
    "Part des apparitions d'adversaires avec le viseur à moins de 5° de la tête.",
)
D_VISEUR_VERTICAL = definir(
    "cs2.viseur.ecart_vertical_moyen",
    1,
    "°",
    "Écart vertical moyen viseur − tête à l'apparition ; positif = viseur trop bas.",
    sens="neutre",
)
D_VISEUR_HORIZONTAL = definir(
    "cs2.viseur.ecart_horizontal_moyen",
    1,
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
D_ARME_KILLS = definir("cs2.armes.kills", 1, "kills", "Kills par arme.")
D_ARME_HS = definir("cs2.armes.headshot", 1, "%", "Part des kills à la tête, par arme.")
D_ARME_PRECISION = definir(
    "cs2.armes.precision", 1, "%", "Part des balles qui touchent un joueur, par arme."
)
D_ARME_DEGATS = definir("cs2.armes.degats", 1, "PV", "Dégâts infligés par arme.")


# --- Préparation --------------------------------------------------------------------------


def _pct(n: float, total: float) -> float | None:
    return 100.0 * n / total if total else None


def preparer_tirs(d: DonneesMatch) -> pd.DataFrame:
    """Tirs du joueur suivi, avec son état au moment du tir, l'engagement, la rafale, le
    rang de la balle et la touche éventuelle."""
    tirs = d.tirs[(d.tirs["steamid"] == d.moi) & d.tirs["arme"].map(est_arme_a_feu)]
    tirs = tirs.sort_values("tick").reset_index(drop=True)
    if not len(tirs):
        return tirs.assign(
            vitesse=[], premiere=[], rafale=[], balle=[], touche=[], victime=[], zone=[]
        )
    etats = d.mes_ticks()[
        ["tick", "x", "y", "z", "vx", "vy", "pitch", "yaw", "accroupi", "punch_pitch", "punch_yaw"]
    ].sort_values("tick")
    t = pd.merge_asof(tirs, etats, on="tick", direction="backward")
    t["vitesse"] = np.hypot(t["vx"].fillna(0.0), t["vy"].fillna(0.0))

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
    if not len(t):
        return r
    t = t.assign(precis=t["vitesse"] <= t["arme"].map(lambda a: arme(a).vitesse_precise))
    premieres = t[t["premiere"]]
    r.mesures.append(mesure(D_CS_PRECIS, _pct(t["precis"].sum(), len(t)), n=len(t)))
    for code, g in t.groupby("arme"):
        r.mesures.append(mesure(D_CS_PRECIS, _pct(g["precis"].sum(), len(g)), arme=code, n=len(g)))
    if len(premieres):
        r.mesures.append(
            mesure(
                D_CS_PREMIERES, _pct(premieres["precis"].sum(), len(premieres)), n=len(premieres)
            )
        )
        r.mesures.append(mesure(D_CS_VITESSE, premieres["vitesse"].median(), n=len(premieres)))
        pires = premieres[~premieres["precis"]].nlargest(NB_PREUVES, "vitesse")
        for _, s in pires.iterrows():
            a = arme(s["arme"])
            r.preuves.append(
                Preuve(
                    D_CS_PREMIERES.nom,
                    int(s["tick"]),
                    f"Première balle à {s['vitesse']:.0f} u/s avec {a.libelle} "
                    f"(précis sous {a.vitesse_precise:.0f} u/s)",
                    d.numero_round(int(s["tick"])),
                    {"vitesse": round(float(s["vitesse"]), 1), "arme": s["arme"]},
                )
            )
    return r


# --- CS-AIM-02 : première balle -----------------------------------------------------------


def premiere_balle(d: DonneesMatch, tirs: pd.DataFrame) -> ResultatAnalyse:
    r = ResultatAnalyse()
    if not len(tirs):
        return r
    p = tirs[tirs["premiere"] & tirs["arme"].map(est_arme_de_precision_balle)]
    if not len(p):
        return r
    tete = p["zone"] == "tete"
    r.mesures.append(mesure(D_PB_PRECISION, _pct(p["touche"].sum(), len(p)), n=len(p)))
    r.mesures.append(mesure(D_PB_HS, _pct(tete.sum(), len(p)), n=len(p)))
    for code, g in p.groupby("arme"):
        r.mesures.append(
            mesure(D_PB_PRECISION, _pct(g["touche"].sum(), len(g)), arme=code, n=len(g))
        )
        r.mesures.append(
            mesure(D_PB_HS, _pct((g["zone"] == "tete").sum(), len(g)), arme=code, n=len(g))
        )
    for _, s in p[~p["touche"]].head(NB_PREUVES).iterrows():
        r.preuves.append(
            Preuve(
                D_PB_PRECISION.nom,
                int(s["tick"]),
                f"Première balle manquée ({arme(s['arme']).libelle}, {s['vitesse']:.0f} u/s)",
                d.numero_round(int(s["tick"])),
                {"arme": s["arme"]},
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
    r = ResultatAnalyse()
    e = erreurs_spray(d, tirs, positions)
    if not len(e):
        return r
    nb_rafales = int(e["rafale"].nunique())
    r.mesures.append(mesure(D_SPRAY_DECROCHE, balle_de_decrochage(e), rafales=nb_rafales))
    e = e.assign(tranche=e["balle"].map(_tranche))
    for _debut, _fin, nom in TRANCHES:
        g = e[e["tranche"] == nom]
        if not len(g):
            continue
        r.mesures.append(
            mesure(D_SPRAY_TOUCHE, _pct(g["touche"].sum(), len(g)), tranche=nom, n=len(g))
        )
        erreurs = g["erreur"].dropna()
        if len(erreurs):
            r.mesures.append(mesure(D_SPRAY_ERREUR, erreurs.median(), tranche=nom, n=len(erreurs)))
    pires = (
        e.dropna(subset=["erreur"])
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
                {"erreur": round(float(s["erreur"]), 2)},
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
        visee = angle_entre(
            tir["yaw"] + ECHELLE_RECUL * tir["punch_yaw"],
            tir["pitch"] + ECHELLE_RECUL * tir["punch_pitch"],
            yaw_c,
            pitch_c,
        )
        if visee <= ANGLE_TIR_SUR_CIBLE:
            app.reaction_ms = (int(tir["tick"]) - app.tick) * 1000 / TICKS_PAR_SECONDE
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


def _cote(valeur: float, positif: str, negatif: str) -> str:
    return f"{abs(valeur):.1f}° {positif if valeur > 0 else negatif}"


def viseur_et_reaction(
    d: DonneesMatch, tirs: pd.DataFrame, positions: _Positions
) -> ResultatAnalyse:
    r = ResultatAnalyse()
    apps = apparitions(d, tirs, positions)
    if apps:
        ecarts = np.array([a.ecart for a in apps])
        n = len(apps)
        r.mesures += [
            mesure(D_VISEUR_ECART, float(np.median(ecarts)), n=n),
            mesure(D_VISEUR_SOUS_5, _pct((ecarts < 5).sum(), n), n=n),
            mesure(D_VISEUR_VERTICAL, float(np.mean([a.ecart_vertical for a in apps])), n=n),
            mesure(D_VISEUR_HORIZONTAL, float(np.mean([a.ecart_horizontal for a in apps])), n=n),
        ]
        for a in sorted(apps, key=lambda a: a.ecart, reverse=True)[:NB_PREUVES]:
            r.preuves.append(
                Preuve(
                    D_VISEUR_ECART.nom,
                    a.tick,
                    f"{a.nom} apparaît à {a.ecart:.0f}° du viseur "
                    f"({_cote(a.ecart_horizontal, 'à gauche', 'à droite')}, "
                    f"{_cote(a.ecart_vertical, 'trop bas', 'trop haut')}), à {a.distance:.0f} u",
                    d.numero_round(a.tick),
                    {
                        "ecart": round(a.ecart, 2),
                        "vertical": round(a.ecart_vertical, 2),
                        "horizontal": round(a.ecart_horizontal, 2),
                        "adversaire": a.adversaire,
                    },
                )
            )
        reactions = [a for a in apps if a.reaction_ms is not None]
        if reactions:
            r.mesures.append(
                mesure(
                    D_REACTION,
                    float(np.median([a.reaction_ms for a in reactions])),
                    n=len(reactions),
                )
            )
            for a in sorted(reactions, key=lambda a: a.reaction_ms, reverse=True)[:NB_PREUVES]:
                r.preuves.append(
                    Preuve(
                        D_REACTION.nom,
                        a.tick,
                        f"{a.reaction_ms:.0f} ms avant de tirer sur {a.nom}",
                        d.numero_round(a.tick),
                        {"reaction_ms": a.reaction_ms},
                    )
                )
        ttks = [a.ttk_ms for a in apps if a.ttk_ms is not None]
        if ttks:
            r.mesures.append(mesure(D_TTK, float(np.median(ttks)), n=len(ttks)))

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
    degats = d.degats[(d.degats["attaquant"] == d.moi) & (d.degats["victime"] != d.moi)]
    codes = set(tirs["arme"]) if len(tirs) else set()
    codes |= {c for c in kills["arme"] if est_arme_a_feu(c)}
    for code in sorted(codes):
        k = kills[kills["arme"] == code]
        t = tirs[tirs["arme"] == code] if len(tirs) else tirs
        r.mesures.append(mesure(D_ARME_KILLS, len(k), arme=code))
        if len(k):
            r.mesures.append(
                mesure(D_ARME_HS, _pct(k["headshot"].sum(), len(k)), arme=code, n=len(k))
            )
        if len(t):
            r.mesures.append(
                mesure(D_ARME_PRECISION, _pct(t["touche"].sum(), len(t)), arme=code, n=len(t))
            )
        r.mesures.append(
            mesure(D_ARME_DEGATS, degats.loc[degats["arme"] == code, "degats"].sum(), arme=code)
        )
    if len(kills):
        r.mesures.append(mesure(D_ARME_HS, _pct(kills["headshot"].sum(), len(kills)), n=len(kills)))
    if len(tirs):
        r.mesures.append(
            mesure(D_ARME_PRECISION, _pct(tirs["touche"].sum(), len(tirs)), n=len(tirs))
        )
    return r


# --- Point d'entrée -----------------------------------------------------------------------


def analyser_mecanique(d: DonneesMatch) -> ResultatAnalyse:
    tirs = preparer_tirs(d)
    positions = _Positions(d.ticks)
    r = ResultatAnalyse()
    r.etendre(contre_strafe(d, tirs))
    r.etendre(premiere_balle(d, tirs))
    r.etendre(spray(d, tirs, positions))
    r.etendre(viseur_et_reaction(d, tirs, positions))
    r.etendre(par_arme(d, tirs))
    return r
