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
