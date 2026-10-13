"""Comptes liés (CPT-01) : SteamID appris par le pseudo, classements dans le temps."""

from postgame import comptes
from postgame.config import charger_config
from postgame.db import Partie


def test_steamid_appris_puis_reutilise(tmp_path, cfg):
    comptes.apprendre_de_la_partie(cfg, {"steamid_joueur": "76561198000000001"})
    assert cfg.steamid == "76561198000000001"
    (tmp_path / "postgame.toml").write_text(
        f'[service]\ndossier_donnees = "{cfg.dossier_donnees.as_posix()}"\n', encoding="utf-8"
    )
    assert charger_config(tmp_path / "postgame.toml").steamid == "76561198000000001"
    # Un SteamID déjà configuré n'est jamais remplacé.
    cfg.steamid = "1"
    comptes.apprendre_de_la_partie(cfg, {"steamid_joueur": "2"})
    assert cfg.steamid == "1"


def test_classements(base, cfg):
    for i, (mode, carte, valeur) in enumerate(
        [
            ("premier", "de_mirage", 14900),
            ("premier", "de_nuke", 15230),
            ("competitif", "de_anubis", 11),
            ("deathmatch", "de_dust2", 0),
        ]
    ):
        base.ajouter_partie(
            Partie(
                jeu="cs2",
                date_partie=f"2026-10-0{i + 1}T20:00:00+00:00",
                mode=mode,
                carte=carte,
                resultat="victoire",
                source="x",
                fichier="x",
                empreinte=str(i),
                details={"classement": valeur},
            )
        )
    base.ajouter_partie(
        Partie(
            jeu="lol",
            date_partie="2026-10-05T20:00:00+00:00",
            mode="classée solo",
            carte="Ahri",
            resultat="victoire",
            source="x",
            fichier="x",
            empreinte="l",
            details={
                "rang": [
                    {
                        "queueType": "RANKED_SOLO_5x5",
                        "tier": "GOLD",
                        "rank": "II",
                        "leaguePoints": 57,
                    }
                ]
            },
        )
    )
    s = comptes.classements(base)
    assert [p["valeur"] for p in s["premier"]] == [14900, 15230]
    assert s["competitif"][0]["contexte"] == {"carte": "de_anubis"}
    assert s["lol"][0]["contexte"]["palier"] == "GOLD II"
    cfg.riot_id = "iamheremyfriend#hiii"
    r = comptes.resume(cfg, base)
    assert r["riot"]["riot_id"] == "iamheremyfriend#hiii" and r["steam"]["steamid"] is None
