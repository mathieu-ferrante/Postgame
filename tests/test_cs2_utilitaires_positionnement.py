"""Utilitaires et positionnement CS2 (L2) sur scénarios synthétiques calculés à la main.

DONNÉES DE SUBSTITUTION : la vérification sur une vraie démo Premier reste à faire.
"""

import pandas as pd
import pytest
from fabrique_cs2 import ADV, ADV2, COEQ, MOI, Scenario

from postgame.games.cs2.donnees import Positions, code_grenade, extraire_grenades
from postgame.games.cs2.positionnement import analyser_positionnement
from postgame.games.cs2.utilitaires import flashs, gaspillage, he, molotovs


def _valeur(resultat, nom):
    for mes in resultat.mesures:
        if mes.nom == nom:
            return mes.valeur
    raise AssertionError(f"mesure absente : {nom}")


def _equipe(nb_ticks=2000):
    """Match à 2 rounds (0-900, 1000-1900) : Mathieu et COEQ (T) contre ADV et ADV2 (CT)."""
    s = Scenario(nb_ticks=nb_ticks)
    s.debuts_rounds, s.fins_rounds = [0, 1000], [900, 1900]
    s.joueur(MOI, equipe=2, nom="Mathieu")
    s.joueur(COEQ, equipe=2, nom="Coequipier", x=500)
    s.joueur(ADV, equipe=3, nom="Adv1", x=1000)
    s.joueur(ADV2, equipe=3, nom="Adv2", x=2000)
    return s


def _pos(d):
    return Positions(d.ticks)


# --- Flashs -------------------------------------------------------------------------------


def test_flashs():
    s = _equipe()
    s.grenade(MOI, 100, "flash")
    s.aveugle(MOI, ADV, 100, 2.5)
    s.aveugle(MOI, ADV2, 100, 0.5)  # < 1 s : ne compte pas
    s.aveugle(MOI, COEQ, 101, 1.2)
    s.mort(COEQ, ADV, 150)  # 50 ticks après : flash convertie
    s.grenade(MOI, 400, "flash")  # n'aveugle personne
    s.grenade(ADV, 500, "flash")  # pas à Mathieu
    d = s.donnees()
    r = flashs(d, _pos(d))
    assert _valeur(r, "cs2.flash.nombre") == 2
    assert _valeur(r, "cs2.flash.adversaires_aveugles_par_flash") == 0.5
    assert _valeur(r, "cs2.flash.duree_aveuglement_adversaires") == 2.5
    assert _valeur(r, "cs2.flash.coequipiers_aveugles") == 1
    assert _valeur(r, "cs2.flash.part_convertie") == 50.0
    assert _valeur(r, "cs2.flash.part_inutile") == 50.0
    textes = [p.texte for p in r.preuves]
    assert any("Coequipier" in t for t in textes)


# --- HE et molotovs -----------------------------------------------------------------------


def test_he():
    s = _equipe()
    s.grenade(MOI, 200, "he")
    s.touche(MOI, ADV, 200, "hegrenade", degats=40)
    s.touche(MOI, ADV2, 201, "hegrenade", degats=25)
    s.touche(MOI, COEQ, 200, "hegrenade", degats=10)
    s.grenade(MOI, 600, "he")
    d = s.donnees()
    r = he(d, _pos(d))
    assert _valeur(r, "cs2.he.nombre") == 2
    assert _valeur(r, "cs2.he.degats_moyens") == 32.5
    assert _valeur(r, "cs2.he.degats_coequipiers") == 10


def test_molotov_deloge():
    s = _equipe()
    s.regler(ADV, 0, 399, x=100)  # dans le feu à l'allumage…
    s.regler(ADV, 400, 1999, x=400)  # … et sorti 100 ticks plus tard
    s.grenade(MOI, 300, "molotov", x=0, y=0, fin=300 + 448)
    s.touche(MOI, ADV, 320, "inferno", degats=12)
    d = s.donnees()
    r = molotovs(d, _pos(d))
    assert _valeur(r, "cs2.molotov.duree_moyenne") == 7.0
    assert _valeur(r, "cs2.molotov.degats_moyens") == 12
    assert _valeur(r, "cs2.molotov.adversaires_deloges") == 1
    assert "Adv1" in r.preuves[0].texte


# --- Gaspillage ---------------------------------------------------------------------------


def test_gaspillage():
    s = _equipe()
    s.grenade(MOI, 100, "flash")  # lancée au tick 36, dans le round 1
    s.mort(ADV, MOI, 800)
    s.inventaire(MOI, 799, ["flash", "smoke", "he"])  # 200 + 300 + 300
    s.inventaire(MOI, 0, ["flash", "molotov"])
    s.inventaire(MOI, 1000, ["smoke"])  # rien lancé au round 2
    d = s.donnees()
    r = gaspillage(d)
    assert _valeur(r, "cs2.utilitaires.valeur_perdue_par_mort") == 800
    assert _valeur(r, "cs2.utilitaires.part_rounds_sans_lancer") == 50.0
    assert any(p.round == 2 for p in r.preuves)


def test_gaspillage_ignore_deathmatch():
    s = Scenario(nb_ticks=100)
    s.joueur(MOI)
    s.inventaire(MOI, 0, ["flash"])
    assert gaspillage(s.donnees()).mesures == []


# --- Positionnement -----------------------------------------------------------------------


def _scenario_trades():
    s = _equipe()
    # Round 1 : Adv1 tue Mathieu (Coequipier à 500 u), Coequipier le venge 100 ticks après.
    s.mort(ADV, MOI, 500)
    s.regler(MOI, 500, 999, vivant=False)
    s.mort(COEQ, ADV, 600)
    s.regler(ADV, 600, 999, vivant=False)
    # Round 2 : Adv2 tue Coequipier, Mathieu le venge 100 ticks après (1562,5 ms).
    s.mort(ADV2, COEQ, 1100)
    s.regler(COEQ, 1100, 1999, vivant=False)
    s.mort(MOI, ADV2, 1200)
    s.regler(ADV2, 1200, 1999, vivant=False)
    # Puis Adv1 tue Mathieu, seul (aucun coéquipier vivant).
    s.mort(ADV, MOI, 1500)
    s.regler(MOI, 1500, 1999, vivant=False)
    return s


def test_trades_et_isolement():
    r = analyser_positionnement(_scenario_trades().donnees())
    assert _valeur(r, "cs2.trades.part_morts_tradees") == 50.0
    assert _valeur(r, "cs2.position.part_morts_isolees") == 50.0
    assert _valeur(r, "cs2.position.distance_coequipier_a_la_mort") == 500.0
    assert _valeur(r, "cs2.trades.part_tradables_non_tradees") == 0.0
    assert _valeur(r, "cs2.trades.reussis") == 1
    assert _valeur(r, "cs2.trades.delai_median") == pytest.approx(1562.5)
    assert _valeur(r, "cs2.trades.occasions_manquees") == 0
    kills = [p for p in r.preuves if p.mesure == "cs2.position.kill"]
    morts = [p for p in r.preuves if p.mesure == "cs2.position.mort"]
    assert len(kills) == 1 and len(morts) == 2
    assert morts[0].donnees["camp"] == "T" and morts[0].donnees["carte"] == "de_test"


def test_occasion_manquee_et_mort_non_vengee():
    s = _equipe()
    s.mort(ADV2, COEQ, 1100)  # Coequipier meurt à 500 u de Mathieu, personne ne le venge
    s.regler(COEQ, 1100, 1999, vivant=False)
    s.mort(ADV, MOI, 300)  # Mathieu meurt avec Coequipier à 500 u, pas vengé
    s.regler(MOI, 300, 999, vivant=False)
    r = analyser_positionnement(s.donnees())
    assert _valeur(r, "cs2.trades.occasions_manquees") == 1
    assert _valeur(r, "cs2.trades.part_tradables_non_tradees") == 100.0
    texte = next(p.texte for p in r.preuves if p.mesure == "cs2.trades.part_tradables_non_tradees")
    assert "Coequipier (500 u)" in texte


def test_positionnement_deathmatch_seulement_chaleur():
    s = Scenario(nb_ticks=200)
    s.joueur(MOI)
    s.joueur(ADV, equipe=3, x=100)
    s.mort(MOI, ADV, 50)
    r = analyser_positionnement(s.donnees())
    assert r.mesures == []
    assert [p.mesure for p in r.preuves] == ["cs2.position.kill"]


# --- Extraction des grenades (pure) -------------------------------------------------------


def test_code_grenade():
    assert code_grenade("Incendiary Grenade") == "molotov"
    assert code_grenade("weapon_flashbang") == "flash"
    assert code_grenade("AK-47") is None


def test_extraire_grenades():
    evts = {
        "smokegrenade_detonate": pd.DataFrame(
            {
                "tick": [100],
                "user_steamid": ["1"],
                "x": [1.0],
                "y": [2.0],
                "z": [3.0],
                "entityid": [42],
            }
        ),
        "smokegrenade_expired": pd.DataFrame({"tick": [1250], "entityid": [42]}),
        "flashbang_detonate": pd.DataFrame(
            {
                "tick": [50],
                "user_steamid": ["2"],
                "x": [0.0],
                "y": [0.0],
                "z": [0.0],
                "entityid": [7],
            }
        ),
        "molotov_detonate": pd.DataFrame(
            {"tick": [300], "user_steamid": [3.0], "x": [10.0], "y": [10.0], "z": [0.0]}
        ),
        "inferno_startburn": pd.DataFrame(
            {"tick": [301], "entityid": [9], "x": [20.0], "y": [15.0], "z": [0.0]}
        ),
        "inferno_expire": pd.DataFrame({"tick": [750], "entityid": [9]}),
    }
    g = extraire_grenades(evts)
    assert g["type"].tolist() == ["flash", "smoke", "molotov"]
    smoke = g[g["type"] == "smoke"].iloc[0]
    assert smoke["fin"] == 1250 and smoke["lanceur"] == "1"
    molo = g[g["type"] == "molotov"].iloc[0]
    assert molo["lanceur"] == "3" and molo["fin"] == 750
