import pytest
from fastapi.testclient import TestClient

from postgame.api import creer_app
from postgame.db import Mesure


@pytest.fixture
def client(base, cfg, factice):
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        yield c


def test_sante(client):
    r = client.get("/api/sante")
    assert r.status_code == 200
    assert r.json()["statut"] == "ok"


def test_jeux(client):
    noms = [j["nom"] for j in client.get("/api/jeux").json()]
    assert "cs2" in noms and "factice" in noms


def test_import_manuel_puis_fiche(client, base):
    r = client.post("/api/import", files={"fichier": ("m.factice", b"carte=de_train")})
    assert r.status_code == 200, r.text
    pid = r.json()["partie_id"]
    assert r.json()["statut"] == "importe"

    liste = client.get("/api/parties").json()
    assert liste["total"] == 1 and liste["parties"][0]["carte"] == "de_train"

    fiche = client.get(f"/api/parties/{pid}").json()
    assert fiche["source"] == "m.factice"
    assert fiche["mesures"][0]["nom"] == "factice.taille"
    assert fiche["preuves"][0]["texte"] == "début du fichier"
    assert client.get(f"/api/parties/{pid}/preuves?mesure=factice.taille").json()[0]["tick"] == 0

    # Second envoi du même contenu : reconnu.
    r2 = client.post("/api/import", files={"fichier": ("copie.factice", b"carte=de_train")})
    assert r2.json()["statut"] == "deja_connu"


def test_import_refuse_extension_et_fichier_casse(client):
    assert client.post("/api/import", files={"fichier": ("a.txt", b"x")}).status_code == 415
    r = client.post("/api/import", files={"fichier": ("a.factice", b"illisible")})
    assert r.status_code == 422


def test_partie_inconnue(client):
    assert client.get("/api/parties/999").status_code == 404
    assert client.get("/api/parties/999/mesures").status_code == 404


def test_progression(client, base):
    r = client.post("/api/import", files={"fichier": ("m.factice", b"x")})
    pid = r.json()["partie_id"]
    base.remplacer_mesures(pid, [Mesure("cs2.test", 1, 0.42, "%")])
    assert "cs2.test" in client.get("/api/mesures").json()
    # La partie factice est datée du 2026-10-01 : présente dans « tout ».
    points = client.get("/api/progression/cs2.test?periode=tout").json()["points"]
    assert points[0]["valeur"] == 0.42
    assert client.get("/api/progression/cs2.test?periode=1an").status_code == 422


def test_etat_import(client):
    etat = client.get("/api/import/etat").json()
    assert etat["surveillance_active"] is False
    assert etat["derniers_fichiers"] == []


def test_definitions(client):
    import postgame.games.cs2.mecanique  # noqa: F401  (enregistre les définitions)

    defs = {d["nom"]: d for d in client.get("/api/mesures/definitions").json()}
    d = defs["cs2.contre_strafe.part_tirs_precis"]
    assert d["unite"] == "%" and d["version"] >= 1 and d["fiable"] is False


def test_chaleur(client, base):
    from postgame.mesures import Preuve

    r = client.post("/api/import", files={"fichier": ("m.factice", b"carte=de_mirage")})
    pid = r.json()["partie_id"]
    base.remplacer_preuves(
        pid,
        [
            Preuve("cs2.position.mort", 10, "Mort (T)", 1, {"x": 1.0, "y": 2.0, "camp": "T"}),
            Preuve("cs2.position.mort", 20, "Mort (CT)", 2, {"x": 3.0, "y": 4.0, "camp": "CT"}),
            Preuve("cs2.position.kill", 30, "Kill (T)", 2, {"x": 5.0, "y": 6.0, "camp": "T"}),
        ],
    )
    # La partie factice n'est pas du jeu cs2 : rien.
    assert client.get("/api/cs2/chaleur?carte=de_mirage").json()["points"] == []
    with base.transaction() as cx:
        cx.execute("UPDATE parties SET jeu = 'cs2' WHERE id = ?", (pid,))
    points = client.get("/api/cs2/chaleur?carte=de_mirage&camp=T").json()["points"]
    assert [(p["x"], p["round"]) for p in points] == [(1.0, 1)]
    kills = client.get("/api/cs2/chaleur?carte=de_mirage&type=kill").json()["points"]
    assert len(kills) == 1
