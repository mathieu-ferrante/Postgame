"""Mesures sur les grenades de Mathieu (lot L2 : CS-UTL-02, 03, 04).

Les smokes (CS-UTL-01) demandent les références pros : lot L3.
"""

from __future__ import annotations

import numpy as np

from postgame.games.cs2.donnees import (
    PRIX_GRENADES,
    TICKS_PAR_SECONDE,
    DonneesMatch,
    Positions,
)
from postgame.mesures import Preuve, ResultatAnalyse, definir, mesure

SEUIL_AVEUGLE_S = 1.0  # en dessous, un aveuglement ne gêne pas vraiment
FENETRE_AVEUGLEMENT_TICKS = 2  # player_blind arrive au tick de l'éclatement (à 2 près)
FENETRE_CONVERSION_TICKS = 2 * TICKS_PAR_SECONDE
FENETRE_DEGATS_HE_TICKS = 2
RAYON_MOLOTOV = 250.0  # u : un adversaire plus près du centre du feu est dans la zone
DELAI_DELOGE_TICKS = 3 * TICKS_PAR_SECONDE
ARMES_FEU = {"inferno", "molotov", "incgrenade"}
NB_PREUVES = 5

D_FLASH_NB = definir("cs2.flash.nombre", 1, "flashs", "Flashs lancées.", sens="neutre")
D_FLASH_ADV = definir(
    "cs2.flash.adversaires_aveugles_par_flash",
    1,
    "joueurs",
    "Nombre moyen d'adversaires aveuglés au moins 1 s par flash.",
)
D_FLASH_DUREE = definir(
    "cs2.flash.duree_aveuglement_adversaires",
    1,
    "s",
    "Durée totale d'aveuglement infligée aux adversaires.",
)
D_FLASH_EQUIPE = definir(
    "cs2.flash.coequipiers_aveugles",
    1,
    "joueurs",
    "Coéquipiers aveuglés au moins 1 s par les flashs de Mathieu (lui compris).",
    sens="bas",
)
D_FLASH_CONVERTIE = definir(
    "cs2.flash.part_convertie",
    1,
    "%",
    "Part des flashs suivies, dans les 2 s, d'un kill de l'équipe sur un adversaire aveuglé.",
)
D_FLASH_INUTILE = definir(
    "cs2.flash.part_inutile",
    1,
    "%",
    "Part des flashs qui n'aveuglent aucun adversaire au moins 1 s.",
    sens="bas",
)
D_HE_NB = definir("cs2.he.nombre", 1, "HE", "Grenades HE lancées.", sens="neutre")
D_HE_DEGATS = definir(
    "cs2.he.degats_moyens", 1, "PV", "Dégâts moyens infligés aux adversaires par HE."
)
D_HE_EQUIPE = definir(
    "cs2.he.degats_coequipiers", 1, "PV", "Dégâts infligés aux coéquipiers par les HE.", sens="bas"
)
D_MOLO_NB = definir(
    "cs2.molotov.nombre", 1, "molotovs", "Molotovs et incendiaires lancées.", sens="neutre"
)
D_MOLO_DUREE = definir("cs2.molotov.duree_moyenne", 1, "s", "Durée moyenne du feu.", sens="neutre")
D_MOLO_DEGATS = definir(
    "cs2.molotov.degats_moyens", 1, "PV", "Dégâts moyens infligés aux adversaires par molotov."
)
D_MOLO_DELOGES = definir(
    "cs2.molotov.adversaires_deloges",
    1,
    "joueurs",
    "Nombre moyen d'adversaires présents à moins de 250 u du feu à l'allumage et sortis de "
    "la zone dans les 3 s.",
)
D_GASPI_MORT = definir(
    "cs2.utilitaires.valeur_perdue_par_mort",
    1,
    "$",
    "Valeur moyenne des grenades encore en poche au moment de mourir.",
    sens="bas",
)
D_GASPI_ROUNDS = definir(
    "cs2.utilitaires.part_rounds_sans_lancer",
    1,
    "%",
    "Part des rounds où Mathieu avait des grenades au début et n'en a lancé aucune.",
    sens="bas",
)


def _pct(n: float, total: float) -> float | None:
    return 100.0 * n / total if total else None


def _allies(d: DonneesMatch, pos: Positions, a: str, b: str, tick: int) -> bool:
    if d.est_deathmatch():
        return a == b
    ea, eb = pos.equipe(a, tick), pos.equipe(b, tick)
    return ea is not None and ea == eb


def flashs(d: DonneesMatch, pos: Positions) -> ResultatAnalyse:
    r = ResultatAnalyse()
    mes_flashs = d.grenades[(d.grenades["type"] == "flash") & (d.grenades["lanceur"] == d.moi)]
    if not len(mes_flashs):
        return r
    aveugles = d.aveuglements[d.aveuglements["attaquant"] == d.moi]
    nb_adv, duree_adv, nb_equipe, converties, inutiles = [], 0.0, 0, 0, 0
    for _, f in mes_flashs.iterrows():
        t = int(f["tick"])
        lot = aveugles[
            (aveugles["tick"] >= t) & (aveugles["tick"] <= t + FENETRE_AVEUGLEMENT_TICKS)
        ]
        lot = lot[lot["duree"] >= SEUIL_AVEUGLE_S]
        adv = [v for v in lot.itertuples() if not _allies(d, pos, d.moi, v.victime, t)]
        equipe = [v for v in lot.itertuples() if _allies(d, pos, d.moi, v.victime, t)]
        nb_adv.append(len(adv))
        duree_adv += sum(v.duree for v in adv)
        nb_equipe += len(equipe)
        victimes = {v.victime for v in adv}
        kills = d.morts[
            (d.morts["tick"] >= t)
            & (d.morts["tick"] <= t + FENETRE_CONVERSION_TICKS)
            & d.morts["victime"].isin(victimes)
        ]
        kills = [k for k in kills.itertuples() if _allies(d, pos, d.moi, k.attaquant, t)]
        if kills:
            converties += 1
        rnd = d.numero_round(t)
        if not adv:
            inutiles += 1
            r.preuves.append(
                Preuve(
                    D_FLASH_INUTILE.nom,
                    t,
                    "Flash sans adversaire aveuglé",
                    rnd,
                    {"x": f["x"], "y": f["y"]},
                )
            )
        for v in equipe:
            qui = "Mathieu lui-même" if v.victime == d.moi else _nom(pos, v.victime, t)
            r.preuves.append(
                Preuve(
                    D_FLASH_EQUIPE.nom,
                    t,
                    f"Flash qui aveugle {qui} {v.duree:.1f} s",
                    rnd,
                    {"victime": v.victime, "duree": round(v.duree, 2)},
                )
            )
        if kills:
            r.preuves.append(
                Preuve(
                    D_FLASH_CONVERTIE.nom,
                    t,
                    f"Flash convertie : {len(adv)} aveuglé(s), kill dans les 2 s",
                    rnd,
                )
            )
    n = len(mes_flashs)
    r.mesures += [
        mesure(D_FLASH_NB, n),
        mesure(D_FLASH_ADV, float(np.mean(nb_adv)), n=n),
        mesure(D_FLASH_DUREE, duree_adv, n=n),
        mesure(D_FLASH_EQUIPE, nb_equipe, n=n),
        mesure(D_FLASH_CONVERTIE, _pct(converties, n), n=n),
        mesure(D_FLASH_INUTILE, _pct(inutiles, n), n=n),
    ]
    return r


def _nom(pos: Positions, steamid: str, tick: int) -> str:
    etat = pos.etat(steamid, tick)
    return str(etat["nom"]) if etat is not None else steamid


def he(d: DonneesMatch, pos: Positions) -> ResultatAnalyse:
    r = ResultatAnalyse()
    mes_he = d.grenades[(d.grenades["type"] == "he") & (d.grenades["lanceur"] == d.moi)]
    if not len(mes_he):
        return r
    degats = d.degats[(d.degats["attaquant"] == d.moi) & (d.degats["arme"] == "hegrenade")]
    par_he, sur_equipe = [], 0.0
    for _, g in mes_he.iterrows():
        t = int(g["tick"])
        lot = degats[(degats["tick"] >= t) & (degats["tick"] <= t + FENETRE_DEGATS_HE_TICKS)]
        adv = sum(x.degats for x in lot.itertuples() if not _allies(d, pos, d.moi, x.victime, t))
        sur_equipe += sum(
            x.degats
            for x in lot.itertuples()
            if x.victime != d.moi and _allies(d, pos, d.moi, x.victime, t)
        )
        par_he.append(adv)
        r.preuves.append(
            Preuve(
                D_HE_DEGATS.nom,
                t,
                f"HE : {adv:.0f} dégâts aux adversaires",
                d.numero_round(t),
                {"degats": adv},
            )
        )
    r.mesures += [
        mesure(D_HE_NB, len(mes_he)),
        mesure(D_HE_DEGATS, float(np.mean(par_he)), n=len(mes_he)),
        mesure(D_HE_EQUIPE, sur_equipe, n=len(mes_he)),
    ]
    r.preuves = sorted(r.preuves, key=lambda p: p.donnees["degats"])[:NB_PREUVES]
    return r


def molotovs(d: DonneesMatch, pos: Positions) -> ResultatAnalyse:
    r = ResultatAnalyse()
    mes_molos = d.grenades[(d.grenades["type"] == "molotov") & (d.grenades["lanceur"] == d.moi)]
    if not len(mes_molos):
        return r
    degats = d.degats[(d.degats["attaquant"] == d.moi) & d.degats["arme"].isin(ARMES_FEU)]
    durees, par_molo, deloges = [], [], []
    for _, g in mes_molos.iterrows():
        t, fin = int(g["tick"]), int(g["fin"])
        durees.append((fin - t) / TICKS_PAR_SECONDE)
        lot = degats[(degats["tick"] >= t) & (degats["tick"] <= fin)]
        par_molo.append(
            sum(x.degats for x in lot.itertuples() if not _allies(d, pos, d.moi, x.victime, t))
        )
        sortis = []
        for sid in pos.joueurs():
            if sid == d.moi or _allies(d, pos, d.moi, sid, t):
                continue
            avant = pos.etat(sid, t)
            if avant is None or not bool(avant["vivant"]):
                continue
            if np.hypot(avant["x"] - g["x"], avant["y"] - g["y"]) > RAYON_MOLOTOV:
                continue
            apres = pos.etat(sid, min(fin, t + DELAI_DELOGE_TICKS))
            if (
                apres is not None
                and bool(apres["vivant"])
                and np.hypot(apres["x"] - g["x"], apres["y"] - g["y"]) > RAYON_MOLOTOV
            ):
                sortis.append(str(avant["nom"]))
        deloges.append(len(sortis))
        texte = f"Molotov : {durees[-1]:.1f} s de feu, {par_molo[-1]:.0f} dégâts"
        if sortis:
            texte += f", a délogé {', '.join(sortis)}"
        r.preuves.append(
            Preuve(
                D_MOLO_DELOGES.nom,
                t,
                texte,
                d.numero_round(t),
                {"deloges": sortis, "degats": par_molo[-1]},
            )
        )
    n = len(mes_molos)
    r.mesures += [
        mesure(D_MOLO_NB, n),
        mesure(D_MOLO_DUREE, float(np.mean(durees)), n=n),
        mesure(D_MOLO_DEGATS, float(np.mean(par_molo)), n=n),
        mesure(D_MOLO_DELOGES, float(np.mean(deloges)), n=n),
    ]
    return r


def _inventaire(d: DonneesMatch, tick: int) -> list[str] | None:
    inv = d.inventaires[(d.inventaires["steamid"] == d.moi) & (d.inventaires["tick"] == tick)]
    return list(inv["grenades"].iloc[0]) if len(inv) else None


def gaspillage(d: DonneesMatch) -> ResultatAnalyse:
    r = ResultatAnalyse()
    if d.est_deathmatch() or not len(d.inventaires):
        return r
    mes_morts = d.morts[d.morts["victime"] == d.moi]
    valeurs = []
    for _, m in mes_morts.iterrows():
        poche = _inventaire(d, max(0, int(m["tick"]) - 1))
        if poche is None:
            continue
        valeur = sum(PRIX_GRENADES.get(g, 0) for g in poche)
        valeurs.append(valeur)
        if valeur >= 500:
            r.preuves.append(
                Preuve(
                    D_GASPI_MORT.nom,
                    int(m["tick"]),
                    f"Mort avec {valeur} $ de grenades en poche ({', '.join(poche)})",
                    d.numero_round(int(m["tick"])),
                    {"grenades": poche, "valeur": valeur},
                )
            )
    if valeurs:
        r.mesures.append(
            mesure(D_GASPI_MORT, float(np.mean(valeurs)), n=len(valeurs), total=float(sum(valeurs)))
        )

    mes_lancers = d.lancers[d.lancers["steamid"] == d.moi]
    if not len(mes_lancers):  # repli : éclatements de grenades
        mes_lancers = d.grenades[d.grenades["lanceur"] == d.moi]
    avec, sans = 0, 0
    for _, rnd in d.rounds.iterrows():
        poche = _inventaire(d, int(rnd["debut"]))
        if not poche:
            continue
        avec += 1
        lances = mes_lancers[
            (mes_lancers["tick"] >= rnd["debut"]) & (mes_lancers["tick"] <= rnd["fin"])
        ]
        if not len(lances):
            sans += 1
            r.preuves.append(
                Preuve(
                    D_GASPI_ROUNDS.nom,
                    int(rnd["debut"]),
                    f"Round {int(rnd['numero'])} : aucune grenade lancée sur {', '.join(poche)}",
                    int(rnd["numero"]),
                    {"grenades": poche},
                )
            )
    if avec:
        r.mesures.append(mesure(D_GASPI_ROUNDS, _pct(sans, avec), n=avec))
    return r


def analyser_utilitaires(d: DonneesMatch, pos: Positions | None = None) -> ResultatAnalyse:
    pos = pos or Positions(d.ticks)
    r = ResultatAnalyse()
    for analyse in (flashs, he, molotovs):
        r.etendre(analyse(d, pos))
    r.etendre(gaspillage(d))
    return r
