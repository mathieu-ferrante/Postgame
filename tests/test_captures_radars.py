"""Captures d'écran Steam et export des radars officiels (sans le jeu : faux dossiers)."""

import os

from postgame.games.cs2 import captures, radar


def test_dossiers_et_capture(tmp_path):
    steam = tmp_path / "Steam"
    for compte in ("111", "222"):
        (steam / "userdata" / compte / "760" / "remote" / "730" / "screenshots").mkdir(parents=True)
    tous = captures.dossiers_captures(steam)
    assert len(tous) == 2
    # SteamID64 connu : seulement le dossier de ce compte.
    assert captures.dossiers_captures(steam, str(76561197960265728 + 222)) == [
        steam / "userdata" / "222" / "760" / "remote" / "730" / "screenshots"
    ]
    d = tous[0]
    for nom, instant in (("a.jpg", 100), ("b.jpg", 300), ("c.jpg", 200), ("d.txt", 250)):
        (d / nom).write_bytes(b"x")
        os.utime(d / nom, (instant, instant))
    assert captures.capture_depuis(tous, 150).name == "c.jpg"  # la première après la demande
    assert captures.capture_depuis(tous, 300) is None


def test_attentes_expirent():
    a = captures.Attentes()
    a.demander("s1", maintenant=1000)
    assert a.depuis("s1", maintenant=1060) == 1000
    assert a.depuis("s1", maintenant=1000 + captures.DUREE_ATTENTE_S + 1) is None
    assert a.depuis("s1", maintenant=1001) is None  # oubliée


def test_ranger_les_radars(tmp_path):
    sortie = tmp_path / "export"
    images = sortie / "panorama" / "images" / "overheadmaps"
    textes = sortie / "resource" / "overviews"
    images.mkdir(parents=True)
    textes.mkdir(parents=True)
    (images / "de_nuke_radar_psd.png").write_bytes(b"haut")
    (images / "de_nuke_lower_radar_psd.png").write_bytes(b"bas")
    (images / "de_mirage_radar_psd.png").write_bytes(b"mirage")
    (textes / "de_nuke.txt").write_text('"pos_x" "-3453"')
    bilan = radar.ranger(sortie, tmp_path / "data", ["de_nuke", "de_mirage", "de_cache"])
    assert bilan["de_nuke"] == "exporté"
    assert bilan["de_mirage"].startswith("exporté (sans description")
    assert bilan["de_cache"] == "radar absent des fichiers du jeu"
    assert (tmp_path / "data" / "radars" / "de_nuke_lower.png").read_bytes() == b"bas"
    assert radar.manquants(tmp_path / "data", ["de_nuke", "de_cache"]) == ["de_cache"]
    commande = radar.commande_export(tmp_path / "S2V.exe", tmp_path / "pak01_dir.vpk", sortie)
    assert commande[commande.index("--vpk_extensions") + 1] == "vtex_c,txt"
