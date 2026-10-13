import os
from pathlib import Path

from postgame.importation import empreinte_fichier, importer, reanalyser


def _fichier(dossier: Path, nom: str, contenu: str) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / nom
    chemin.write_text(contenu, encoding="utf-8")
    return chemin


def test_import_cree_fiche_archive_et_mesures(tmp_path, base, cfg, factice):
    source = _fichier(tmp_path / "src", "match.factice", "carte=de_nuke\n")
    res = importer(source, base, cfg)
    assert res.statut == "importe", res.message
    p = base.partie(res.partie_id)
    assert (p.jeu, p.carte, p.resultat) == ("factice", "de_nuke", "victoire")
    archive = Path(p.fichier)
    assert archive.exists() and archive.parent == cfg.dossier_archives / "factice"
    assert p.empreinte == empreinte_fichier(source)
    assert base.mesures_partie(p.id)[0]["nom"] == "factice.taille"


def test_import_deux_fois_deduplique(tmp_path, base, cfg, factice):
    source = _fichier(tmp_path / "src", "a.factice", "carte=x")
    copie = _fichier(tmp_path / "ailleurs", "b.factice", "carte=x")
    premier = importer(source, base, cfg)
    second = importer(copie, base, cfg)
    assert second.statut == "deja_connu"
    assert second.partie_id == premier.partie_id
    assert base.compter_parties() == 1


def test_extension_inconnue_ignoree(tmp_path, base, cfg, factice):
    res = importer(_fichier(tmp_path, "notes.txt", "rien"), base, cfg)
    assert res.statut == "ignore"


def test_fichier_illisible_en_erreur_sans_archive(tmp_path, base, cfg, factice):
    res = importer(_fichier(tmp_path, "casse.factice", "illisible"), base, cfg)
    assert res.statut == "erreur"
    assert base.compter_parties() == 0
    assert not any((cfg.dossier_archives / "factice").iterdir())


def test_analyse_en_echec_garde_la_fiche(tmp_path, base, cfg, factice, monkeypatch):
    def plante(*_):
        raise RuntimeError("bug d'analyse")

    monkeypatch.setattr(factice, "analyser", plante)
    res = importer(_fichier(tmp_path, "m.factice", "x"), base, cfg)
    assert res.statut == "importe"
    assert "analyse en échec" in res.message
    assert base.partie(res.partie_id) is not None


def test_reanalyse(tmp_path, base, cfg, factice):
    res = importer(_fichier(tmp_path, "m.factice", "carte=de_ancient"), base, cfg)
    archive = Path(base.partie(res.partie_id).fichier)
    # Simule une nouvelle version de l'analyse : la carte lue change.
    archive.write_text("carte=de_anubis", encoding="utf-8")
    os.utime(archive)
    assert reanalyser(base, cfg) == {"ok": 1, "erreur": 0, "manquant": 0}
    assert base.partie(res.partie_id).carte == "de_anubis"
    archive.unlink()
    assert reanalyser(base, cfg)["manquant"] == 1
