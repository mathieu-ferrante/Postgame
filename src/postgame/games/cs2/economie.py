"""Économie CS2 (lot L4 : CS-ECO-01).

On relève l'équipement et l'argent de chaque joueur à la fin de la période d'achat
(20 s après le freeze), juste avant chaque mort et en fin de round.

Type d'achat d'après la valeur d'équipement (seuils usuels des outils d'analyse) :
éco < 1 500 $, partiel (force) de 1 500 à 3 999 $, complet ≥ 4 000 $. Pour l'équipe, on
classe la valeur moyenne de ses joueurs. Les rounds pistolet (1 et 13) sont à part.
"""

from __future__ import annotations

import numpy as np

from postgame.games.cs2.decisions import ROUNDS_PAR_MOITIE, Round, decouper_rounds
from postgame.games.cs2.donnees import DELAI_INSTALLATION_TICKS, DonneesMatch, Positions
from postgame.mesures import Preuve, ResultatAnalyse, definir, mesure

SEUIL_PARTIEL = 1500
SEUIL_COMPLET = 4000
LIBELLES = {"eco": "éco", "partiel": "achat partiel", "complet": "achat complet"}

D_DESYNC = definir(
    "cs2.eco.part_achats_desynchronises",
    1,
    "%",
    "Rounds (hors pistolet) où le type d'achat de Mathieu diffère de celui de son équipe.",
    sens="bas",
)
D_VICTOIRE_TYPE = definir(
    "cs2.eco.taux_victoire_type",
    1,
    "%",
    "Taux de victoire de l'équipe selon son type d'achat (éco, partiel, complet).",
)
D_VALEUR_PERDUE = definir(
    "cs2.eco.valeur_perdue_moyenne",
    1,
    "$",
    "Valeur moyenne de l'équipement de Mathieu au moment de ses morts.",
    sens="neutre",
)
D_ARGENT_RESTANT = definir(
    "cs2.eco.argent_restant_moyen",
    1,
    "$",
    "Argent moyen gardé en poche après les achats, dans les rounds où l'équipe achète complet.",
    sens="neutre",
)
D_PART_TYPE = definir(
    "cs2.eco.part_rounds_type",
    1,
    "%",
    "Répartition des rounds de Mathieu par type d'achat.",
    sens="neutre",
)


def type_achat(valeur: float) -> str:
    if valeur >= SEUIL_COMPLET:
        return "complet"
    if valeur >= SEUIL_PARTIEL:
        return "partiel"
    return "eco"


def est_pistolet(numero: int) -> bool:
    return numero in (1, ROUNDS_PAR_MOITIE + 1)


def _pct(n: float, total: float) -> float | None:
    return 100.0 * n / total if total else None


def analyser_economie(
    d: DonneesMatch, pos: Positions | None = None, rounds: list[Round] | None = None
) -> ResultatAnalyse:
    r = ResultatAnalyse()
    if d.est_deathmatch() or not len(d.economie):
        return r
    pos = pos or Positions(d.ticks)
    rounds = rounds if rounds is not None else decouper_rounds(d, pos)

    desync, comptes, victoires, restants = [], {}, {}, []
    for rnd in rounds:
        t = rnd.debut + DELAI_INSTALLATION_TICKS
        lot = d.economie[d.economie["tick"] == t]
        if not len(lot):
            continue
        equipe = lot[lot["steamid"].isin(rnd.vivants_debut[rnd.mon_equipe])]
        moi = lot[lot["steamid"] == d.moi]
        if not len(moi) or not len(equipe):
            continue
        ma_valeur = int(moi["valeur_equipement"].iloc[0])
        moyenne = float(equipe["valeur_equipement"].mean())
        mon_type, type_equipe = type_achat(ma_valeur), type_achat(moyenne)
        comptes[mon_type] = comptes.get(mon_type, 0) + 1
        if rnd.gagne is not None and not est_pistolet(rnd.numero):
            victoires.setdefault(type_equipe, []).append(rnd.gagne)
        if type_equipe == "complet":
            restants.append(int(moi["argent"].iloc[0]))
        if est_pistolet(rnd.numero):
            continue
        different = mon_type != type_equipe
        desync.append(different)
        if different:
            r.preuves.append(
                Preuve(
                    D_DESYNC.nom,
                    t,
                    f"Round {rnd.numero} : Mathieu en {LIBELLES[mon_type]} ({ma_valeur} $) alors "
                    f"que l'équipe est en {LIBELLES[type_equipe]} (moyenne {moyenne:.0f} $)",
                    rnd.numero,
                    {"valeur": ma_valeur, "moyenne_equipe": round(moyenne)},
                )
            )
    if desync:
        r.mesures.append(mesure(D_DESYNC, _pct(sum(desync), len(desync)), n=len(desync)))
    total = sum(comptes.values())
    for type_, nb in sorted(comptes.items()):
        r.mesures.append(mesure(D_PART_TYPE, _pct(nb, total), type=type_, n=total))
    for type_, lot in sorted(victoires.items()):
        r.mesures.append(mesure(D_VICTOIRE_TYPE, _pct(sum(lot), len(lot)), type=type_, n=len(lot)))
    if restants:
        r.mesures.append(mesure(D_ARGENT_RESTANT, float(np.mean(restants)), n=len(restants)))

    valeurs = []
    for rnd in rounds:
        if rnd.ma_mort is None:
            continue
        ligne = d.economie[
            (d.economie["steamid"] == d.moi) & (d.economie["tick"] == rnd.ma_mort - 1)
        ]
        if len(ligne):
            valeurs.append(int(ligne["valeur_equipement"].iloc[0]))
    if valeurs:
        r.mesures.append(
            mesure(
                D_VALEUR_PERDUE, float(np.mean(valeurs)), n=len(valeurs), total=float(sum(valeurs))
            )
        )
    return r
