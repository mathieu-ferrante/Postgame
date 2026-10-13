"""Point d'entrée de l'analyse d'une démo CS2 : enchaîne tous les analyseurs."""

from __future__ import annotations

from postgame.games.cs2.decisions import analyser_decisions, decouper_rounds
from postgame.games.cs2.donnees import DonneesMatch, Positions
from postgame.games.cs2.economie import analyser_economie
from postgame.games.cs2.mecanique import analyser_mecanique
from postgame.games.cs2.positionnement import analyser_positionnement
from postgame.games.cs2.references import Catalogue, analyser_references
from postgame.games.cs2.utilitaires import analyser_utilitaires
from postgame.mesures import ResultatAnalyse


def analyser_match(d: DonneesMatch, catalogue: Catalogue | None = None) -> ResultatAnalyse:
    pos = Positions(d.ticks)
    r = analyser_mecanique(d)
    r.etendre(analyser_utilitaires(d, pos))
    r.etendre(analyser_positionnement(d, pos))
    r.etendre(analyser_references(d, catalogue or Catalogue(), pos))
    r.etendre(analyser_decisions(d, pos))
    if not d.est_deathmatch():
        r.etendre(analyser_economie(d, pos, decouper_rounds(d, pos)))
    return r
