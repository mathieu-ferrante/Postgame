import os

from postgame.surveillance import Surveillant


class Horloge:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_import_apres_stabilite(tmp_path, base, cfg, factice):
    dossier = tmp_path / "replays"
    dossier.mkdir()
    factice.dossiers = [dossier, tmp_path / "inexistant"]
    cfg.delai_stabilite_s = 10
    horloge = Horloge()
    s = Surveillant(base, cfg, horloge=horloge)

    demo = dossier / "match.factice"
    demo.write_text("carte=de_vertigo", encoding="utf-8")
    (dossier / "autre.txt").write_text("ignoré")

    assert s.passe() == []  # découvert, mis en attente
    assert s.en_attente() == [str(demo)]
    horloge.t = 5
    assert s.passe() == []  # pas encore stable assez longtemps

    # Le fichier grossit (enregistrement en cours) : le délai repart de zéro.
    demo.write_text("carte=de_vertigo\nsuite", encoding="utf-8")
    os.utime(demo, (1_000_000, 1_000_000))
    horloge.t = 12
    assert s.passe() == []
    horloge.t = 21
    assert s.passe() == []
    horloge.t = 23
    faits = s.passe()
    assert [(c.name, r.statut) for c, r in faits] == [("match.factice", "importe")]
    assert base.compter_parties() == 1
    assert base.fichier_vu(str(demo))["statut"] == "importe"

    # Fichier inchangé : plus rien à faire.
    horloge.t = 100
    assert s.passe() == [] and s.en_attente() == []


def test_fichier_reecrit_reimporte(tmp_path, base, cfg, factice):
    """Les démos DM tournent sur des noms fixes : un fichier réécrit est une nouvelle partie."""
    dossier = tmp_path / "csgo"
    dossier.mkdir()
    factice.dossiers = [dossier]
    s = Surveillant(base, cfg)  # délai de stabilité nul dans la config de test
    demo = dossier / "postgame_01.factice"
    demo.write_text("carte=a")
    s.passe()
    s.passe()
    demo.write_text("carte=bb")
    os.utime(demo, (2_000_000, 2_000_000))
    s.passe()
    s.passe()
    assert base.compter_parties() == 2


def test_erreur_notee_et_non_reessayee(tmp_path, base, cfg, factice):
    dossier = tmp_path / "d"
    dossier.mkdir()
    factice.dossiers = [dossier]
    s = Surveillant(base, cfg)
    (dossier / "casse.factice").write_text("illisible")
    s.passe()
    faits = s.passe()
    assert faits[0][1].statut == "erreur"
    assert s.passe() == [] and s.passe() == []


def test_plantage_d_import_note_une_seule_fois(tmp_path, base, cfg, factice, monkeypatch):
    import postgame.surveillance as surveillance

    dossier = tmp_path / "d"
    dossier.mkdir()
    factice.dossiers = [dossier]
    appels = []

    def importer_qui_plante(chemin, base, cfg):
        appels.append(chemin)
        raise KeyError("champ inattendu")

    monkeypatch.setattr(surveillance, "importer", importer_qui_plante)
    s = Surveillant(base, cfg)
    (dossier / "bizarre.factice").write_text("carte=a")
    s.passe()
    faits = s.passe()
    # Noté « erreur » et plus jamais réessayé tant que le fichier ne change pas.
    assert faits[0][1].statut == "erreur" and "champ inattendu" in faits[0][1].message
    assert s.passe() == [] and s.passe() == [] and len(appels) == 1
