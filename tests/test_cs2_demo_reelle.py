"""Tests sur vraies démos CS2, déposées dans tests/donnees/ (ignoré par git).

Ignorés tant qu'aucune démo n'est présente. Ce sont eux qui valident pour de bon la
lecture de la fiche (L0) : tant qu'ils n'ont pas tourné, la fiche CS2 n'est pas vérifiée.
"""

import pytest
from conftest import DOSSIER_DONNEES_TEST

from postgame.config import charger_config
from postgame.games.cs2.demo import construire_fiche, extraire

DEMOS = sorted(DOSSIER_DONNEES_TEST.glob("*.dem")) if DOSSIER_DONNEES_TEST.exists() else []

pytestmark = [
    pytest.mark.demo_reelle,
    pytest.mark.skipif(not DEMOS, reason="aucune démo réelle dans tests/donnees/"),
]


@pytest.mark.parametrize("demo", DEMOS, ids=lambda p: p.name)
def test_fiche_coherente(demo):
    donnees = extraire(demo)
    fiche = construire_fiche(donnees, charger_config().steamid)
    assert fiche.carte.startswith(("de_", "cs_", "ar_", "dz_"))
    assert fiche.duree_s and fiche.duree_s > 0
    assert fiche.mode in {"premier", "competitif", "faceit", "deathmatch", "wingman", "autre"}
    assert fiche.details["nb_joueurs"] > 0
