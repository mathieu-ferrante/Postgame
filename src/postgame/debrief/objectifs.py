"""Cibles et poids des mesures pour estimer l'impact d'un constat (COM-06).

CIBLES PROVISOIRES : ordres de grandeur raisonnables pour un joueur qui progresse, pas
des références mesurées. Elles seront remplacées par les médianes des pros calculées sur
les démos pros (L3) quand le catalogue sera assez fourni. En attendant, la référence
principale d'un constat reste la moyenne personnelle de Mathieu.

`echelle` : écart qui vaut « une unité d'impact » (10 points de %, 50 ms, 2°…).
`poids` : importance relative pour gagner des rounds (2 = mesure phare du cahier des charges).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Objectif:
    cible: float | None
    echelle: float
    poids: float = 1.0


OBJECTIFS: dict[str, Objectif] = {
    "cs2.contre_strafe.part_premieres_balles_precises": Objectif(80, 10, 2.0),
    "cs2.contre_strafe.part_tirs_precis": Objectif(75, 10, 1.0),
    "cs2.contre_strafe.vitesse_mediane_premiere_balle": Objectif(50, 20, 1.0),
    "cs2.premiere_balle.precision": Objectif(None, 10, 1.5),
    "cs2.premiere_balle.headshot": Objectif(None, 10, 1.5),
    "cs2.spray.balle_decrochage": Objectif(8, 2, 1.0),
    "cs2.viseur.ecart_median": Objectif(5, 2, 2.0),
    "cs2.viseur.part_ecart_sous_5deg": Objectif(50, 10, 1.5),
    "cs2.reaction.delai_median": Objectif(300, 50, 1.0),
    "cs2.ttk.median": Objectif(None, 100, 0.5),
    "cs2.flash.part_inutile": Objectif(30, 10, 1.0),
    "cs2.flash.part_convertie": Objectif(None, 10, 1.0),
    "cs2.flash.coequipiers_aveugles": Objectif(0, 1, 1.0),
    "cs2.he.degats_moyens": Objectif(None, 10, 0.5),
    "cs2.molotov.adversaires_deloges": Objectif(None, 0.5, 0.5),
    "cs2.utilitaires.valeur_perdue_par_mort": Objectif(200, 150, 1.0),
    "cs2.utilitaires.part_rounds_sans_lancer": Objectif(20, 10, 1.0),
    "cs2.position.part_morts_isolees": Objectif(30, 10, 1.0),
    "cs2.trades.part_tradables_non_tradees": Objectif(30, 10, 1.5),
    "cs2.trades.occasions_manquees": Objectif(0, 2, 1.0),
    "cs2.smoke.part_reconnues": Objectif(70, 10, 1.5),
    "cs2.smoke.part_ligne_coupee": Objectif(None, 10, 1.0),
    "cs2.position.part_positions_pro": Objectif(None, 10, 1.0),
    "cs2.ouverture.taux_victoire": Objectif(50, 10, 1.0),
    "cs2.save.part_morts_inutiles": Objectif(30, 15, 1.0),
    "cs2.eco.part_achats_desynchronises": Objectif(10, 10, 1.0),
    "cs2.rotation.delai_median": Objectif(None, 2, 0.5),
}

ECHELLES_PAR_UNITE = {
    "%": 10.0,
    "ms": 50.0,
    "°": 2.0,
    "u": 200.0,
    "$": 300.0,
    "s": 2.0,
    "u/s": 20.0,
}


def objectif(nom: str, unite: str, reference: float | None) -> Objectif:
    if nom in OBJECTIFS:
        return OBJECTIFS[nom]
    echelle = ECHELLES_PAR_UNITE.get(unite)
    if echelle is None:
        echelle = max(abs(reference) * 0.25, 1.0) if reference is not None else 1.0
    return Objectif(None, echelle, 1.0)
