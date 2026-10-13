"""Décisions, stratégie et économie CS2 (L4) sur scénarios synthétiques calculés à la main.

DONNÉES DE SUBSTITUTION : la vérification sur 3 vrais matchs reste à faire.
"""

import pytest
from fabrique_cs2 import ADV, ADV2, COEQ, MOI, Scenario

from postgame.games.cs2.decisions import analyser_decisions, site_depuis_lieu
from postgame.games.cs2.economie import analyser_economie, type_achat

ADV3 = "76561198000000005"
ADV4 = "76561198000000006"


def _valeur(resultat, nom, **contexte):
    for mes in resultat.mesures:
        if mes.nom == nom and all(mes.contexte.get(k) == v for k, v in contexte.items()):
            return mes.valeur
    raise AssertionError(f"mesure absente : {nom} {contexte}")


def _absente(resultat, nom):
    return all(m.nom != nom for m in resultat.mesures)


def _match_2v2():
    """4 rounds de 900 ticks (début tous les 1000). Mathieu et COEQ sont T, ADV et ADV2 CT.
    R1 (gagné) : Mathieu ouvre en tuant ADV. R2 (perdu) : ADV ouvre sur Mathieu.
    R3 (perdu) : ADV tue COEQ → 1v2 de Mathieu, qui tue ADV puis meurt.
    R4 (gagné) : COEQ pose sur BombsiteA, Mathieu (à « Long ») tue ADV après la pose."""
    s = Scenario(nb_ticks=4000)
    s.debuts_rounds = [0, 1000, 2000, 3000]
    s.fins_rounds = [900, 1900, 2900, 3900]
    s.gagnants = {900: 2, 1900: 3, 2900: 3, 3900: 2}
    s.joueur(MOI, equipe=2, nom="Mathieu")
    s.joueur(COEQ, equipe=2, nom="Coequipier", x=300)
    s.joueur(ADV, equipe=3, nom="Adv1", x=2000)
    s.joueur(ADV2, equipe=3, nom="Adv2", x=2500)
    s.mort(MOI, ADV, 100)
    s.mort(COEQ, ADV2, 200)
    s.mort(ADV, MOI, 1100)
    s.mort(ADV, COEQ, 1200)
    s.mort(ADV, COEQ, 2100)
    s.mort(MOI, ADV, 2200)
    s.mort(ADV2, MOI, 2300)
    s.bombe.append({"tick": 3300, "evenement": "pose", "steamid": COEQ})
    s.lieu(COEQ, 3300, "BombsiteA")
    s.lieu(MOI, 3300, "Long")
    s.mort(MOI, ADV, 3400)
    return s


def test_ouvertures():
    r = analyser_decisions(_match_2v2().donnees())
    assert _valeur(r, "cs2.ouverture.part_impliquee") == 75.0
    assert _valeur(r, "cs2.ouverture.taux_victoire") == pytest.approx(200 / 3, abs=1e-3)
    assert _valeur(r, "cs2.ouverture.rounds_gagnes_apres_victoire") == 100.0
    assert _valeur(r, "cs2.ouverture.rounds_gagnes_apres_defaite") == 0.0


def test_clutch():
    r = analyser_decisions(_match_2v2().donnees())
    assert _valeur(r, "cs2.clutch.situations") == 1
    assert _valeur(r, "cs2.clutch.taux_victoire") == 0.0
    assert _valeur(r, "cs2.clutch.taux_victoire", adversaires=2) == 0.0
    texte = next(p.texte for p in r.preuves if p.mesure == "cs2.clutch.taux_victoire")
    assert texte == "Round 3 : 1v2 perdu, 1 kill(s)"


def test_apres_pose():
    r = analyser_decisions(_match_2v2().donnees())
    assert _valeur(r, "cs2.apres_pose.taux_victoire") == 100.0
    assert _valeur(r, "cs2.apres_pose.survie") == 100.0
    assert _valeur(r, "cs2.apres_pose.kills_moyens") == 1.0
    assert _absente(r, "cs2.retake.taux_victoire")
    texte = next(p.texte for p in r.preuves if p.mesure == "cs2.apres_pose.taux_victoire")
    assert "site A" in texte and "à Long" in texte


def test_strategie():
    r = analyser_decisions(_match_2v2().donnees())
    assert _valeur(r, "cs2.strat.part_poses_site", site="A") == 25.0
    assert _valeur(r, "cs2.strat.part_poses_site", site="aucune pose") == 75.0
    assert _valeur(r, "cs2.strat.taux_victoire_site", site="A") == 100.0
    assert _valeur(r, "cs2.strat.repetition_max") == 3
    assert _valeur(r, "cs2.strat.taux_victoire_moitie", moitie="1") == 50.0


def test_site_depuis_lieu():
    assert site_depuis_lieu("BombsiteB") == "B"
    assert site_depuis_lieu("Bombsite A") == "A"
    assert site_depuis_lieu("Palace") == "Palace"
    assert site_depuis_lieu(None) == "?"


def test_saves():
    """2 T (Mathieu, COEQ) contre 4 CT : dès la mort de COEQ, Mathieu est seul contre 4.
    R1 : il survit (sauvegarde). R2 : il meurt sans tuer, avec 4 700 $ d'équipement."""
    s = Scenario(nb_ticks=2000)
    s.debuts_rounds, s.fins_rounds = [0, 1000], [900, 1900]
    s.gagnants = {900: 3, 1900: 3}
    s.joueur(MOI, equipe=2)
    s.joueur(COEQ, equipe=2)
    for sid in (ADV, ADV2, ADV3, ADV4):
        s.joueur(sid, equipe=3, x=2000)
    s.mort(ADV, COEQ, 100)
    s.mort(ADV, COEQ, 1100)
    s.mort(ADV2, MOI, 1300)
    s.eco(MOI, 1299, argent=200, valeur=4700)
    r = analyser_decisions(s.donnees())
    assert _valeur(r, "cs2.save.situations") == 2
    assert _valeur(r, "cs2.save.part_sauvegardes") == 50.0
    assert _valeur(r, "cs2.save.part_morts_inutiles") == 50.0
    assert _valeur(r, "cs2.save.valeur_perdue") == 4700


def test_rotation():
    """Mathieu CT à 2000 u du site au moment de la pose ; il arrive à 1000 u 3 s plus tard."""
    s = Scenario(nb_ticks=1000)
    s.debuts_rounds, s.fins_rounds = [0, 1000], [900, 1900]
    s.gagnants = {900: 3}
    s.joueur(MOI, equipe=3)
    s.joueur(ADV, equipe=2, x=2000)
    s.bombe.append({"tick": 300, "evenement": "pose", "steamid": ADV})
    s.regler(MOI, 300 + 3 * 64, 999, x=1000)
    r = analyser_decisions(s.donnees())
    assert _valeur(r, "cs2.rotation.delai_median") == 3.0
    assert _valeur(r, "cs2.rotation.part_arrivee") == 100.0
    assert _valeur(r, "cs2.retake.taux_victoire") == 100.0


def test_deathmatch_rien():
    s = Scenario(nb_ticks=100)
    s.joueur(MOI)
    assert analyser_decisions(s.donnees()).mesures == []
    assert analyser_economie(s.donnees()).mesures == []


# --- Économie -----------------------------------------------------------------------------


def test_type_achat():
    assert (type_achat(800), type_achat(1500), type_achat(3999), type_achat(4000)) == (
        "eco",
        "partiel",
        "partiel",
        "complet",
    )


def test_economie():
    s = _match_2v2()
    for debut, (moi, coeq, argent) in zip(
        [0, 1000, 2000, 3000],
        [(800, 800, 0), (4700, 900, 300), (800, 1000, 2000), (5000, 4400, 1200)],
        strict=True,
    ):
        s.eco(MOI, debut + 1280, argent=argent, valeur=moi)
        s.eco(COEQ, debut + 1280, argent=0, valeur=coeq)
    s.eco(MOI, 1099, argent=300, valeur=4700)
    s.eco(MOI, 2299, argent=2000, valeur=800)
    r = analyser_economie(s.donnees())
    # R2 : Mathieu complet, équipe partielle (moyenne 2 800) ; R3, R4 alignés ; R1 pistolet.
    assert _valeur(r, "cs2.eco.part_achats_desynchronises") == pytest.approx(100 / 3, abs=1e-3)
    assert _valeur(r, "cs2.eco.taux_victoire_type", type="partiel") == 0.0
    assert _valeur(r, "cs2.eco.taux_victoire_type", type="eco") == 0.0
    assert _valeur(r, "cs2.eco.taux_victoire_type", type="complet") == 100.0
    assert _valeur(r, "cs2.eco.part_rounds_type", type="eco") == 50.0
    assert _valeur(r, "cs2.eco.argent_restant_moyen") == 1200
    assert _valeur(r, "cs2.eco.valeur_perdue_moyenne") == 2750
    texte = next(p.texte for p in r.preuves)
    assert texte.startswith("Round 2 : Mathieu en achat complet (4700 $)")
