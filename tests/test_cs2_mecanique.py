"""Mesures de mécanique CS2 sur scénarios synthétiques calculés à la main (L1).

Ces tests valident les calculs. La validation sur vraie démo (5 cas vérifiés à la main
par mesure) reste à faire : voir A_VALIDER.md.
"""

import math

import pytest
from fabrique_cs2 import ADV, ADV2, MOI, Scenario

from postgame.games.cs2 import mecanique as m
from postgame.games.cs2.geometrie import angle_entre, direction, ecart_angulaire


def _valeur(resultat, nom, **contexte):
    for mes in resultat.mesures:
        if (
            mes.nom == nom
            and all(mes.contexte.get(k) == v for k, v in contexte.items())
            and (contexte or "arme" not in mes.contexte and "tranche" not in mes.contexte)
        ):
            return mes.valeur
    raise AssertionError(f"mesure absente : {nom} {contexte}")


# --- Géométrie ----------------------------------------------------------------------------


def test_geometrie_conventions():
    # Cible devant, à gauche (y positif) : yaw positif ; cible plus haute : pitch négatif.
    assert direction(100, 0, 0) == (0.0, -0.0)
    yaw, pitch = direction(100, 100, 0)
    assert yaw == pytest.approx(45)
    _, pitch = direction(100, 0, 100)
    assert pitch == pytest.approx(-45)
    assert ecart_angulaire(350, 10) == pytest.approx(-20)
    assert ecart_angulaire(-170, 170) == pytest.approx(20)
    # cos θ = cos 5° × cos 10° (calcul à la main) → 11,17°
    assert angle_entre(0, 5, 10, 0) == pytest.approx(11.17, abs=0.01)


# --- CS-AIM-01 : contre-strafe ------------------------------------------------------------


def _scenario_tirs():
    """4 tirs d'AK isolés (engagements distincts) à 0, 50, 73 et 150 u/s.
    Seuil AK = 215 × 0,34 = 73,1 u/s → 3 tirs précis sur 4."""
    s = Scenario(nb_ticks=600)
    s.joueur(MOI, equipe=2)
    s.joueur(ADV, equipe=3, x=1000)
    for tick, vitesse in [(100, 0), (200, 50), (300, 73), (400, 150)]:
        s.regler(MOI, tick - 5, tick, vx=vitesse)
        s.tir(MOI, tick)
    return s


def test_contre_strafe():
    d = _scenario_tirs().donnees()
    r = m.contre_strafe(d, m.preparer_tirs(d))
    assert _valeur(r, "cs2.contre_strafe.part_tirs_precis") == 75.0
    assert _valeur(r, "cs2.contre_strafe.part_tirs_precis", arme="ak47") == 75.0
    assert _valeur(r, "cs2.contre_strafe.part_premieres_balles_precises") == 75.0
    # médiane de 0, 50, 73, 150 = 61,5
    assert _valeur(r, "cs2.contre_strafe.vitesse_mediane_premiere_balle") == 61.5
    assert [p.tick for p in r.preuves] == [400]
    assert "150 u/s" in r.preuves[0].texte


def test_contre_strafe_ignore_pompes_et_autres_joueurs():
    s = _scenario_tirs()
    s.tir(MOI, 500, "nova")
    s.tir(ADV, 450)
    d = s.donnees()
    r = m.contre_strafe(d, m.preparer_tirs(d))
    assert _valeur(r, "cs2.contre_strafe.part_tirs_precis") == 75.0


# --- CS-AIM-02 : première balle -----------------------------------------------------------


def test_premiere_balle():
    s = _scenario_tirs()
    s.touche(MOI, ADV, 100, zone="tete")
    s.touche(MOI, ADV, 201, zone="torse")  # 1 tick après le tir : rattaché
    s.touche(MOI, ADV, 305, zone="tete")  # 5 ticks après : hors fenêtre, ignoré
    d = s.donnees()
    tirs = m.preparer_tirs(d)
    assert tirs["touche"].tolist() == [True, True, False, False]
    r = m.premiere_balle(d, tirs)
    assert _valeur(r, "cs2.premiere_balle.precision") == 50.0
    assert _valeur(r, "cs2.premiere_balle.headshot") == 25.0


def test_engagements_et_rafales():
    s = Scenario(nb_ticks=400)
    s.joueur(MOI)
    # Rafale de 4, tir isolé 72 ticks plus tard, puis un autre 40 ticks après (> 32 : nouvel
    # engagement).
    for tick in [10, 16, 22, 28, 100, 140]:
        s.tir(MOI, tick)
    tirs = m.preparer_tirs(s.donnees())
    assert tirs["premiere"].tolist() == [True, False, False, False, True, True]
    assert tirs["balle"].tolist() == [1, 2, 3, 4, 1, 1]


# --- CS-AIM-03 : spray --------------------------------------------------------------------


def _scenario_spray(nb_rafales=3):
    """Rafales d'AK de 10 balles (1 toutes les 6 ticks) sur un adversaire immobile à
    1000 u devant. Balles 1-5 : recul compensé (erreur 0°, touchent). Balles 6-10 : recul
    non compensé, aim punch −1,5° → tir 3° au-dessus de la tête (manquent)."""
    s = Scenario(nb_ticks=1000)
    s.joueur(MOI, equipe=2)
    s.joueur(ADV, equipe=3, x=1000)
    for r in range(nb_rafales):
        debut = 100 + 200 * r
        for b in range(10):
            tick = debut + 6 * b
            s.tir(MOI, tick)
            if b < 5:
                s.touche(MOI, ADV, tick)
            else:
                s.regler(MOI, tick, tick + 5, punch_pitch=-1.5)
    return s


def test_spray_decrochage_et_tranches():
    d = _scenario_spray().donnees()
    tirs = m.preparer_tirs(d)
    r = m.spray(d, tirs, m._Positions(d.ticks))
    assert _valeur(r, "cs2.spray.balle_decrochage") == 6
    assert _valeur(r, "cs2.spray.touche_par_tranche", tranche="2-5") == 100.0
    assert _valeur(r, "cs2.spray.touche_par_tranche", tranche="6-10") == 0.0
    assert _valeur(r, "cs2.spray.erreur_mediane_par_tranche", tranche="1") == pytest.approx(
        0, abs=1e-6
    )
    assert _valeur(r, "cs2.spray.erreur_mediane_par_tranche", tranche="6-10") == pytest.approx(3.0)


def test_spray_pas_assez_de_rafales():
    d = _scenario_spray(nb_rafales=2).donnees()
    r = m.spray(d, m.preparer_tirs(d), m._Positions(d.ticks))
    assert _valeur(r, "cs2.spray.balle_decrochage") is None


# --- CS-AIM-04/05 : apparitions, viseur, réaction, TTK -------------------------------------


def _scenario_apparition():
    """L'adversaire, à 1000 u devant et 10° à gauche, devient visible au tick 1000.
    Le joueur regarde droit devant, 5° vers le bas. Il tire dans sa direction 16 ticks
    plus tard (250 ms) et le tue 24 ticks après ce tir (375 ms)."""
    s = Scenario(nb_ticks=1400)
    s.joueur(MOI, equipe=2, pitch=5.0)
    y = 1000 * math.tan(math.radians(10))
    s.joueur(ADV, equipe=3, nom="Adversaire", x=1000, y=y)
    s.regler(ADV, 1000, 1100, vu_par_moi=True)
    s.regler(MOI, 1016, 1100, yaw=10.0, pitch=0.0)
    s.tir(MOI, 1016)
    s.touche(MOI, ADV, 1016)
    s.mort(MOI, ADV, 1040, headshot=True)
    s.regler(ADV, 1041, 1399, vivant=False)
    return s


def test_apparition_placement_viseur():
    d = _scenario_apparition().donnees()
    tirs = m.preparer_tirs(d)
    apps = m.apparitions(d, tirs, m._Positions(d.ticks))
    assert len(apps) == 1
    a = apps[0]
    assert a.tick == 1000
    assert a.ecart == pytest.approx(11.17, abs=0.01)
    assert a.ecart_vertical == pytest.approx(5.0)  # trop bas
    assert a.ecart_horizontal == pytest.approx(-10.0)  # viseur à droite de la tête
    assert a.reaction_ms == 250.0
    assert a.ttk_ms == 375.0


def test_viseur_et_reaction_mesures():
    d = _scenario_apparition().donnees()
    r = m.viseur_et_reaction(d, m.preparer_tirs(d), m._Positions(d.ticks))
    assert _valeur(r, "cs2.viseur.ecart_median") == pytest.approx(11.17, abs=0.01)
    assert _valeur(r, "cs2.viseur.part_ecart_sous_5deg") == 0.0
    assert _valeur(r, "cs2.reaction.delai_median") == 250.0
    assert _valeur(r, "cs2.ttk.median") == 375.0
    texte = next(p.texte for p in r.preuves if p.mesure == "cs2.viseur.ecart_median")
    assert "Adversaire" in texte and "à droite" in texte and "trop bas" in texte


def test_reapparition_et_coequipier():
    s = _scenario_apparition()
    # Disparition de 20 ticks (< 32) : même épisode ; puis de 40 ticks : nouvel épisode.
    s.regler(ADV, 1000, 1399, vivant=True)
    s.morts.clear()
    s.regler(ADV, 1101, 1120, vu_par_moi=False)
    s.regler(ADV, 1121, 1150, vu_par_moi=True)
    s.regler(ADV, 1151, 1190, vu_par_moi=False)
    s.regler(ADV, 1191, 1200, vu_par_moi=True)
    # Un coéquipier « repéré » ne compte pas en match à rounds.
    s.joueur(ADV2, equipe=2, x=500, vu_par_moi=True)
    s.debuts_rounds = [0, 1300]
    d = s.donnees()
    apps = m.apparitions(d, m.preparer_tirs(d), m._Positions(d.ticks))
    assert [a.tick for a in apps] == [1000, 1191]


def test_pas_d_apparition_si_mort():
    s = _scenario_apparition()
    s.regler(MOI, 900, 1399, vivant=False)
    d = s.donnees()
    assert m.apparitions(d, m.preparer_tirs(d), m._Positions(d.ticks)) == []


def test_pitch_en_deplacement():
    s = Scenario(nb_ticks=300)
    s.joueur(MOI, pitch=8.0)
    s.regler(MOI, 0, 99, vx=250.0)  # 100 ticks en déplacement à 8°
    s.regler(MOI, 100, 299, pitch=-3.0)  # immobile : ignoré
    d = s.donnees()
    r = m.viseur_et_reaction(d, m.preparer_tirs(d), m._Positions(d.ticks))
    assert _valeur(r, "cs2.viseur.pitch_median_deplacement") == 8.0


# --- CS-AIM-06 : armes --------------------------------------------------------------------


def test_par_arme():
    s = _scenario_tirs()  # 4 tirs d'AK
    s.tir(MOI, 500, "deagle")
    s.touche(MOI, ADV, 100, degats=100, zone="tete")
    s.touche(MOI, ADV, 500, "deagle", degats=40)
    s.mort(MOI, ADV, 100, headshot=True)
    s.mort(MOI, ADV2, 300, "ak47")
    s.mort(ADV, MOI, 550, "awp")  # mort subie : ne compte pas
    d = s.donnees()
    r = m.par_arme(d, m.preparer_tirs(d))
    assert _valeur(r, "cs2.armes.kills", arme="ak47") == 2
    assert _valeur(r, "cs2.armes.headshot", arme="ak47") == 50.0
    assert _valeur(r, "cs2.armes.precision", arme="ak47") == 25.0
    assert _valeur(r, "cs2.armes.degats", arme="ak47") == 100
    assert _valeur(r, "cs2.armes.precision", arme="deagle") == 100.0
    assert _valeur(r, "cs2.armes.kills", arme="deagle") == 0
    assert _valeur(r, "cs2.armes.precision") == 40.0  # 2 touches sur 5 tirs
    assert _valeur(r, "cs2.armes.headshot") == 50.0


def test_analyse_complete_sans_tir():
    s = Scenario(nb_ticks=100)
    s.joueur(MOI)
    r = m.analyser_mecanique(s.donnees())
    assert all(mes.nom.startswith("cs2.") for mes in r.mesures)


def test_analyse_complete_scenario_riche():
    s = _scenario_spray()
    r = m.analyser_mecanique(s.donnees())
    noms = {mes.nom for mes in r.mesures}
    assert {
        "cs2.contre_strafe.part_tirs_precis",
        "cs2.premiere_balle.precision",
        "cs2.spray.balle_decrochage",
        "cs2.armes.kills",
    } <= noms
