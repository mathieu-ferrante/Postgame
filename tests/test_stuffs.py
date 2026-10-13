"""Apprentissage des stuffs (STUFF-01) : catalogue, maîtrise, notes, révisions.

DONNÉES DE SUBSTITUTION : catalogue et smokes fabriqués à la main.
"""

from datetime import date

import pandas as pd
from fastapi.testclient import TestClient

from postgame.api import creer_app
from postgame.db import Partie
from postgame.games.cs2 import stuffs
from postgame.games.cs2.references import cles_stables, yaw_moyen
from postgame.mesures import Preuve


def _catalogue(base):
    with base.transaction() as cx:
        cx.execute(
            "INSERT INTO cs2_ref_lancers (carte, type, x, y, z, lx, ly, lz, lieu_arrivee, "
            "lieu_lancer, nb, nb_demos, lpitch, lyaw, part_saut, part_accroupi, cle, "
            "construit_le) VALUES ('de_mirage', 'smoke', 500, 0, 0, -1200.5, -300.25, -167.97, "
            "'Window', 'TSpawn', 12, 5, -15.4, 32.8, 0.9, 0, 'abc', 'x')"
        )
        cx.execute(
            "INSERT INTO cs2_ref_lancers (carte, type, x, y, z, lx, ly, lz, lieu_arrivee, "
            "lieu_lancer, nb, nb_demos, lpitch, lyaw, part_saut, part_accroupi, cle, "
            "construit_le) VALUES ('de_mirage', 'flash', 900, 900, 0, 0, 0, 0, 'Jungle', "
            "'Connector', 4, 2, NULL, NULL, NULL, NULL, 'def', 'x')"
        )


def _smoke_en_match(base, empreinte, date_partie, ecart):
    pid = base.ajouter_partie(
        Partie(
            jeu="cs2",
            date_partie=date_partie,
            mode="premier",
            carte="de_mirage",
            resultat="victoire",
            source="x",
            fichier="x",
            empreinte=empreinte,
        )
    )
    base.remplacer_preuves(
        pid, [Preuve("cs2.smoke.part_reconnues", 100, "smoke", 1, {"stuff": "abc", "ecart": ecart})]
    )


def test_commandes_et_technique():
    s = {
        "lx": -1200.5,
        "ly": -300.25,
        "lz": -167.97,
        "lpitch": -15.4,
        "lyaw": 32.8,
        "part_saut": 0.9,
        "part_accroupi": 0,
        "type": "smoke",
        "lieu_arrivee": "Window",
        "lieu_lancer": "TSpawn",
    }
    assert stuffs.commandes(s) == "setpos -1200.50 -300.25 -167.97; setang -15.40 32.80 0"
    assert stuffs.technique(s) == "en sautant (jumpthrow)"
    assert stuffs.nom(s) == "Smoke Window depuis TSpawn"
    assert stuffs.commandes({"lx": None}) is None


def test_yaw_moyen_circulaire():
    assert abs(abs(yaw_moyen(pd.Series([-170.0, 170.0]))) - 180) < 1e-9


def test_cles_stables():
    anciens = pd.DataFrame(
        [{"carte": "de_mirage", "type": "smoke", "x": 500, "y": 0, "cle": "abc"}]
    )
    nouveaux = pd.DataFrame(
        [
            {"carte": "de_mirage", "type": "smoke", "x": 540, "y": 10},
            {"carte": "de_mirage", "type": "smoke", "x": 3000, "y": 0},
        ]
    )
    cles = cles_stables(nouveaux, anciens)
    assert cles[0] == "abc" and cles[1] != "abc"


def test_maitrise_revisions_et_a_reviser(base):
    _catalogue(base)
    _smoke_en_match(base, "a", "2026-10-01T20:00:00+00:00", 80.0)  # réussie
    _smoke_en_match(base, "b", "2026-10-05T20:00:00+00:00", 260.0)  # ratée
    m = stuffs.maitrise(base, "de_mirage")["abc"]
    assert (m["tentatives"], m["reussites"], m["dernier_ecart"]) == (2, 1, 260.0)
    # Jamais révisés : le plus joué par les pros d'abord.
    jour = date(2026, 10, 13)  # jamais révisés : le plus joué par les pros d'abord
    assert [s["cle"] for s in stuffs.a_reviser(base, "de_mirage", jour=jour)] == ["abc", "def"]
    r = stuffs.noter_revision(base, "def", True, date(2026, 10, 13))
    assert (r["boite"], r["prochaine"]) == (2, "2026-10-15")
    r = stuffs.noter_revision(base, "def", True, date(2026, 10, 15))
    assert (r["boite"], r["prochaine"]) == (3, "2026-10-19")
    r = stuffs.noter_revision(base, "def", False, date(2026, 10, 19))
    assert (r["boite"], r["prochaine"]) == (1, "2026-10-20")
    a_voir = [s["cle"] for s in stuffs.a_reviser(base, "de_mirage", jour=date(2026, 10, 19))]
    assert a_voir == ["abc"]  # « def » n'est dû que le 20


def test_notes_et_api(base, cfg):
    _catalogue(base)
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        nid = c.post(
            "/api/notes",
            json={"carte": "de_mirage", "texte": "Toujours smoke window avant d'entrer mid"},
        ).json()["id"]
        c.post(
            "/api/notes", json={"carte": "de_mirage", "stuff": "abc", "texte": "viser l'antenne"}
        )
        vue = c.get("/api/cs2/stuffs?carte=de_mirage").json()
        assert vue["notes_carte"][0]["id"] == nid
        smoke = next(s for s in vue["stuffs"] if s["cle"] == "abc")
        assert smoke["notes"][0]["texte"] == "viser l'antenne"
        assert smoke["commandes"].startswith("setpos -1200.50")
        assert "sv_cheats 1" in vue["config_entrainement"]
        assert c.put(f"/api/notes/{nid}", json={"texte": "modifiée"}).status_code == 200
        assert c.delete(f"/api/notes/{nid}").status_code == 200
        assert c.delete(f"/api/notes/{nid}").status_code == 404
        assert c.post("/api/cs2/stuffs/abc/revision", json={"reussi": True}).json()["boite"] == 2
