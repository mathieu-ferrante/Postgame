"""Module Geometry Dash : séances journalisées par le mod Geode « Postgame — journal »."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Any

from postgame.config import Config
from postgame.games.base import Fiche
from postgame.games.gd.analyse import (
    analyser_session,
    inputs_attendus,
    longueur_niveau,
    pourcent,
)
from postgame.games.gd.session import Session, lire_session
from postgame.mesures import ResultatAnalyse


def construire_fiche(session: Session) -> Fiche:
    modes = {e.mode for e in session.essais}
    mode = "mixte" if len(modes) > 1 else (modes.pop() if modes else "normal")
    if session.plateforme:
        mode = f"plateforme {mode}"
    normaux = [e for e in session.essais if e.mode == "normal" and e.pct_fin is not None]
    meilleur = max((e.pct_fin for e in normaux), default=None)
    complete = any(e.complete and e.mode == "normal" for e in session.essais)
    return Fiche(
        date_partie=session.debut.astimezone(UTC).isoformat(timespec="seconds"),
        mode=mode,
        carte=session.niveau,
        resultat="victoire" if complete else "sans_objet",
        score_joueur=int(meilleur) if meilleur is not None else None,
        score_adverse=None,
        duree_s=round(session.duree_ms / 1000, 1),
        details={
            "niveau_id": session.niveau_id,
            "createur": session.createur,
            "essais": len(session.essais),
            "essais_practice": sum(e.mode == "practice" for e in session.essais),
            "version_mod": session.version_mod,
            **({"avertissements": session.avertissements} if session.avertissements else {}),
        },
    )


def donnees_replay(session: Session) -> dict[str, Any]:
    """Superposition de tous les essais sur le profil du niveau (GD-07)."""
    longueur = longueur_niveau(session)
    return {
        "niveau": session.niveau,
        "longueur": longueur,
        "essais": [
            {
                "numero": e.numero,
                "mode": e.mode,
                "x_debut": round(e.x_debut, 1),
                "x_fin": round(e.x_fin, 1) if e.x_fin is not None else None,
                "pct_fin": e.pct_fin,
                "mort": e.mort,
                "complete": e.complete,
                "appuis": [round(c.x, 1) for c in e.appuis],
            }
            for e in session.essais
        ],
        "inputs": [
            {
                "x": round(a.x, 1),
                "pct": pourcent(a.x, longueur),
                "ecart_type": round(a.ecart_type, 1),
                "decalage": round(a.decalage, 1),
                "n": len(a.decalages),
            }
            for a in (inputs_attendus(session) if not session.plateforme else [])
        ],
    }


class ModuleGD:
    nom = "gd"
    libelle = "Geometry Dash"
    extensions = (".gdsession",)
    cout = "leger"

    def dossiers_surveilles(self, cfg: Config) -> list[Path]:
        return list(cfg.dossiers_gd)

    def lire_fiche(self, chemin: Path, cfg: Config) -> Fiche:
        return construire_fiche(lire_session(chemin))

    def analyser(self, chemin: Path, cfg: Config) -> ResultatAnalyse:
        return analyser_session(lire_session(chemin))
