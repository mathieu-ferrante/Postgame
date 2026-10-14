"""Protection du service local : pages web malveillantes, DNS rebinding, chemins."""

from fastapi.testclient import TestClient

from postgame.api import creer_app
from postgame.games.cs2 import revoir
from postgame.securite import hote_autorise, hote_et_port, hote_seul


def test_hotes():
    assert hote_seul("192.168.1.20:8765") == "192.168.1.20"
    assert hote_seul("[::1]:8765") == "::1"
    assert hote_et_port("localhost", "http") == ("localhost", 80)
    assert hote_et_port("[::1]:8765", "http") == ("::1", 8765)
    noms = {"pc-de-jeu"}
    for ok in ("localhost", "127.0.0.1", "192.168.1.20", "::1", "pc-de-jeu", "pc-de-jeu.local"):
        assert hote_autorise(ok, noms), ok
    assert not hote_autorise("site-malveillant.example", noms)


def test_requetes_intersites_refusees(base, cfg):
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        assert c.get("/api/sante").status_code == 200  # client sans navigateur
        # Interface servie par le service lui-même (téléphone sur le réseau local).
        meme = {"Origin": "http://192.168.1.20:8765", "Host": "192.168.1.20:8765"}
        assert (
            c.get("/api/sante", headers={**meme, "Sec-Fetch-Site": "same-origin"}).status_code
            == 200
        )
        # Page d'un autre site ouverte dans le navigateur de Mathieu.
        r = c.post(
            "/api/cs2/stuffs/annotations?carte=de_mirage",
            headers={"Origin": "https://site-malveillant.example"},
        )
        assert r.status_code == 403
        assert c.get("/api/sante", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert c.get("/api/sante", headers={"Origin": "null"}).status_code == 403
        # Une autre application locale (autre port) n'est pas l'interface de Postgame.
        autre = {"Origin": "http://localhost:3000", "Host": "localhost:8765"}
        assert c.post("/api/notes", headers=autre, json={}).status_code == 403
        # DNS rebinding : un domaine qui pointe vers 127.0.0.1.
        assert c.get("/api/sante", headers={"Host": "attaque.example:8765"}).status_code == 403


def test_parametres_de_chemin_valides(base, cfg):
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        assert c.post("/api/cs2/stuffs/annotations?carte=../../../evil").status_code == 422
        assert c.get("/api/cs2/stuffs?carte=de_mirage%0Aquit").status_code == 422
        assert c.get("/api/cs2/stuffs/a..b/image").status_code in (404, 422)


def test_noms_sans_commande_cachee(tmp_path):
    demo = tmp_path / "m.dem"
    demo.write_bytes(b"x")
    revoir.preparer(demo, 100, 'pro"\nquit; bind', None, tmp_path, "p1", joueurs=["a\r\nexec x"])
    aller = (tmp_path / "cfg" / "postgame_aller.cfg").read_text(encoding="utf-8")
    vue = (tmp_path / "cfg" / "postgame_vue_1.cfg").read_text(encoding="utf-8")
    assert aller.count("\n") == 3 and 'spec_player "proquit bind"' in aller
    assert vue == 'spec_player "aexec x"\n'
