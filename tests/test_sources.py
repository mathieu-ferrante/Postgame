"""Récupération automatique (AUTO-01) : codes de partage Steam et FACEIT (API simulées)."""

import gzip
import json

import httpx
import pytest

from postgame.games.cs2 import sources


def test_code_de_partage_exemple_public():
    # Exemple publié par les outils de la communauté (bibliothèque csgo-sharecode).
    d = sources.decoder_code("CSGO-GADqf-jjyJ8-cSP2r-smZRo-TO2xK")
    assert d == {
        "matchid": 3230642215713767580,
        "reservationid": 3230647599455273103,
        "port_tv": 55788,
    }
    assert sources.encoder_code(**d) == "CSGO-GADqf-jjyJ8-cSP2r-smZRo-TO2xK"
    with pytest.raises(ValueError):
        sources.decoder_code("CSGO-xxxxx")


def test_codes_steam(cfg):
    cfg.steamid, cfg.steam_code_connu = "76561198000000001", "CSGO-GADqf-jjyJ8-cSP2r-smZRo-TO2xK"
    cfg.secrets = {"steam": {"cle": "k", "code_historique": "AAAA-BBBBB-CCCC"}}
    suivants = [sources.encoder_code(1000 + i, 2000 + i, 27015) for i in range(2)]
    vus = []

    def repondre(req):
        vus.append(dict(req.url.params))
        if len(vus) <= 2:
            return httpx.Response(200, json={"result": {"nextcode": suivants[len(vus) - 1]}})
        return httpx.Response(202, json={"result": {"nextcode": "n/a"}})

    codes = sources.CodesSteam(cfg, httpx.Client(transport=httpx.MockTransport(repondre)))
    assert codes.synchroniser() == suivants
    assert vus[1]["knowncode"] == suivants[0] and vus[0]["steamidkey"] == "AAAA-BBBBB-CCCC"
    assert [c["matchid"] for c in codes.sans_demo()] == [1000, 1001]


def test_faceit(base, cfg, monkeypatch):
    cfg.faceit_pseudo = "JEANMARK"
    cfg.secrets = {"faceit": {"cle": "c", "jeton_telechargement": "j"}}
    demo = gzip.compress(b"contenu de demo")
    imports = []
    monkeypatch.setattr(
        sources,
        "importer",
        lambda chemin, b, c: (
            imports.append(chemin.read_bytes()) or type("R", (), {"statut": "importe"})()
        ),
    )

    def repondre(req):
        url = str(req.url)
        if "/players?" in url:
            return httpx.Response(200, json={"player_id": "p1"})
        if "/history" in url:
            return httpx.Response(
                200, json={"items": [{"match_id": "1-abc"}, {"match_id": "1-def"}]}
            )
        if url.endswith("/matches/1-abc"):
            return httpx.Response(
                200, json={"status": "FINISHED", "demo_url": ["https://demos/1-abc.dem.gz"]}
            )
        if url.endswith("/matches/1-def"):
            return httpx.Response(200, json={"status": "ONGOING"})
        if "download/v2" in url:
            assert req.headers["Authorization"] == "Bearer j"
            assert json.loads(req.content) == {"resource_url": "https://demos/1-abc.dem.gz"}
            return httpx.Response(200, json={"payload": {"download_url": "https://signe/x"}})
        if url == "https://signe/x":
            return httpx.Response(200, content=demo)
        return httpx.Response(404)

    collecteur = sources.CollecteurFaceit(
        base, cfg, httpx.Client(transport=httpx.MockTransport(repondre))
    )
    bilan = collecteur.synchroniser()
    assert bilan["importees"] == 1 and imports == [b"contenu de demo"]
    assert collecteur.synchroniser()["importees"] == 0  # déjà vue ; l'autre est en cours


def test_faceit_sans_jeton(base, cfg):
    cfg.secrets = {"faceit": {"cle": "c"}}
    with pytest.raises(sources.ErreurSource, match="jeton de téléchargement"):
        sources.CollecteurFaceit(base, cfg).lien_demo("x")
