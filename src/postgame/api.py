"""API HTTP locale (COM-07), pour l'interface web et pour Jarvis.

Documentation interactive générée automatiquement : http://<hôte>:8765/docs
Description lisible : docs/API.md.
"""

from __future__ import annotations

import shutil
import tempfile
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from postgame import __version__
from postgame.config import Config
from postgame.db import Base
from postgame.games import MODULES
from postgame.importation import importer
from postgame.surveillance import Surveillant

PERIODES = {"7j": timedelta(days=7), "30j": timedelta(days=30), "tout": None}


def creer_app(cfg: Config, base: Base | None = None, surveiller: bool = True) -> FastAPI:
    base = base or Base(cfg.chemin_base)
    surveillant = Surveillant(base, cfg)

    @asynccontextmanager
    async def cycle_de_vie(_app: FastAPI):
        if surveiller:
            surveillant.demarrer()
        yield
        surveillant.arreter()

    app = FastAPI(
        title="Postgame",
        version=__version__,
        description="API locale de Postgame : parties, fiches, mesures, progression.",
        lifespan=cycle_de_vie,
    )
    # Réseau local uniquement : l'interface (Vite en développement) et le téléphone.
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.state.base = base
    app.state.surveillant = surveillant

    @app.get("/api/sante", tags=["service"])
    def sante() -> dict[str, Any]:
        """État du service."""
        return {
            "statut": "ok",
            "version": __version__,
            "schema": base.version_schema,
            "parties": base.compter_parties(),
        }

    @app.get("/api/jeux", tags=["service"])
    def jeux() -> list[dict[str, Any]]:
        """Jeux pris en charge et dossiers surveillés."""
        return [
            {
                "nom": m.nom,
                "libelle": m.libelle,
                "extensions": list(m.extensions),
                "dossiers": [
                    {"chemin": str(d), "existe": d.is_dir()} for d in m.dossiers_surveilles(cfg)
                ],
                "parties": base.compter_parties(m.nom),
            }
            for m in MODULES.values()
        ]

    @app.get("/api/import/etat", tags=["import"])
    def etat_import() -> dict[str, Any]:
        """Dernière passe de surveillance, fichiers en attente de stabilité, derniers
        fichiers traités."""
        derniere = surveillant.derniere_passe
        return {
            "surveillance_active": surveiller,
            "derniere_passe": datetime.fromtimestamp(derniere, UTC).isoformat()
            if derniere
            else None,
            "en_attente": surveillant.en_attente(),
            "derniers_fichiers": base.derniers_fichiers(),
        }

    @app.post("/api/import", tags=["import"])
    async def import_manuel(fichier: UploadFile) -> dict[str, Any]:
        """Import manuel d'un fichier (glisser-déposer dans l'interface)."""
        nom = Path(fichier.filename or "fichier").name
        with tempfile.TemporaryDirectory() as dossier:
            temporaire = Path(dossier) / nom
            with temporaire.open("wb") as sortie:
                shutil.copyfileobj(fichier.file, sortie)
            resultat = importer(temporaire, base, cfg, nom_origine=nom)
        if resultat.statut == "ignore":
            raise HTTPException(415, resultat.message)
        if resultat.statut == "erreur":
            raise HTTPException(422, resultat.message)
        return {
            "statut": resultat.statut,
            "message": resultat.message,
            "partie_id": resultat.partie_id,
        }

    @app.get("/api/parties", tags=["parties"])
    def parties(
        jeu: str | None = None,
        limite: int = Query(50, ge=1, le=500),
        decalage: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        """Liste des parties, les plus récentes d'abord."""
        lot = base.lister_parties(jeu=jeu, limite=limite, decalage=decalage)
        return {"total": base.compter_parties(jeu), "parties": [_resume(p) for p in lot]}

    @app.get("/api/parties/{partie_id}", tags=["parties"])
    def partie(partie_id: int) -> dict[str, Any]:
        """Fiche complète d'une partie, avec ses mesures."""
        p = base.partie(partie_id)
        if p is None:
            raise HTTPException(404, "partie inconnue")
        return {**p.en_dict(), "mesures": base.mesures_partie(partie_id)}

    @app.get("/api/parties/{partie_id}/mesures", tags=["mesures"])
    def mesures_partie(partie_id: int) -> list[dict[str, Any]]:
        if base.partie(partie_id) is None:
            raise HTTPException(404, "partie inconnue")
        return base.mesures_partie(partie_id)

    @app.get("/api/mesures", tags=["mesures"])
    def noms_mesures() -> list[str]:
        """Noms des mesures disponibles en base."""
        return base.noms_mesures()

    @app.get("/api/progression/{nom}", tags=["mesures"])
    def progression(
        nom: str, periode: str = Query("30j", pattern="^(7j|30j|tout)$")
    ) -> dict[str, Any]:
        """Série d'une mesure partie par partie sur 7 jours, 30 jours ou tout (COM-03)."""
        duree = PERIODES[periode]
        depuis = (datetime.now(UTC) - duree).isoformat() if duree else None
        return {"nom": nom, "periode": periode, "points": base.serie_mesure(nom, depuis)}

    return app


def _resume(p) -> dict[str, Any]:
    return {
        k: getattr(p, k)
        for k in (
            "id",
            "jeu",
            "date_partie",
            "mode",
            "carte",
            "resultat",
            "score_joueur",
            "score_adverse",
            "duree_s",
        )
    }
