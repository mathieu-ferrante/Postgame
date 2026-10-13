"""Pool de cartes CS2 tenu à jour d'après les notes officielles (actualités simulées)."""

import httpx

from postgame.games.cs2 import cartes


def test_base_officielle_du_9_juillet_2026():
    assert "de_cache" in cartes.BASE["pool"] and "de_overpass" not in cartes.BASE["pool"]
    assert len(cartes.BASE["pool"]) == 7


def test_codes():
    assert cartes.code_carte("Dust II") == "de_dust2"
    assert cartes.code_carte("Cache") == "de_cache"
    assert cartes.code_carte("El Dorado") == "de_eldorado"
    assert cartes.nom_affiche("de_dust2") == "Dust II"


def test_actualites_appliquees_dans_l_ordre():
    evts = [
        {"date": "2026-07-09", "titre": "x", "texte": "Added Cache to the Active Duty Map Pool"},
        {
            "date": "2026-12-02",
            "titre": "Counter-Strike 2 Update",
            "texte": "[ PREMIER ] Added Train to the Active Duty Map Pool "
            "Removed Nuke from the Active Duty Map Pool",
        },
    ]
    etat = cartes.appliquer_actualites(dict(cartes.BASE), evts)
    assert "de_train" in etat["pool"] and "de_nuke" not in etat["pool"]
    assert etat["date"] == "2026-12-02" and "2026-12-02" in etat["source"]


def test_actualiser(tmp_path):
    corps = {
        "events": [
            {
                "event_name": "Counter-Strike 2 Update",
                "rtime32_start_time": 1798761600,
                "announcement_body": {
                    "body": "[list][*]Added Vertigo to the Active Duty Map Pool[/*][/list]"
                },
            }
        ]
    }
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=corps)))
    etat = cartes.actualiser(tmp_path, client)
    assert "de_vertigo" in etat["pool"]
    assert cartes.etat_cartes(tmp_path)["pool"] == etat["pool"]
    panne = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    assert cartes.actualiser(tmp_path, panne)["pool"] == etat["pool"]  # on garde l'acquis
