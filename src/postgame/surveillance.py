"""Surveillance des dossiers de démos / journaux (COM-01).

Choix : scrutation périodique plutôt qu'évènements du système de fichiers. Deux dossiers à
lire toutes les 5 s ne coûtent rien, et la scrutation gère naturellement le cas clé : une
démo en cours d'écriture (enregistrement `record` en cours, téléchargement Premier) n'est
importée qu'une fois sa taille stable pendant `delai_stabilite_s`.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from postgame.config import Config
from postgame.db import Base
from postgame.games import MODULES
from postgame.importation import ResultatImport, importer

journal = logging.getLogger(__name__)


@dataclass
class _EnAttente:
    taille: int
    mtime: float
    stable_depuis: float


class Surveillant:
    def __init__(self, base: Base, cfg: Config, horloge=time.monotonic, garde=None):
        self.base = base
        self.cfg = cfg
        self.garde = garde  # PERF-01 : reporte les imports pendant une partie
        self.reportes: set[str] = set()
        self._horloge = horloge
        self._attente: dict[str, _EnAttente] = {}
        self._arret = threading.Event()
        self._fil: threading.Thread | None = None
        self.derniere_passe: float | None = None

    def dossiers(self) -> list[tuple[str, Path]]:
        return [(m.nom, d) for m in MODULES.values() for d in m.dossiers_surveilles(self.cfg)]

    def passe(self) -> list[tuple[Path, ResultatImport]]:
        """Une passe de scrutation ; renvoie les imports réalisés (utile aux tests)."""
        faits: list[tuple[Path, ResultatImport]] = []
        maintenant = self._horloge()
        vus: set[str] = set()
        for nom_jeu, dossier in self.dossiers():
            if not dossier.is_dir():
                continue
            extensions = MODULES[nom_jeu].extensions
            try:
                entrees = list(dossier.iterdir())
            except OSError as exc:
                journal.warning("dossier illisible %s : %s", dossier, exc)
                continue
            for chemin in entrees:
                if chemin.suffix.lower() not in extensions or not chemin.is_file():
                    continue
                cle = str(chemin)
                vus.add(cle)
                try:
                    st = chemin.stat()
                except OSError:
                    continue
                connu = self.base.fichier_vu(cle)
                if connu and connu["taille"] == st.st_size and connu["mtime"] == st.st_mtime:
                    continue  # déjà traité dans cet état
                attente = self._attente.get(cle)
                if attente is None or (attente.taille, attente.mtime) != (st.st_size, st.st_mtime):
                    self._attente[cle] = _EnAttente(st.st_size, st.st_mtime, maintenant)
                    continue
                if maintenant - attente.stable_depuis < self.cfg.delai_stabilite_s:
                    continue
                cout = getattr(MODULES[nom_jeu], "cout", "leger")
                if self.garde is not None and self.garde.doit_attendre(cout):
                    self.reportes.add(cle)  # importé dès la fin de la partie
                    continue
                self.reportes.discard(cle)
                del self._attente[cle]
                try:
                    resultat = importer(chemin, self.base, self.cfg)
                except Exception as exc:
                    # Noté en erreur : le fichier n'est pas réimporté en boucle (il le sera
                    # s'il change, ou par « reanalyser » une fois le défaut corrigé).
                    journal.exception("import de %s en échec", chemin)
                    resultat = ResultatImport("erreur", f"import en échec : {exc}", None)
                self.base.noter_fichier(
                    cle,
                    st.st_size,
                    st.st_mtime,
                    resultat.statut,
                    resultat.message,
                    resultat.partie_id,
                )
                journal.info("%s : %s (%s)", chemin.name, resultat.statut, resultat.message)
                faits.append((chemin, resultat))
        # Oublier les fichiers disparus pendant leur attente.
        for cle in list(self._attente):
            if cle not in vus:
                del self._attente[cle]
        self.derniere_passe = time.time()
        return faits

    def en_attente(self) -> list[str]:
        return sorted(self._attente)

    def demarrer(self) -> None:
        if self._fil and self._fil.is_alive():
            return
        self._arret.clear()
        self._fil = threading.Thread(target=self._boucle, name="surveillance", daemon=True)
        self._fil.start()

    def arreter(self) -> None:
        self._arret.set()
        if self._fil:
            self._fil.join(timeout=5)

    def _boucle(self) -> None:
        while not self._arret.is_set():
            try:
                self.passe()
            except Exception:
                journal.exception("passe de surveillance en échec")
            self._arret.wait(self.cfg.intervalle_s)
