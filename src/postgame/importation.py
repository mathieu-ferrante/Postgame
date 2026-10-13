"""Import d'un fichier (démo, journal) : déduplication, archivage, fiche, mesures.

Le fichier source est copié dans data/archives/<jeu>/ avant analyse : les démos Premier
sont purgées par le jeu au bout de quelques semaines, et les démos de DM enregistrées avec
des noms tournants seraient écrasées. L'analyse lit toujours la copie archivée.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from postgame.config import Config
from postgame.db import Base, Partie
from postgame.games import module_pour
from postgame.games.base import ErreurLecture
from postgame.mesures import ResultatAnalyse

journal = logging.getLogger(__name__)


@dataclass
class ResultatImport:
    statut: str  # importe, deja_connu, ignore, erreur
    message: str = ""
    partie_id: int | None = None


def empreinte_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def importer(
    chemin: Path, base: Base, cfg: Config, nom_origine: str | None = None
) -> ResultatImport:
    """Importe un fichier. `nom_origine` sert quand le fichier est une copie temporaire
    (téléversement depuis l'interface)."""
    chemin = Path(chemin)
    module = module_pour(Path(nom_origine) if nom_origine else chemin)
    if module is None:
        return ResultatImport("ignore", f"extension non prise en charge : {chemin.suffix}")

    try:
        empreinte = empreinte_fichier(chemin)
    except OSError as exc:
        return ResultatImport("erreur", f"lecture impossible : {exc}")

    existante = base.partie_par_empreinte(empreinte)
    if existante is not None:
        return ResultatImport("deja_connu", "fichier déjà importé", existante.id)

    date = datetime.fromtimestamp(chemin.stat().st_mtime)
    dossier = cfg.dossier_archives / module.nom
    dossier.mkdir(parents=True, exist_ok=True)
    archive = dossier / f"{date:%Y%m%d-%H%M%S}_{empreinte[:12]}{chemin.suffix.lower()}"
    shutil.copy2(chemin, archive)

    try:
        fiche = module.lire_fiche(archive, cfg)
    except ErreurLecture as exc:
        archive.unlink(missing_ok=True)
        return ResultatImport("erreur", str(exc))

    partie = Partie(
        jeu=module.nom,
        date_partie=fiche.date_partie,
        mode=fiche.mode,
        carte=fiche.carte,
        resultat=fiche.resultat,
        score_joueur=fiche.score_joueur,
        score_adverse=fiche.score_adverse,
        duree_s=fiche.duree_s,
        details=fiche.details,
        source=str(nom_origine or chemin),
        fichier=str(archive),
        empreinte=empreinte,
    )
    partie_id = base.ajouter_partie(partie)

    # Les mesures ne doivent jamais faire perdre la fiche : une analyse en échec se rejoue
    # plus tard par la re-analyse.
    try:
        enregistrer_analyse(base, partie_id, module.analyser(archive, cfg))
    except Exception as exc:
        journal.exception("analyse en échec pour %s", archive)
        return ResultatImport("importe", f"fiche créée, analyse en échec : {exc}", partie_id)

    if cfg.debrief.automatique:
        try:
            from postgame.debrief import generer_debrief

            generer_debrief(base, cfg, partie_id)
        except Exception:
            journal.exception("débrief automatique en échec pour la partie %s", partie_id)

    return ResultatImport("importe", f"{module.libelle} — {fiche.carte}, {fiche.mode}", partie_id)


def enregistrer_analyse(base: Base, partie_id: int, resultat: ResultatAnalyse) -> None:
    base.remplacer_mesures(partie_id, resultat.mesures)
    base.remplacer_preuves(partie_id, resultat.preuves)


def reanalyser(base: Base, cfg: Config, jeu: str | None = None) -> dict[str, int]:
    """Recalcule fiches et mesures de tout l'historique à partir des archives (COM-08)."""
    bilan = {"ok": 0, "erreur": 0, "manquant": 0}
    decalage = 0
    while True:
        lot = base.lister_parties(jeu=jeu, limite=200, decalage=decalage)
        if not lot:
            break
        decalage += len(lot)
        for partie in lot:
            archive = Path(partie.fichier)
            module = module_pour(archive)
            if module is None or not archive.exists():
                bilan["manquant"] += 1
                continue
            try:
                fiche = module.lire_fiche(archive, cfg)
                for cle in (
                    "date_partie",
                    "mode",
                    "carte",
                    "resultat",
                    "score_joueur",
                    "score_adverse",
                    "duree_s",
                    "details",
                ):
                    setattr(partie, cle, getattr(fiche, cle))
                base.mettre_a_jour_fiche(partie)
                enregistrer_analyse(base, partie.id, module.analyser(archive, cfg))
                bilan["ok"] += 1
            except Exception:
                journal.exception("re-analyse en échec pour %s", archive)
                bilan["erreur"] += 1
    return bilan
