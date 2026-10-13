"""Aucune analyse pendant une partie (PERF-01).

Lire une démo CS2 et la tout analyser prend plusieurs secondes de processeur à pleine
charge : hors de question pendant une partie. Règles :
- tant qu'un jeu suivi tourne (processus du jeu) ou qu'un flux GSI arrive, les fichiers
  « lourds » (démos CS2) restent en attente ; ils sont importés dès la fermeture du jeu ;
- les fichiers « légers » (séances Geometry Dash, parties LoL / TFT reçues de l'API) ne
  sont reportés que pendant une partie de CS2 ou de LoL, où chaque image compte ;
- le service tourne en priorité basse : Windows lui donne le processeur en dernier.

Le second écran (GSI, API locale LoL) reste actif : il ne fait que lire de petits messages.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable

journal = logging.getLogger(__name__)

# Nom du processus (en minuscules) → jeu. Le lanceur LoL (LeagueClient) n'est pas une partie.
PROCESSUS_JEUX = {
    "cs2.exe": "cs2",
    "league of legends.exe": "lol",
    "geometrydash.exe": "gd",
}
JEUX_EXIGEANTS = {"cs2", "lol"}  # pendant ces jeux, même les petits imports attendent
DUREE_GSI_ACTIF_S = 30.0


def processus_en_cours() -> list[str]:
    import psutil

    noms = []
    for p in psutil.process_iter(["name"]):
        nom = p.info.get("name")
        if nom:
            noms.append(nom)
    return noms


class Garde:
    """Dit si un jeu est en cours et si un import doit attendre."""

    def __init__(
        self,
        lister: Callable[[], Iterable[str]] = processus_en_cours,
        dernier_gsi: Callable[[], float | None] = lambda: None,
        horloge: Callable[[], float] = time.time,
        cache_s: float = 5.0,
    ):
        self.lister, self.dernier_gsi, self.horloge = lister, dernier_gsi, horloge
        self.cache_s = cache_s
        self._cache: tuple[float, set[str]] | None = None

    def jeux_en_cours(self) -> set[str]:
        maintenant = self.horloge()
        if self._cache and maintenant - self._cache[0] < self.cache_s:
            return self._cache[1]
        try:
            jeux = {PROCESSUS_JEUX[n.lower()] for n in self.lister() if n.lower() in PROCESSUS_JEUX}
        except Exception:  # liste des processus inaccessible : on ne bloque rien
            jeux = set()
        gsi = self.dernier_gsi()
        if gsi is not None and maintenant - gsi < DUREE_GSI_ACTIF_S:
            jeux.add("cs2")
        self._cache = (maintenant, jeux)
        return jeux

    def doit_attendre(self, cout: str) -> bool:
        jeux = self.jeux_en_cours()
        if cout == "lourd":
            return bool(jeux)
        return bool(jeux & JEUX_EXIGEANTS)


def abaisser_priorite() -> None:
    """Priorité « inférieure à la normale » pour tout le service (Windows), « nice 10 » sinon."""
    try:
        import psutil

        p = psutil.Process()
        p.nice(
            psutil.BELOW_NORMAL_PRIORITY_CLASS
            if hasattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS")
            else 10
        )
    except Exception as exc:
        journal.warning("priorité basse impossible : %s", exc)
