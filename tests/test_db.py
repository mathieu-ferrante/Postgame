import sqlite3

import pytest

from postgame.db import MIGRATIONS, Base, Mesure, Partie


def _partie(empreinte: str = "a" * 64, date: str = "2026-10-01T20:00:00+00:00") -> Partie:
    return Partie(
        jeu="cs2",
        date_partie=date,
        mode="competitif",
        carte="de_mirage",
        resultat="victoire",
        source="x.dem",
        fichier="y.dem",
        empreinte=empreinte,
        score_joueur=13,
        score_adverse=9,
        details={"joueur": "Mathieu"},
    )


def test_schema_cree_et_versionne(base: Base):
    assert base.version_schema == len(MIGRATIONS)


def test_migration_idempotente(cfg):
    Base(cfg.chemin_base).fermer()
    b = Base(cfg.chemin_base)
    assert b.version_schema == len(MIGRATIONS)
    b.fermer()


def test_ajout_et_lecture_partie(base: Base):
    pid = base.ajouter_partie(_partie())
    p = base.partie(pid)
    assert p.carte == "de_mirage"
    assert p.details == {"joueur": "Mathieu"}
    assert p.importe_le
    assert base.partie_par_empreinte("a" * 64).id == pid


def test_empreinte_unique(base: Base):
    base.ajouter_partie(_partie())
    with pytest.raises(sqlite3.IntegrityError):
        base.ajouter_partie(_partie())


def test_liste_ordre_et_filtre(base: Base):
    base.ajouter_partie(_partie("a" * 64, "2026-10-01T20:00:00+00:00"))
    base.ajouter_partie(_partie("b" * 64, "2026-10-03T20:00:00+00:00"))
    liste = base.lister_parties()
    assert [p.empreinte[0] for p in liste] == ["b", "a"]
    assert base.lister_parties(jeu="gd") == []
    assert base.compter_parties("cs2") == 2


def test_mesures_remplacees_et_serie(base: Base):
    p1 = base.ajouter_partie(_partie("a" * 64, "2026-10-01T20:00:00+00:00"))
    p2 = base.ajouter_partie(_partie("b" * 64, "2026-10-03T20:00:00+00:00"))
    base.remplacer_mesures(p1, [Mesure("cs2.m", 1, 0.5, "%", {"arme": "ak47"})])
    base.remplacer_mesures(
        p2,
        [
            Mesure("cs2.m", 1, 0.7, "%", {"arme": "ak47"}),
            Mesure("cs2.m", 1, 0.2, "%", {"arme": "m4a1"}),
        ],
    )
    # Remplacement : la nouvelle version écrase l'ancienne.
    base.remplacer_mesures(p1, [Mesure("cs2.m", 2, 0.6, "%", {"arme": "ak47"})])
    serie = base.serie_mesure("cs2.m", contexte={"arme": "ak47"})
    assert [(s["partie_id"], s["valeur"], s["version"]) for s in serie] == [
        (p1, 0.6, 2),
        (p2, 0.7, 1),
    ]
    assert len(base.serie_mesure("cs2.m", depuis="2026-10-02")) == 2
    assert base.noms_mesures() == ["cs2.m"]


def test_suppression_partie_supprime_mesures(base: Base):
    pid = base.ajouter_partie(_partie())
    base.remplacer_mesures(pid, [Mesure("x", 1, 1.0)])
    with base.transaction() as cx:
        cx.execute("DELETE FROM parties WHERE id = ?", (pid,))
    assert base.mesures_partie(pid) == []


def test_fichiers_vus_upsert(base: Base):
    base.noter_fichier("c:/a.dem", 10, 1.0, "erreur", "tronqué")
    base.noter_fichier("c:/a.dem", 20, 2.0, "importe", "", 3)
    vu = base.fichier_vu("c:/a.dem")
    assert (vu["taille"], vu["statut"], vu["partie_id"]) == (20, "importe", 3)
    assert len(base.derniers_fichiers()) == 1
