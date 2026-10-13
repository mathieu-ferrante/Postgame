"""Données du replay 2D, radar et service de l'interface (L6), sur match synthétique."""

from pathlib import Path

import pytest
from fabrique_cs2 import ADV, COEQ, MOI, Scenario
from fastapi.testclient import TestClient

from postgame.api import creer_app
from postgame.db import Partie
from postgame.games.cs2 import radar
from postgame.games.cs2.replay import construire_meta, construire_replay


def _match():
    s = Scenario(nb_ticks=2400)
    s.debuts_rounds, s.fins_rounds = [400, 1400], [1300, 2300]
    s.gagnants = {1300: 2, 2300: 3}
    s.joueur(MOI, equipe=2, nom="Mathieu", x=0.4, y=10.6, yaw=90.4)
    s.joueur(COEQ, equipe=2, nom="Coequipier", x=300)
    s.joueur(ADV, equipe=3, nom="Adv", x=1000, y=500)
    s.tir(MOI, 600)
    s.mort(MOI, ADV, 604, headshot=True)
    s.regler(ADV, 604, 1399, vivant=False)
    s.grenade(MOI, 800, "smoke", x=500, y=200, fin=800 + 18 * 64)
    s.bombe.append({"tick": 1000, "evenement": "pose", "steamid": MOI})
    return s.donnees()


def test_meta():
    meta = construire_meta(_match())
    assert meta["carte"] == "de_test"
    assert [j["nom"] for j in meta["joueurs"]] == ["Coequipier", "Mathieu", "Adv"]
    assert [j["moi"] for j in meta["joueurs"]] == [False, True, False]
    assert meta["rounds"][0] == {"numero": 1, "debut": 400, "fin": 1300, "gagnant": 2}
    fond = meta["fond"]
    assert fond["cellule"] == 64 and [0, 0] in fond["cellules"]


def test_round():
    replay = construire_replay(_match())
    r1 = replay["rounds"]["1"]
    # Départ 5 s avant la fin du freeze, puis une image tous les 4 ticks.
    assert r1["depart"] == 80 and r1["ticks"][:3] == [80, 84, 88]
    moi = r1["joueurs"]["1"]
    assert (moi["x"][0], moi["y"][0], moi["yaw"][0], moi["equipe"]) == (0, 11, 90, 2)
    adv = r1["joueurs"]["2"]
    i = r1["ticks"].index(604)
    assert adv["vivant"][i - 1] == 1 and adv["vivant"][i] == 0
    assert r1["tirs"] == [[600, 1]]
    assert r1["morts"] == [[604, 1, 2, "ak47", True]]
    assert r1["grenades"] == [["smoke", 500, 200, 800, 800 + 18 * 64, 1]]
    assert r1["bombe"] == [[1000, "pose", 0, 11]]
    # La smoke déborde sur le round 2 : elle y figure aussi.
    assert replay["rounds"]["2"]["grenades"][0][0] == "smoke"


def test_radar(tmp_path):
    assert radar.radar(tmp_path, "de_mirage")["parametres"]["scale"] == 5.0
    assert radar.radar(tmp_path, "de_mirage")["image"] is None
    (tmp_path / "radars").mkdir()
    (tmp_path / "radars" / "de_mirage.txt").write_text(
        '"de_mirage"\n{\n\t"material" "overviews/de_mirage"\n\t"pos_x" "-3240"\n'
        '\t"pos_y" "1700"\n\t"scale" "5.00"\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "radars" / "de_mirage.png").write_bytes(b"\x89PNG")
    r = radar.radar(tmp_path, "de_mirage")
    assert r["parametres"] == {"pos_x": -3240, "pos_y": 1700, "scale": 5.0}
    assert r["source_parametres"] == "jeu" and r["image"] == "/api/cs2/radar/de_mirage.png"
    assert radar.radar(tmp_path, "de_inconnue")["parametres"] is None
    assert radar.chemin_image(tmp_path, "../secret") is None


@pytest.fixture
def client(base, cfg, tmp_path):
    demo = tmp_path / "m.dem"
    demo.write_bytes(b"demo")
    pid = base.ajouter_partie(
        Partie(
            jeu="cs2",
            date_partie="2026-10-01T20:00:00+00:00",
            mode="competitif",
            carte="de_test",
            resultat="victoire",
            source="m.dem",
            fichier=str(demo),
            empreinte="r" * 64,
        )
    )
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>Postgame</html>", encoding="utf-8")
    (web / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    cfg.dossier_web = web
    app = creer_app(cfg, base=base, surveiller=False)
    appels = []

    def extraire(chemin: Path, steamid: str):
        appels.append(chemin)
        return _match()

    app.state.extraire_match = extraire
    with TestClient(app) as c:
        c.pid, c.appels = pid, appels
        yield c


def test_api_replay_et_cache(client):
    meta = client.get(f"/api/cs2/replay/{client.pid}").json()
    assert meta["carte"] == "de_test" and meta["radar"]["parametres"] is None
    r2 = client.get(f"/api/cs2/replay/{client.pid}/round/2").json()
    assert r2["debut"] == 1400
    assert client.get(f"/api/cs2/replay/{client.pid}/round/9").status_code == 404
    assert len(client.appels) == 1  # la démo n'est lue qu'une fois, ensuite le cache
    assert client.get("/api/cs2/replay/999").status_code == 404
    assert client.get("/api/cs2/radar/de_test.png").status_code == 404


def test_interface_servie(client):
    assert client.get("/").text == "<html>Postgame</html>"
    assert client.get("/partie/3").text == "<html>Postgame</html>"  # route de l'appli
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/api/inexistant").status_code == 404
    assert client.get("/../pyproject.toml").text == "<html>Postgame</html>"
