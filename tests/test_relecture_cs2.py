"""Défauts trouvés en relecture des analyses CS2 (cas construits d'après les vraies démos)."""

import pandas as pd
from fabrique_cs2 import ADV, COEQ, MOI, Scenario

from postgame.games.cs2.decisions import analyser_decisions
from postgame.games.cs2.donnees import construire_rounds
from postgame.games.cs2.geometrie import distance_3d
from postgame.games.cs2.mecanique import adversaires_seulement, preparer_tirs
from postgame.games.cs2.positionnement import analyser_positionnement


def test_lunette_lue_avant_le_tir():
    # Vraie démo : lunette ouverte jusqu'au tick précédent, déjà refermée au tick du tir.
    s = Scenario(nb_ticks=300)
    s.joueur(MOI, equipe=2, arme="awp")
    s.joueur(ADV, equipe=3, x=1000)
    s.regler(MOI, 50, 199, lunette=True)
    s.tir(MOI, 200, "awp")
    assert bool(preparer_tirs(s.donnees())["lunette"].iloc[0]) is True


def test_round_sans_fin_borne_a_la_demo():
    r = construire_rounds([100, 5000], [3000], dernier_tick=9000)
    assert r["fin"].tolist() == [3000, 9000]


def test_mi_temps_wingman():
    s = Scenario(nb_ticks=20000)
    s.debuts_rounds = [1000 * i for i in range(1, 17)]
    s.fins_rounds = [1000 * i + 900 for i in range(1, 17)]
    s.joueur(MOI, equipe=2)
    s.regler(MOI, 8950, 20000, equipe=3)  # changement de camp après 8 rounds
    assert s.donnees().rounds_par_moitie() == 8


def test_distance_3d_etages():
    # Nuke : un coéquipier juste au-dessus, 400 u plus haut, n'est pas « à côté ».
    assert distance_3d({"x": 0, "y": 0, "z": -400}, {"x": 30, "y": 0, "z": 0}) > 400


def test_mort_par_la_bombe_ni_duel_ni_mort_isolee():
    s = Scenario(nb_ticks=8000)
    s.debuts_rounds, s.fins_rounds = [0, 4000], [3800, 7800]
    s.joueur(MOI, equipe=2)
    s.joueur(COEQ, equipe=2, x=5000)
    s.joueur(ADV, equipe=3, x=1000)
    s.mort("", MOI, 1000, arme="planted_c4")  # tué par la bombe
    s.regler(MOI, 1000, 4000, vivant=False)
    s.mort(ADV, COEQ, 2000)  # le vrai premier duel du round
    d = s.donnees()
    noms = {m.nom: m for m in analyser_decisions(d).mesures}
    assert noms["cs2.ouverture.part_impliquee"].valeur == 0.0
    assert "cs2.position.part_morts_isolees" not in {
        m.nom for m in analyser_positionnement(d).mesures
    }


def test_kills_sur_coequipiers_hors_stats_d_armes():
    s = Scenario(nb_ticks=300)
    s.debuts_rounds, s.fins_rounds = [0, 150], [140, 290]
    s.joueur(MOI, equipe=2)
    s.joueur(COEQ, equipe=2)
    s.joueur(ADV, equipe=3)
    morts = pd.DataFrame(
        {"tick": [100, 200], "attaquant": [MOI, MOI], "victime": [COEQ, ADV], "arme": "ak47"}
    )
    assert adversaires_seulement(s.donnees(), morts)["victime"].tolist() == [ADV]
