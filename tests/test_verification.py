from postgame.db import Mesure, Partie
from postgame.mesures import Preuve
from postgame.verification import fiche_verification


def test_fiche_verification(base):
    pid = base.ajouter_partie(
        Partie(
            jeu="cs2",
            date_partie="2026-10-01T20:00:00+00:00",
            mode="deathmatch",
            carte="de_dust2",
            resultat="sans_objet",
            source="a.dem",
            fichier="archives/a.dem",
            empreinte="e",
        )
    )
    base.remplacer_mesures(
        pid, [Mesure("cs2.contre_strafe.part_tirs_precis", 1, 62.5, "%", {"n": 40})]
    )
    base.remplacer_preuves(
        pid,
        [Preuve("cs2.contre_strafe.part_tirs_precis", 1200 + i, f"cas {i}", 1) for i in range(7)],
    )
    texte = fiche_verification(base, pid)
    assert "62.5 %" in texte
    assert texte.count("- [ ]") == 5
    assert "demo_gototick 1200" in texte
