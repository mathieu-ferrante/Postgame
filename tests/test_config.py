from pathlib import Path

from postgame.config import Config, charger_config


def test_defauts_sans_fichier(tmp_path):
    cfg = charger_config(tmp_path / "absent.toml")
    assert cfg.port == Config().port
    assert cfg.steamid == ""


def test_lecture_fichier(tmp_path):
    chemin = tmp_path / "postgame.toml"
    chemin.write_text(
        '[service]\nport = 9000\ndossier_donnees = "mes_donnees"\n'
        '[joueur]\nsteamid = " 76561198000000001 "\n'
        '[cs2]\ndossiers_demos = ["D:/demos"]\n'
        "[surveillance]\ndelai_stabilite_s = 3\n",
        encoding="utf-8",
    )
    cfg = charger_config(chemin)
    assert cfg.port == 9000
    assert cfg.dossier_donnees == tmp_path / "mes_donnees"
    assert cfg.steamid == "76561198000000001"
    assert cfg.dossiers_cs2 == [Path("D:/demos")]
    assert cfg.delai_stabilite_s == 3.0


def test_fichier_exemple_valide():
    exemple = Path(__file__).parent.parent / "postgame.exemple.toml"
    cfg = charger_config(exemple)
    assert len(cfg.dossiers_cs2) == 2
