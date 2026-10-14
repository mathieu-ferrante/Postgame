"""Références pros (L3) sur données synthétiques calculées à la main.

DONNÉES DE SUBSTITUTION : aucune démo pro n'a encore été lue. Le catalogue réel se
construira avec `python -m postgame references ajouter <dossier de démos pros>`.
"""

import math

import numpy as np
import pandas as pd
import pytest
from fabrique_cs2 import ADV, MOI, Scenario

from postgame.games.cs2 import references as ref


def _valeur(resultat, nom):
    for mes in resultat.mesures:
        if mes.nom == nom:
            return mes.valeur
    raise AssertionError(f"mesure absente : {nom}")


def test_regrouper():
    points = np.array(
        [[0, 0], [30, 10], [-20, 40], [1000, 0], [1040, 20], [990, -30], [5000, 0]], dtype=float
    )
    etiquettes = ref.regrouper(points)
    assert len(set(etiquettes[:3])) == 1
    assert len(set(etiquettes[3:6])) == 1
    assert len(set(etiquettes)) == 3


def test_associer_lancers_premier_lance_premier_eclate():
    lancers = pd.DataFrame(
        {"tick": [10, 20, 30], "steamid": ["A", "A", "B"], "type": ["smoke", "smoke", "flash"]}
    )
    grenades = pd.DataFrame(
        {
            "tick": [100, 110, 130, 140],
            "lanceur": ["A", "A", "B", "C"],
            "type": ["smoke", "smoke", "flash", "he"],
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "entite": [1, 2, 3, 4],
            "fin": [0, 0, 0, 0],
        }
    )
    g = ref.associer_lancers(lancers, grenades)
    assert g["tick_lancer"].tolist()[:3] == [10, 20, 30]
    assert math.isnan(g["tick_lancer"].iloc[3])


def _observations():
    """Démos pros fictives sur de_test : 4 smokes vers « Window » (≈ 500, 0) lancées depuis
    « TSpawn » (0, -2000), 2 smokes isolées (pas de référence), positions T installées :
    Window 6 fois, Jungle 3, Connector 1."""
    lignes = []
    for i, (x, y) in enumerate([(500, 0), (520, 10), (480, -15), (505, 20)]):
        lignes.append(
            {
                "carte": "de_test",
                "genre": "lancer",
                "type": "smoke",
                "camp": "T",
                "lieu": "TSpawn",
                "x": x,
                "y": y,
                "z": 0,
                "lx": 0,
                "ly": -2000,
                "lz": 0,
                "empreinte": f"d{i % 2}",
            }
        )
    for x in (3000, 6000):
        lignes.append(
            {
                "carte": "de_test",
                "genre": "lancer",
                "type": "smoke",
                "camp": "T",
                "lieu": "Mid",
                "x": x,
                "y": 0,
                "z": 0,
                "lx": 0,
                "ly": 0,
                "lz": 0,
                "empreinte": "d0",
            }
        )
    lignes.append(
        {
            "carte": "de_test",
            "genre": "lieu",
            "type": None,
            "camp": "CT",
            "lieu": "Window",
            "x": 510,
            "y": 5,
            "z": 0,
            "lx": None,
            "ly": None,
            "lz": None,
            "empreinte": "d0",
        }
    )
    for lieu, nb in (("Window", 6), ("Jungle", 3), ("Connector", 1)):
        for _ in range(nb):
            lignes.append(
                {
                    "carte": "de_test",
                    "genre": "position",
                    "type": None,
                    "camp": "T",
                    "lieu": lieu,
                    "x": 100,
                    "y": 100,
                    "z": 0,
                    "lx": None,
                    "ly": None,
                    "lz": None,
                    "empreinte": "d1",
                }
            )
    return pd.DataFrame(lignes)


def test_construire_catalogue():
    lancers, positions = ref.construire_catalogue(_observations())
    assert len(lancers) == 1
    smoke = lancers.iloc[0]
    assert (smoke["x"], smoke["y"]) == pytest.approx((501.25, 3.75))
    assert smoke["lieu_arrivee"] == "Window" and smoke["lieu_lancer"] == "TSpawn"
    assert smoke["nb"] == 4 and smoke["nb_demos"] == 2
    parts = dict(zip(positions["lieu"], positions["part"], strict=True))
    assert parts == pytest.approx({"Window": 0.6, "Jungle": 0.3, "Connector": 0.1})


def test_observations_depuis():
    grenades = pd.DataFrame(
        {
            "tick": [500],
            "lanceur": ["A"],
            "type": ["smoke"],
            "x": [10.0],
            "y": [20.0],
            "z": [0.0],
            "entite": [1],
            "fin": [1500],
        }
    )
    lancers = pd.DataFrame({"tick": [400], "steamid": ["A"], "type": ["smoke"]})
    etats = pd.DataFrame(
        {
            "tick": [400, 1280, 1280],
            "steamid": ["A", "A", "B"],
            "x": [1.0, 2.0, 3.0],
            "y": [0.0, 0.0, 0.0],
            "z": [0.0, 0.0, 0.0],
            "equipe": [2, 2, 3],
            "vivant": [True, True, False],
            "lieu": ["TSpawn", "Window", "Jungle"],
            "nom": ["s1mple", "s1mple", "ZywOo"],
        }
    )
    obs = ref.observations_depuis("de_test", grenades, lancers, etats, debuts=[0])
    # Tick, joueur et round retenus pour revoir le vrai moment dans CS2.
    assert obs[["tick", "joueur", "round"]].iloc[0].tolist() == [400, "s1mple", 1]
    lancer = obs[obs["genre"] == "lancer"].iloc[0]
    assert (lancer["lieu"], lancer["lx"], lancer["camp"]) == ("TSpawn", 1.0, "T")
    positions = obs[obs["genre"] == "position"]
    assert positions["lieu"].tolist() == ["Window"]  # B est mort : ignoré


def _scenario_smokes():
    s = Scenario(nb_ticks=4000)
    s.debuts_rounds, s.fins_rounds = [0, 2000], [1800, 3800]
    s.joueur(MOI, equipe=2, nom="Mathieu")
    s.joueur(ADV, equipe=3, nom="Adv", x=1000)
    s.grenade(MOI, 100, "smoke", x=510, y=10, fin=100 + 18 * 64)  # reconnue, coupe la ligne
    s.grenade(MOI, 2100, "smoke", x=500, y=300, fin=2100 + 18 * 64)  # ratée de ~300 u
    s.grenade(MOI, 2200, "smoke", x=3000, y=3000, fin=2200 + 18 * 64)  # hors référence
    s.lieux = [
        {"tick": 1280, "steamid": MOI, "lieu": "Window"},
        {"tick": 3280, "steamid": MOI, "lieu": "Palace"},
    ]
    return s


def _donnees_avec_lieux(s):
    d = s.donnees()
    d.lieux = pd.DataFrame(s.lieux, columns=["tick", "steamid", "lieu"])
    return d


def test_analyser_references():
    lancers, positions = ref.construire_catalogue(_observations())
    d = _donnees_avec_lieux(_scenario_smokes())
    r = ref.analyser_references(d, ref.Catalogue(lancers, positions))
    assert _valeur(r, "cs2.smoke.part_reconnues") == pytest.approx(100 / 3, abs=1e-3)
    ecart_1 = math.hypot(510 - 501.25, 10 - 3.75)
    ecart_2 = math.hypot(500 - 501.25, 300 - 3.75)
    assert _valeur(r, "cs2.smoke.ecart_median_reference") == pytest.approx(
        (ecart_1 + ecart_2) / 2, abs=1e-3
    )
    assert _valeur(r, "cs2.smoke.part_ligne_coupee") == pytest.approx(100 / 3, abs=1e-3)
    assert _valeur(r, "cs2.position.part_positions_pro") == 50.0
    textes = [p.texte for p in r.preuves]
    assert any(t.startswith("Smoke reconnue : smoke Window depuis TSpawn") for t in textes)
    assert any(t.startswith("Smoke ratée de 296 u") for t in textes)
    assert any(t.startswith("Smoke hors référence") for t in textes)
    assert any("Palace" in t and "Window" in t for t in textes)


def test_sans_catalogue_seule_la_ligne_de_vue():
    d = _donnees_avec_lieux(_scenario_smokes())
    r = ref.analyser_references(d, ref.Catalogue())
    assert {m.nom for m in r.mesures} == {"cs2.smoke.part_ligne_coupee"}


def test_stockage_catalogue(base, tmp_path, monkeypatch):
    from postgame.games.cs2 import extrait_pro
    from postgame.games.cs2.extrait_pro import _tableau

    obs = _observations().drop(columns=["empreinte"])
    obs = obs.assign(tick=range(len(obs)), round=1)
    # 6 pros mesurés sur l'AK : 70, 72, 75, 80, 81, 90 % de premières balles précises.
    mesures = [
        {
            "joueur": f"pro{i}",
            "nom": "cs2.contre_strafe.part_premieres_balles_precises",
            "contexte": {"arme": "ak47", "categorie": "fusil"},
            "valeur": v,
            "n": 20,
        }
        for i, v in enumerate([70, 72, 75, 80, 81, 90])
    ]
    version = {"v": 1}

    def extraire(chemin):
        return {
            "format": 1,
            "version": version["v"],
            "empreinte": "e" * 64,
            "fichier": chemin.name,
            "carte": "de_test",
            "observations": _tableau(obs),
            "mesures": mesures,
        }

    monkeypatch.setattr(extrait_pro, "extraire", extraire)
    monkeypatch.setattr("postgame.importation.empreinte_fichier", lambda chemin: "e" * 64)
    demo = tmp_path / "pro.dem"
    demo.write_bytes(b"demo pro factice")
    extraits = tmp_path / "extraits"
    assert ref.ajouter_demo_pro(base, demo, extraits).startswith("ajoutee")
    # Lue par une version plus ancienne de Postgame : relue au prochain ajout.
    version["v"] = extrait_pro.VERSION_EXTRACTION
    assert ref.ajouter_demo_pro(base, demo, extraits).startswith("ajoutee")
    assert ref.ajouter_demo_pro(base, demo, extraits) == "deja_connue"
    # L'extrait compact se réimporte ailleurs (PC de jeu) sans la démo.
    fichier = extraits / "pro.pgpro"
    assert extrait_pro.lire(fichier)["mesures"] == mesures
    assert ref.ajouter_demo_pro(base, fichier) == "deja_connue"
    assert ref.reconstruire_catalogue(base) == {
        "lancers": 1,
        "positions": 3,
        "references_mecanique": 1,
    }
    cible = base.references(
        "cs2.contre_strafe.part_premieres_balles_precises", {"arme": "ak47", "categorie": "fusil"}
    )[0]
    assert (cible["valeur"], cible["n"], cible["source"]) == (77.5, 6, "joueurs des démos pros")
    cat = ref.charger_catalogue(base, "de_test")
    assert cat.lancers.iloc[0]["lieu_arrivee"] == "Window"
    assert ref.charger_catalogue(base, "de_autre").vide
    assert ref.resume_catalogue(base) == [
        {"carte": "de_test", "demos": 1, "lancers": 1, "positions": 3}
    ]
