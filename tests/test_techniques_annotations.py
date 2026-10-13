"""Technique de lancer et annotations CS2 (STUFF-01), sur cas construits à la main."""

import math
import re

import pandas as pd
from fastapi.testclient import TestClient

from postgame.api import creer_app
from postgame.games.cs2 import annotations_jeu as annotations
from postgame.games.cs2.techniques import (
    lachers,
    reconnaitre,
    technique_majoritaire,
    techniques_des_lancers,
)


def avant(**colonnes):
    """3 ticks avant le lancer ; chaque argument : liste de 3 valeurs ou valeur constante."""
    lignes = {k: (v if isinstance(v, list) else [v] * 3) for k, v in colonnes.items()}
    return pd.DataFrame({"tick": [97, 98, 99], **lignes})


def test_techniques():
    immobile = dict(vx=0.0, vy=0.0, en_l_air=False, accroupi=False)
    assert reconnaitre(avant(FIRE=True, **immobile)).libelle == "immobile, clic gauche"
    assert (
        reconnaitre(
            avant(
                FIRE=True,
                JUMP=[False, False, True],
                **{**immobile, "en_l_air": [False, False, True]},
            )
        ).libelle
        == "jumpthrow (clic gauche)"
    )
    assert (
        reconnaitre(
            avant(
                FIRE=True,
                JUMP=[False, False, True],
                FORWARD=True,
                vx=250.0,
                vy=0.0,
                en_l_air=False,
                accroupi=False,
            )
        ).libelle
        == "W + saut + clic gauche"
    )
    assert (
        reconnaitre(avant(RIGHTCLICK=True, DUCK=True, **immobile)).libelle
        == "accroupi + clic droit"
    )
    assert (
        reconnaitre(
            avant(
                FIRE=True,
                RIGHTCLICK=True,
                WALK=True,
                vx=80.0,
                vy=0.0,
                en_l_air=False,
                accroupi=False,
            )
        ).libelle
        == "en marchant + clic gauche + droit"
    )
    # Démo sans les touches : saut vu par « en l'air », clic inconnu.
    assert (
        reconnaitre(avant(vx=0.0, vy=0.0, en_l_air=[False, False, True], accroupi=False)).libelle
        == "jumpthrow (clic ?)"
    )


def test_technique_majoritaire_et_association():
    assert technique_majoritaire(
        ["jumpthrow (clic gauche)"] * 3 + ["immobile, clic gauche", None]
    ) == ("jumpthrow (clic gauche)", 0.75)
    assert technique_majoritaire([None]) == (None, None)
    # Schéma réel (démo ESL Pro League S24) : clic tenu, relâché au décollage, et
    # grenade_thrown enregistré 6 ticks plus tard ; le pro a déjà tourné la tête.
    ticks = list(range(90, 101))
    etats = pd.DataFrame(
        {
            "tick": ticks,
            "steamid": "A",
            "FIRE": [t < 94 for t in ticks],
            "vx": 0.0,
            "vy": 0.0,
            "en_l_air": [t >= 94 for t in ticks],
            "accroupi": False,
            "x": [float(t) for t in ticks],
            "y": 0.0,
            "z": 0.0,
            "pitch": [-40.0 if t <= 94 else 5.0 for t in ticks],
            "yaw": [170.0 if t <= 94 else 90.0 for t in ticks],
        }
    )
    lancers = pd.DataFrame({"tick": [100], "steamid": ["A"], "type": ["smoke"]})
    assert techniques_des_lancers(etats, lancers) == {("A", 100): "jumpthrow (clic gauche)"}
    lacher = lachers(etats, lancers)[("A", 100)]
    assert (lacher.tick, lacher.x, lacher.pitch, lacher.yaw) == (94, 94.0, -40.0, 170.0)


def test_saut_puis_lancer_en_l_air():
    # Décollage 10 ticks avant le lâcher : ce n'est pas un jumpthrow.
    ticks = list(range(80, 101))
    etats = pd.DataFrame(
        {
            "tick": ticks,
            "steamid": "A",
            "FIRE": [t < 95 for t in ticks],
            "vx": 0.0,
            "vy": 0.0,
            "en_l_air": [85 <= t <= 99 for t in ticks],
            "accroupi": False,
        }
    )
    lancers = pd.DataFrame({"tick": [100], "steamid": ["A"], "type": ["flash"]})
    assert techniques_des_lancers(etats, lancers)[("A", 100)] == "en l'air + clic gauche"


STUFF = {
    "cle": "abc",
    "type": "smoke",
    "nom": "Smoke Window depuis TSpawn",
    "x": 500.0,
    "y": 0.0,
    "z": -160.0,
    "lx": 1000.0,
    "ly": 0.0,
    "lz": -168.0,
    "lpitch": -30.0,
    "lyaw": 180.0,
    "technique": "jumpthrow (clic gauche)",
    "part_technique": 0.8,
}


def test_annotations():
    texte = annotations.generer("de_mirage", [STUFF, {**STUFF, "cle": "x", "lx": None}])
    assert texte.startswith("<!-- kv3 encoding:text") and 'MapName = "de_mirage"' in texte
    assert texte.count('Type = "grenade"') == 3  # 3 nœuds pour l'unique stuff complet
    assert 'SubType = "main"' in texte and "JumpThrow = true" in texte
    assert 'Text = "jumpthrow (clic gauche) (80 % des pros)"' in texte
    # Point visé : œil (z + 64) + 100 u dans la direction yaw 180°, pitch −30° (vers le haut).
    bloc = texte.split('SubType = "aim_target"')[1]
    x, y, z = map(float, re.search(r"Position = \[ ([^\]]+) \]", bloc).group(1).split(", "))
    assert math.isclose(x, 1000 - 100 * math.cos(math.radians(30)), abs_tol=1e-3)
    assert math.isclose(y, 0.0, abs_tol=1e-3)
    assert math.isclose(z, -168 + 64 + 100 * math.sin(math.radians(30)), abs_tol=1e-3)
    # Identifiants stables : régénérer donne le même fichier.
    assert texte == annotations.generer("de_mirage", [STUFF, {**STUFF, "cle": "x", "lx": None}])


def test_api_annotations_et_image(base, cfg, tmp_path):
    with base.transaction() as cx:
        cx.execute(
            "INSERT INTO cs2_ref_lancers (carte, type, x, y, z, lx, ly, lz, lieu_arrivee, "
            "lieu_lancer, nb, nb_demos, lpitch, lyaw, part_saut, part_accroupi, technique, "
            "part_technique, cle, construit_le) VALUES ('de_cache', 'smoke', 500, 0, -160, "
            "1000, 0, -168, 'Mid', 'TSpawn', 9, 3, -30, 180, 1, 0, 'jumpthrow (clic gauche)', "
            "0.8, 'abc', 'x')"
        )
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        r = c.get("/api/cs2/stuffs/annotations?carte=de_cache")
        assert r.status_code == 200 and 'MapName = "de_cache"' in r.text
        installe = c.post("/api/cs2/stuffs/annotations?carte=de_cache").json()
        assert installe["commande"] == "annotation_load postgame_de_cache"
        assert (
            c.post("/api/cs2/stuffs/abc/image", files={"fichier": ("vue.txt", b"x")}).status_code
            == 415
        )
        assert (
            c.post(
                "/api/cs2/stuffs/abc/image", files={"fichier": ("vue.png", b"\x89PNG")}
            ).status_code
            == 200
        )
        assert c.get("/api/cs2/stuffs/abc/image").content == b"\x89PNG"
        stuff = c.get("/api/cs2/stuffs?carte=de_cache").json()["stuffs"][0]
        assert stuff["image"] == "/api/cs2/stuffs/abc/image"
        assert stuff["technique"] == "jumpthrow (clic gauche) (80 % des pros)"
