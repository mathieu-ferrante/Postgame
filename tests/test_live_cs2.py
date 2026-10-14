"""Second écran CS2 (L7) : économie, résumé GSI, jeton, journal, WebSocket.

DONNÉES DE SUBSTITUTION : le message GSI ci-dessous suit le format documenté par Valve ;
le flux réel d'une partie reste à journaliser sur le PC de jeu (A_VALIDER.md).
"""

import json
import time

import pytest
from fastapi.testclient import TestClient

from postgame.api import creer_app
from postgame.live.economie_cs2 import prime_defaite, recommander
from postgame.live.gsi_cs2 import RecepteurGSI, jeton_gsi, resumer, texte_config

MOI = "76561198000000001"


def message(jeton="jeton", argent=3500, camp="T", observe=None, round_joues=4):
    return {
        "provider": {
            "name": "Counter-Strike 2",
            "appid": 730,
            "steamid": MOI,
            "timestamp": 1760000000,
        },
        "map": {
            "mode": "competitive",
            "name": "de_mirage",
            "phase": "live",
            "round": round_joues,
            "team_ct": {"score": 3, "consecutive_round_losses": 0},
            "team_t": {"score": 1, "consecutive_round_losses": 4},
        },
        "round": {"phase": "freezetime"},
        "player": {
            "steamid": observe or MOI,
            "name": "Coequipier" if observe else "Mathieu",
            "team": camp,
            "activity": "playing",
            "state": {
                "health": 100,
                "armor": 0,
                "helmet": False,
                "flashed": 0,
                "money": argent,
                "round_kills": 0,
                "round_killhs": 0,
                "equip_value": 200,
            },
            "weapons": {
                "weapon_0": {"name": "weapon_knife_t", "type": "Knife", "state": "holstered"},
                "weapon_1": {
                    "name": "weapon_glock",
                    "type": "Pistol",
                    "ammo_clip": 20,
                    "ammo_reserve": 120,
                    "state": "active",
                },
            },
            "match_stats": {"kills": 5, "assists": 1, "deaths": 4, "mvps": 0, "score": 12},
        },
        "auth": {"token": jeton},
    }


# --- Économie -----------------------------------------------------------------------------


def test_prime_defaite():
    assert [prime_defaite(n) for n in range(7)] == [1400, 1900, 2400, 2900, 3400, 3400, 3400]


@pytest.mark.parametrize(
    ("argent", "camp", "numero", "defaites", "nous", "eux", "attendu"),
    [
        (800, "T", 1, 0, 0, 0, "pistolet"),
        (800, "CT", 13, 0, 6, 6, "pistolet"),
        (2000, "T", 12, 0, 5, 6, "tout"),  # dernier round de la moitié
        (2000, "T", 20, 0, 7, 12, "tout"),  # balle de match adverse
        (5000, "CT", 6, 0, 3, 2, "complet"),  # 2900 + 1000 + 400 + 700 = 5000
        # T, 3 000 $, 2 défaites : 3 000 − 1 700 + 2 400 = 3 700 < 4 400 → éco
        (3000, "T", 6, 2, 1, 4, "eco"),
        # T, 3 500 $, 4 défaites : 3 500 − 1 700 + 3 400 = 5 200 ≥ 4 400 → force
        (3500, "T", 6, 4, 1, 4, "force"),
        (2000, "T", 8, 0, 6, 1, "eco"),  # on mène : rien n'empêche l'éco
    ],
)
def test_recommander(argent, camp, numero, defaites, nous, eux, attendu):
    assert recommander(argent, camp, numero, defaites, nous, eux).type == attendu


def test_recommandation_chiffree():
    r = recommander(3000, "T", 6, 2, 1, 4)
    assert r.argent_round_suivant_si_defaite == 5400
    assert "5400 $" in r.raison and "4400 $" in r.raison


# --- Résumé et réception --------------------------------------------------------------------


def test_resumer():
    r = resumer(message(argent=3500))
    assert (r["carte"], r["round"], r["camp"], r["score"]) == (
        "de_mirage",
        5,
        "T",
        {"nous": 1, "eux": 3},
    )
    assert r["joueur"]["argent"] == 3500 and r["joueur"]["kills"] == 5
    assert r["joueur"]["armes"][1] == {
        "nom": "glock",
        "type": "Pistol",
        "active": True,
        "munitions": 20,
        "reserve": 120,
    }
    assert r["recommandation"]["type"] == "force"  # 4 défaites consécutives côté T
    assert r["coequipiers"] is None  # jamais fourni à un joueur


def test_pas_de_conseil_d_achat_en_plein_round():
    m = message(argent=350)
    m["round"]["phase"] = "live"
    r = resumer(m)
    assert r["recommandation"] is None
    assert r["joueur"]["argent_si_defaite"] == 350 + 3400  # 4 défaites → prime maximale


def test_resumer_quand_mathieu_observe_un_coequipier():
    r = resumer(message(observe="76561198000000002"))
    assert r["observe"] == "Coequipier"
    assert r["joueur"] is None and r["recommandation"] is None


def test_resumer_avec_allplayers():
    m = message()
    m["allplayers"] = {
        MOI: {"name": "Mathieu", "team": "T", "state": {"money": 3500, "health": 100}},
        "2": {"name": "Coequipier", "team": "T", "state": {"money": 4100, "health": 100}},
        "3": {"name": "Adv", "team": "CT", "state": {"money": 9000, "health": 100}},
    }
    assert resumer(m)["coequipiers"] == [{"nom": "Coequipier", "argent": 4100, "vie": 100}]


def test_resumer_vide():
    assert resumer({})["actif"] is False


def test_recepteur_jeton_et_journal(tmp_path):
    r = RecepteurGSI(tmp_path, "bon-jeton")
    assert r.recevoir(message("mauvais")) is False
    assert r.resume == {"actif": False}
    assert r.recevoir(message("bon-jeton")) is True
    journal = next((tmp_path / "gsi").glob("journal_*.jsonl")).read_text(encoding="utf-8")
    ligne = json.loads(journal.splitlines()[0])
    assert "auth" not in ligne and ligne["map"]["name"] == "de_mirage"


def test_config_gsi(tmp_path):
    jeton = jeton_gsi(tmp_path)
    assert jeton == jeton_gsi(tmp_path) and len(jeton) == 32
    texte = texte_config("http://127.0.0.1:8765/api/cs2/gsi", jeton)
    texte.encode("ascii")  # ASCII strict : pas de BOM, pas d'accent
    assert f'"token" "{jeton}"' in texte and '"player_state"        "1"' in texte


# --- API et WebSocket ---------------------------------------------------------------------


@pytest.fixture
def client(base, cfg):
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        c.jeton = jeton_gsi(cfg.dossier_donnees)
        yield c


def test_api_gsi(client):
    assert client.post("/api/cs2/gsi", json=message("faux")).status_code == 401
    assert client.post("/api/cs2/gsi", content=b"pas du json").status_code == 400
    assert client.post("/api/cs2/gsi", json=message(client.jeton)).status_code == 200
    live = client.get("/api/cs2/live").json()
    assert live["joueur"]["argent"] == 3500 and live["rappel"] == []


def test_websocket_pousse_chaque_message(client):
    with client.websocket_connect("/api/cs2/live/ws") as ws:
        assert ws.receive_json()["actif"] is False
        debut = time.perf_counter()
        client.post("/api/cs2/gsi", json=message(client.jeton, argent=4000))
        recu = ws.receive_json()
        delai = time.perf_counter() - debut
    assert recu["joueur"]["argent"] == 4000
    # Mesure locale seulement : la latence réelle jeu → téléphone se vérifie sur le PC de jeu.
    assert delai < 0.5


def test_alerte_deathmatch_non_enregistre(client):
    m = message(client.jeton)
    m["map"]["mode"] = "deathmatch"
    client.post("/api/cs2/gsi", json=m)
    assert "F8" in client.get("/api/cs2/live").json()["alerte"]


def test_structure_du_match_par_mode():
    from postgame.live.economie_cs2 import moment, structure

    mr12, wingman = structure("premier"), structure("scrimcomp2v2")
    # Wingman : moitiés de 8, pistolet au round 9, balle de match à 8.
    assert moment(9, 3, wingman) == (True, False, False)
    assert moment(8, 2, wingman) == (False, True, False)
    assert moment(12, 8, wingman)[2] is True
    # Premier : pas de balle de match à 12-12 en prolongation (rounds 25 à 30, 4 sur 6).
    assert moment(25, 12, mr12) == (False, False, False)
    assert moment(27, 13, mr12) == (False, True, False)
    assert moment(29, 15, mr12)[2] is True
    assert moment(31, 15, mr12) == (False, False, False)  # 2e prolongation : 15-15
    assert moment(13, 4, mr12) == (True, False, False)
    assert moment(20, 12, mr12)[2] is True


def test_conseil_tout_depenser_pas_systematique_en_prolongation():
    from postgame.live.economie_cs2 import recommander

    reco = recommander(12500, "CT", 26, 0, 12, 12, "premier")
    assert reco.type == "complet"
