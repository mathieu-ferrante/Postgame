"""Revoir un vrai moment dans CS2 : fichiers préparés et moments pros retrouvés."""

from fastapi.testclient import TestClient

from postgame.api import creer_app
from postgame.games.cs2 import revoir


def _demo(chemin, taille=10):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(b"PBDEMS2\0" + b"x" * taille)
    return chemin


def test_preparer_dans_le_jeu(tmp_path):
    csgo = tmp_path / "game" / "csgo"
    (csgo / "cfg").mkdir(parents=True)
    (csgo / "replays").mkdir()
    assert revoir.dossier_csgo([csgo / "replays"]) == csgo
    demo = _demo(tmp_path / "archives" / "match.dem")
    r = revoir.preparer(demo, 5000, 'JEANMARKKARROK "SKIN"', csgo, tmp_path / "repli", "partie3")
    assert r.installe and r.demo == csgo / "postgame" / "partie3.dem" and r.demo.is_file()
    assert r.tick == 5000 - 5 * 64 and r.commandes == ["exec postgame", "pg"]
    lancer = (csgo / "cfg" / "postgame.cfg").read_text(encoding="utf-8")
    assert 'alias pg "exec postgame_aller"' in lancer and "playdemo postgame/partie3" in lancer
    aller = (csgo / "cfg" / "postgame_aller.cfg").read_text(encoding="utf-8")
    assert "demo_gototick 4680" in aller and 'spec_player "JEANMARKKARROK SKIN"' in aller
    # Début de démo : jamais de tick négatif ; sans joueur, pas de spec_player.
    r = revoir.preparer(demo, 10, None, csgo, tmp_path / "repli", "partie3")
    assert r.tick == 0
    assert "spec_player" not in (csgo / "cfg" / "postgame_aller.cfg").read_text(encoding="utf-8")


def test_preparer_hors_du_jeu_et_menage(tmp_path):
    repli = tmp_path / "repli"
    for i in range(6):
        demo = _demo(tmp_path / f"d{i}.dem", taille=i)
        r = revoir.preparer(demo, 1000, None, None, repli, f"pro{i}")
    assert not r.installe and (repli / "cfg" / "postgame.cfg").is_file()
    restantes = sorted(f.name for f in (repli / "postgame").glob("*.dem"))
    assert len(restantes) == revoir.COPIES_GARDEES and "pro5.dem" in restantes


def _remplir(base, demo):
    with base.transaction() as cx:
        cx.execute(
            "INSERT INTO cs2_ref_demos (empreinte, fichier, carte, ajoute_le, chemin) "
            "VALUES ('abc123', 'navi-vs-vitality.dem', 'de_mirage', 'x', ?)",
            (str(demo),),
        )
        cx.execute(
            "INSERT INTO cs2_ref_demos (empreinte, fichier, carte, ajoute_le, chemin) "
            "VALUES ('def456', 'disparue.dem', 'de_mirage', 'x', 'C:/nulle/part.dem')"
        )
        lignes = [
            # empreinte, genre, type, camp, lieu, x, y, lx, ly, tick, joueur, round
            ("abc123", "lieu", None, "CT", "Jungle", 100, 0, None, None, 3000, "ZywOo", 2),
            ("abc123", "lieu", None, "CT", "Jungle", 120, 0, None, None, 3200, "ZywOo", 2),
            ("abc123", "lieu", None, "CT", "Jungle", 50, 0, None, None, 9000, "apEX", 5),
            ("abc123", "lieu", None, "T", "Jungle", 100, 0, None, None, 3000, "s1mple", 2),
            ("abc123", "lieu", None, "CT", "Ticket", 2000, 0, None, None, 3000, "flameZ", 2),
            ("def456", "lieu", None, "CT", "Jungle", 100, 0, None, None, 3000, "m0NESY", 1),
            ("abc123", "lancer", "smoke", "T", "TSpawn", 1000, 0, 500, 0, 4000, "b1t", 3),
            ("abc123", "lancer", "smoke", "T", "TSpawn", 1010, 0, 900, 0, 4100, "jL", 3),
        ]
        cx.executemany(
            "INSERT INTO cs2_ref_observations (empreinte, carte, genre, type, camp, lieu, x, y, "
            "lx, ly, tick, joueur, round) VALUES (?, 'de_mirage', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            lignes,
        )
        cx.execute(
            "INSERT INTO cs2_ref_lancers (carte, type, x, y, lx, ly, nb, nb_demos, cle, "
            "construit_le) VALUES ('de_mirage', 'smoke', 1000, 0, 500, 0, 5, 2, 'cle1', 'x')"
        )


def test_moments_pros(base, tmp_path):
    _remplir(base, _demo(tmp_path / "pro.dem"))
    proches = revoir.moments_proches(base, "de_mirage", "CT", 100.0, 0.0)
    # Un moment par (démo, round, joueur), le plus proche d'abord ; une démo absente de la
    # machine reste listée mais ne peut pas s'ouvrir dans CS2.
    assert [(m["joueur"], m["tick"], m["disponible"]) for m in proches] == [
        ("ZywOo", 3000, True),
        ("m0NESY", 3000, False),
        ("apEX", 9000, True),
    ]
    assert "s1mple" in [
        m["joueur"] for m in revoir.moments_proches(base, "de_mirage", None, 100, 0)
    ]
    # Seul b1t lance depuis le même point que le stuff (jL lance de 400 u plus loin).
    assert [m["joueur"] for m in revoir.exemples_stuff(base, "cle1")] == ["b1t"]


def test_api_revoir(base, cfg, tmp_path):
    _remplir(base, _demo(tmp_path / "pro.dem"))
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        pros = {p["empreinte"]: p["disponible"] for p in c.get("/api/cs2/pros").json()}
        assert pros == {"abc123": True, "def456": False}
        r = c.post("/api/cs2/revoir", json={"empreinte": "abc123", "tick": 4000, "joueur": "b1t"})
        assert r.status_code == 200 and r.json()["commandes"] == ["exec postgame", "pg"]
        assert not r.json()["installe"]  # poste de dev : pas de dossier CS2
        assert c.post("/api/cs2/revoir", json={"empreinte": "def456", "tick": 1}).status_code == 410
        assert c.post("/api/cs2/revoir", json={"partie_id": 99, "tick": 1}).status_code == 404
        assert c.post("/api/cs2/revoir", json={"tick": 1}).status_code == 422
        assert c.get("/api/cs2/stuffs/cle1/pros").json()[0]["joueur"] == "b1t"
        assert c.get("/api/cs2/stuffs/inconnu/pros").status_code == 404
        proches = c.get("/api/cs2/pros/proches?carte=de_mirage&x=100&y=0&camp=CT").json()
        assert proches[0]["joueur"] == "ZywOo"


def test_vues_des_autres_et_pause(tmp_path):
    csgo = tmp_path / "csgo"
    (csgo / "cfg").mkdir(parents=True)
    (csgo / "cfg" / "postgame_vue_9.cfg").write_text("ancien")
    demo = _demo(tmp_path / "m.dem")
    r = revoir.preparer(
        demo,
        1000,
        "b1t",
        csgo,
        tmp_path,
        "pro1",
        avance_s=0.05,
        joueurs=["b1t", "jL", "b1t", "", "Aleksib"],
        pause=True,
    )
    assert r.tick == 1000 - 3 and r.vues == [("v1", "b1t"), ("v2", "jL"), ("v3", "Aleksib")]
    lancer = (csgo / "cfg" / "postgame.cfg").read_text(encoding="utf-8")
    assert 'alias v2 "exec postgame_vue_2"' in lancer
    assert lancer.index("alias v3") < lancer.index("playdemo")  # alias avant le chargement
    assert (csgo / "cfg" / "postgame_vue_2.cfg").read_text(encoding="utf-8") == 'spec_player "jL"\n'
    assert not (csgo / "cfg" / "postgame_vue_9.cfg").exists()
    aller = (csgo / "cfg" / "postgame_aller.cfg").read_text(encoding="utf-8")
    assert aller.strip().endswith("demo_pause")


def test_api_capture_de_la_vue_du_pro(base, cfg, tmp_path):
    import os
    import time

    _remplir(base, _demo(tmp_path / "pro.dem"))
    cfg.dossier_steam = tmp_path / "Steam"
    cfg.steamid = "76561198000000001"
    captures = cfg.dossier_steam / "userdata" / "39734273" / "760" / "remote" / "730"
    captures = captures / "screenshots"
    captures.mkdir(parents=True)
    (captures / "ancienne.jpg").write_bytes(b"vieux")
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        assert c.get("/api/cs2/stuffs/cle1/capture").json() == {"attente": False, "image": None}
        r = c.post(
            "/api/cs2/stuffs/cle1/capture",
            json={"empreinte": "abc123", "tick": 4000, "joueur": "b1t"},
        ).json()
        assert r["dossiers"] == [str(captures)] and r["vues"][0]["joueur"] == "ZywOo"
        assert r["tick"] == 4000 - 2  # 2 ticks avant le vrai lâcher
        assert c.get("/api/cs2/stuffs/cle1/capture").json()["attente"] is True
        nouvelle = captures / "20261013_vue.jpg"
        nouvelle.write_bytes(b"\xff\xd8vue du pro")
        futur = time.time() + 5
        os.utime(nouvelle, (futur, futur))
        assert c.get("/api/cs2/stuffs/cle1/capture").json()["image"] == "/api/cs2/stuffs/cle1/image"
        assert c.get("/api/cs2/stuffs/cle1/image").content == b"\xff\xd8vue du pro"
        assert c.get("/api/cs2/stuffs/cle1/capture").json()["attente"] is False
        assert c.post("/api/cs2/radars/exporter").status_code == 409  # outil non configuré


def test_toutes_les_cartes(base, cfg, tmp_path):
    _remplir(base, _demo(tmp_path / "pro.dem"))
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        cartes = {x["code"]: x["categorie"] for x in c.get("/api/cs2/cartes").json()["cartes"]}
    # Pool actif, cartes officielles hors pool et Wingman, cartes des démos pros.
    assert cartes["de_cache"] == "pool" and cartes["de_overpass"] == "hors pool"
    assert cartes["de_train"] == "hors pool" and cartes["de_eldorado"] == "wingman"
    assert len([c for c, cat in cartes.items() if cat == "pool"]) == 7
