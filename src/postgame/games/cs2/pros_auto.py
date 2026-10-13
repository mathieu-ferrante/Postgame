"""Import automatique des démos et extraits pros déposés dans un dossier (Google Drive…).

Mathieu (ou Postgame sur une autre machine) dépose dans le dossier configuré
(`[cs2] dossiers_pros`) des extraits .pgpro de quelques Mo, et s'il le veut les démos .dem
complètes (nécessaires seulement pour revoir un moment dans CS2). Le service les importe
seul, hors partie : un .pgpro en une seconde, un .dem en une à deux minutes. Le catalogue
des lineups et les cibles par arme sont reconstruits ensuite.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from postgame.db import Base
from postgame.games.base import ErreurLecture

journal = logging.getLogger(__name__)

EXTENSIONS = (".pgpro", ".dem")


def a_importer(dossiers: list[Path], deja_vus: set[str]) -> list[Path]:
    """Fichiers pros pas encore vus, extraits d'abord (rapides), puis démos."""
    fichiers = []
    for d in dossiers:
        if d.is_dir():
            fichiers += [f for f in d.rglob("*") if f.suffix.lower() in EXTENSIONS and f.is_file()]
    nouveaux = [f for f in fichiers if str(f.resolve()) not in deja_vus]
    return sorted(nouveaux, key=lambda f: (f.suffix.lower() != ".pgpro", f.name))


def synchroniser(
    base: Base,
    dossiers: list[Path],
    deja_vus: set[str],
    peut_lire_demo: Callable[[], bool] = lambda: True,
    dossier_extraits: Path | None = None,
) -> dict[str, str]:
    """Importe les nouveaux fichiers ; une démo .dem n'est lue que si `peut_lire_demo()`
    (pas de jeu en cours). Reconstruit le catalogue si quelque chose a été ajouté."""
    from postgame.games.cs2 import references

    bilan: dict[str, str] = {}
    for f in a_importer(dossiers, deja_vus):
        if f.suffix.lower() == ".dem" and not peut_lire_demo():
            bilan[f.name] = "reportée (jeu en cours)"
            continue
        try:
            bilan[f.name] = references.ajouter_demo_pro(base, f, dossier_extraits)
        except (ErreurLecture, OSError, ValueError) as exc:
            bilan[f.name] = f"erreur : {exc}"
            journal.warning("pro %s : %s", f, exc)
        deja_vus.add(str(f.resolve()))
    if any(v.startswith("ajoutee") for v in bilan.values()):
        bilan["catalogue"] = str(references.reconstruire_catalogue(base))
    return bilan
