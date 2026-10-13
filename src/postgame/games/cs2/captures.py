"""Vraies vues de visée pour les stuffs : captures d'écran Steam (F12) prises dans la démo.

Mathieu demande « Capturer la vue du pro » : Postgame ouvre la démo pro au lancer, en
pause, caméra sur le pro (voir revoir.py). Mathieu appuie sur F12 ; Steam enregistre la
capture dans userdata/<compte>/760/remote/730/screenshots/. Postgame repère la première
capture prise après la demande et la joint au stuff. Aucune capture d'écran n'est faite
par Postgame lui-même.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

DECALAGE_STEAMID64 = 76561197960265728
DUREE_ATTENTE_S = 15 * 60  # une demande de capture expire au bout de 15 minutes
EXTENSIONS = {".jpg", ".jpeg", ".png"}


def dossiers_captures(dossier_steam: Path, steamid: str = "") -> list[Path]:
    """Dossiers de captures CS2 (appid 730) : celui du compte de Mathieu s'il est connu,
    sinon ceux de tous les comptes Steam de la machine."""
    userdata = dossier_steam / "userdata"
    if steamid.isdigit() and int(steamid) > DECALAGE_STEAMID64:
        comptes = [userdata / str(int(steamid) - DECALAGE_STEAMID64)]
    else:
        comptes = [d for d in userdata.iterdir() if d.is_dir()] if userdata.is_dir() else []
    return [c / "760" / "remote" / "730" / "screenshots" for c in comptes]


def capture_depuis(dossiers: list[Path], depuis: float) -> Path | None:
    """Première capture (la plus ancienne) prise après l'instant `depuis` (horodatage)."""
    candidates = []
    for d in dossiers:
        if not d.is_dir():
            continue
        for f in d.iterdir():  # pas de récursion : les vignettes sont dans thumbnails/
            if f.suffix.lower() in EXTENSIONS and f.is_file():
                mtime = f.stat().st_mtime
                if mtime > depuis:
                    candidates.append((mtime, f))
    return min(candidates)[1] if candidates else None


@dataclass
class Attentes:
    """Demandes de capture en cours : clé du stuff → instant de la demande."""

    demandes: dict[str, float] = field(default_factory=dict)

    def demander(self, cle: str, maintenant: float | None = None) -> None:
        self.demandes[cle] = time.time() if maintenant is None else maintenant

    def depuis(self, cle: str, maintenant: float | None = None) -> float | None:
        debut = self.demandes.get(cle)
        maintenant = time.time() if maintenant is None else maintenant
        if debut is None or maintenant - debut > DUREE_ATTENTE_S:
            self.demandes.pop(cle, None)
            return None
        return debut

    def terminer(self, cle: str) -> None:
        self.demandes.pop(cle, None)
