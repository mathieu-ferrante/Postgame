"""Vrais lineups : filtre des lancers reproduits, timing et raison, sur cas construits."""

import json

import numpy as np
import pandas as pd
import pytest

from postgame.games.cs2 import lineups as lu
from postgame.games.cs2.donnees import fin_apres
from postgame.games.cs2.geometrie import angle_entre


def _lancers(n, lx=1000.0, yaw=180.0, pitch=-30.0, joueurs=None, **autres):
    return pd.DataFrame(
        {
            "lx": [lx + (i % 3) for i in range(n)],
            "ly": 0.0,
            "lyaw": [yaw + 0.5 * (i % 2) for i in range(n)],
            "lpitch": pitch,
            "joueur": joueurs or ["a"] * n,
            **autres,
        }
    )


def test_seuls_les_lancers_reproduits_sont_des_lineups():
    bons = _lancers(3)
    a_l_arrache = pd.DataFrame(
        {
            "lx": [1500.0, 2200.0],
            "ly": [400.0, -300.0],
            "lyaw": [90.0, 10.0],
            "lpitch": [0.0, 5.0],
            "joueur": ["b", "c"],
        }
    )
    groupes = lu.lineups(pd.concat([bons, a_l_arrache], ignore_index=True))
    assert len(groupes) == 1 and len(groupes[0]) == 3
    # Même point mais visée différente de 10° : écarté du lineup.
    devie = pd.concat([bons, _lancers(1, yaw=190.0)], ignore_index=True)
    assert len(lu.lineups(devie)[0]) == 3
    # Deux lancers seulement : il faut deux joueurs différents.
    assert lu.lineups(_lancers(2)) == []
    assert len(lu.lineups(_lancers(2, joueurs=["a", "b"]))) == 1


def test_phase():
    assert lu.phase("T", 40.0, 8.0, 0, "A") == "exécution A"
    assert lu.phase("T", 40.0, 30.0, 0, "A") == "milieu de round"
    assert lu.phase("T", 70.0, None, 1, "B") == "après la pose"
    assert lu.phase("CT", 70.0, None, 1, "B") == "retake"
    assert lu.phase("CT", 3.0, None, 0, None) == "début de round"


def test_expliquer_une_smoke_d_execution():
    g = _lancers(
        4,
        camp="T",
        temps=[30.0, 31.0, 32.0, 29.0],
        avant_pose=[8.0, 9.0, 10.0, 40.0],
        apres_pose=0,
        site_pose=["A", "A", "A", "B"],
        duree=22.1,
        gagne=[1, 1, 0, 1],
        effet=None,
    )
    e = lu.expliquer(g, "smoke")
    assert e["phase"] == "exécution A" and e["part_phase"] == 0.75
    assert e["temps_median"] == 30.5 and e["part_victoire"] == 0.75
    assert "bombe est posée sur A 9 s plus tard" in e["raison"]
    assert "La smoke dure 22,1 s" in e["raison"] and "encore 13,1 s après la pose" in e["raison"]
    assert "3 fois sur 4" in e["raison"]


def test_expliquer_une_flash():
    g = _lancers(
        3,
        camp="CT",
        temps=5.0,
        avant_pose=None,
        apres_pose=0,
        site_pose=None,
        effet=[2.0, 1.0, 0.0],
        allies=[0.0, 0.0, 1.0],
        gagne=[1, 0, 1],
    )
    e = lu.expliquer(g, "flash")
    assert e["phase"] == "début de round" and e["effet_moyen"] == 1.0
    assert "Aveugle en moyenne 1 adversaire(s)" in e["raison"]


def test_contexte_d_un_lancer():
    ctx = lu.ContexteDemo(
        gagnants={2: 2},
        poses=pd.DataFrame({"tick": [5000], "site": ["A"]}),
        effets={("s", 3000): {"effet": None, "allies": None, "duree": 22.1}},
        trajectoires={("s", 3000): "[[2995,0,0,0]]"},
    )
    c = lu.contexte_lancer(ctx, "s", 3000, 2995, 2, 1000, 9000, 2)
    assert c["temps"] == round(1995 / 64, 1) and c["avant_pose"] == round(2005 / 64, 1)
    assert (c["site_pose"], c["apres_pose"], c["gagne"], c["duree"]) == ("A", 0, 1, 22.1)
    assert json.loads(c["trajectoire"]) == [[2995, 0, 0, 0]]
    assert lu.contexte_lancer(ctx, "s", 6000, None, 2, 1000, 9000, 3)["apres_pose"] == 1


def test_site_et_fins_d_entites_reutilisees():
    assert (lu.site_de("BombsiteA"), lu.site_de("BombsiteB"), lu.site_de("Mid")) == ("A", "B", None)
    fins = pd.DataFrame({"entityid": [7, 7], "tick": [1400, 9000]})
    # La même entité revient plus tard dans le match : on prend la fin qui suit l'éclatement.
    assert fin_apres(fins, 7, 8000, 8000, 30 * 64) == 9000
    assert fin_apres(fins, 7, 100, 100, 30 * 64) == 1400
    assert fin_apres(fins, 7, 3000, 3333, 30 * 64) == 3333


def test_trajectoire_reelle_coupee_a_l_arret():
    vol = [[100 + i, 0.0 + 10 * i, 0.0, 0.0] for i in range(20)]
    arret = [[120 + i, 190.0, 0.0, 0.0] for i in range(30)]
    autre = [[5000 + i, 50.0 * i, 0.0, 0.0] for i in range(10)]  # même identifiant, plus tard
    brut = pd.DataFrame(
        [[1, "s", *p] for p in vol + arret] + [[1, "t", *p] for p in autre],
        columns=["grenade_entity_id", "steamid", "tick", "x", "y", "z"],
    )
    lancers = pd.DataFrame({"tick": [100, 5000], "steamid": ["s", "t"], "type": ["smoke", "flash"]})
    tr = lu.trajectoires_lancers(brut, lancers)
    points = json.loads(tr[("s", 100)])
    assert points[0][0] == 100 and points[-1][1] == 190 and points[-1][0] <= 121
    assert json.loads(tr[("t", 5000)])[0][0] == 5000


def test_angle_inconnu_n_est_pas_nul():
    assert np.isnan(angle_entre(float("nan"), 0.0, 10.0, 0.0))
    assert angle_entre(0.0, 0.0, 10.0, 0.0) == pytest.approx(10.0)


def test_import_automatique_des_pros(base, tmp_path, monkeypatch):
    from postgame.games.cs2 import pros_auto, references

    dossier = tmp_path / "Drive" / "pros"
    (dossier / "sous").mkdir(parents=True)
    (dossier / "a.pgpro").write_bytes(b"x")
    (dossier / "sous" / "b.dem").write_bytes(b"x")
    (dossier / "notes.txt").write_text("rien")
    vus: set[str] = set()
    appels = []
    monkeypatch.setattr(
        references, "ajouter_demo_pro", lambda b, f, d=None: appels.append(f.name) or "ajoutee (1)"
    )
    monkeypatch.setattr(references, "reconstruire_catalogue", lambda b: {"lancers": 1})
    # Jeu en cours : l'extrait passe, la démo (lourde) attend.
    bilan = pros_auto.synchroniser(base, [dossier], vus, peut_lire_demo=lambda: False)
    assert appels == ["a.pgpro"] and bilan["b.dem"] == "reportée (jeu en cours)"
    assert bilan["catalogue"] == "{'lancers': 1}"
    bilan = pros_auto.synchroniser(base, [dossier], vus)
    assert appels == ["a.pgpro", "b.dem"]
    assert pros_auto.synchroniser(base, [dossier], vus) == {}
