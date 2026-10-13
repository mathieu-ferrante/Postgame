"""API HTTP locale (COM-07), pour l'interface web et pour Jarvis.

Documentation interactive générée automatiquement : http://<hôte>:8765/docs
Description lisible : docs/API.md.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from postgame import __version__
from postgame.config import Config
from postgame.db import Base
from postgame.debrief import generer_debrief
from postgame.debrief.constats import charger_definitions
from postgame.games import MODULES
from postgame.games.cs2 import radar as radar_cs2
from postgame.games.cs2 import replay as replay_cs2
from postgame.games.cs2.donnees import extraire_match
from postgame.importation import importer
from postgame.mesures import DEFINITIONS
from postgame.surveillance import Surveillant

PERIODES = {"7j": timedelta(days=7), "30j": timedelta(days=30), "tout": None}


class CorpsFiabilite(BaseModel):
    nom: str
    fiable: bool = True
    note: str = ""


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
    app.state.extraire_match = extraire_match  # remplaçable dans les tests

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
        return {
            **p.en_dict(),
            "mesures": base.mesures_partie(partie_id),
            "preuves": base.preuves_partie(partie_id),
        }

    @app.get("/api/parties/{partie_id}/mesures", tags=["mesures"])
    def mesures_partie(partie_id: int) -> list[dict[str, Any]]:
        if base.partie(partie_id) is None:
            raise HTTPException(404, "partie inconnue")
        return base.mesures_partie(partie_id)

    @app.get("/api/parties/{partie_id}/preuves", tags=["mesures"])
    def preuves_partie(partie_id: int, mesure: str | None = None) -> list[dict[str, Any]]:
        """Moments du replay qui illustrent les mesures (COM-04)."""
        if base.partie(partie_id) is None:
            raise HTTPException(404, "partie inconnue")
        return base.preuves_partie(partie_id, mesure)

    @app.get("/api/mesures/definitions", tags=["mesures"])
    def definitions() -> list[dict[str, Any]]:
        """Toutes les mesures connues : nom, version, unité, description, sens, fiabilité
        (validée à la main ou non)."""
        charger_definitions()
        fiab = base.fiabilites()
        return [
            {**asdict(d), "fiable": fiab.get((d.nom, d.version), d.fiable)}
            for d in sorted(DEFINITIONS.values(), key=lambda d: d.nom)
        ]

    @app.post("/api/mesures/fiabilite", tags=["mesures"])
    def fiabilite(corps: CorpsFiabilite) -> dict[str, Any]:
        """Marque une mesure fiable (ou non) après vérification à la main (NF-06).
        Corps : {"nom": "...", "fiable": true, "note": "5 cas vérifiés"}."""
        charger_definitions()
        d = DEFINITIONS.get(corps.nom)
        if d is None:
            raise HTTPException(404, "mesure inconnue")
        base.noter_fiabilite(d.nom, d.version, corps.fiable, corps.note)
        return {"nom": d.nom, "version": d.version, "fiable": corps.fiable}

    @app.get("/api/parties/{partie_id}/debrief", tags=["debrief"])
    def debrief(partie_id: int, regenerer: bool = False) -> dict[str, Any]:
        """Débrief de la partie : 3 priorités, points forts, détail, preuves (COM-04/05/06).
        Généré à la demande s'il n'existe pas, ou si `regenerer=true`."""
        if base.partie(partie_id) is None:
            raise HTTPException(404, "partie inconnue")
        existant = None if regenerer else base.dernier_debrief(partie_id)
        return existant or generer_debrief(base, cfg, partie_id)

    @app.get("/api/debriefs/couts", tags=["debrief"])
    def couts() -> dict[str, Any]:
        """Coût cumulé des débriefs rédigés (NF-04), en dollars et en jetons."""
        return base.couts_debriefs()

    @app.get("/api/cs2/chaleur", tags=["cs2"])
    def chaleur(
        carte: str,
        type: str = Query("mort", pattern="^(mort|kill)$"),
        camp: str | None = Query(None, pattern="^(T|CT)$"),
        periode: str = Query("tout", pattern="^(7j|30j|tout)$"),
    ) -> dict[str, Any]:
        """Positions des morts ou des kills de Mathieu sur une carte (CS-POS-01)."""
        duree = PERIODES[periode]
        depuis = (datetime.now(UTC) - duree).isoformat() if duree else None
        points = [
            {
                "x": p["donnees"]["x"],
                "y": p["donnees"]["y"],
                "z": p["donnees"].get("z"),
                "camp": p["donnees"].get("camp"),
                "arme": p["donnees"].get("arme"),
                "partie_id": p["partie_id"],
                "tick": p["tick"],
                "round": p["round"],
            }
            for p in base.preuves_toutes_parties(f"cs2.position.{type}", "cs2", depuis)
            if p["carte"] == carte and (camp is None or p["donnees"].get("camp") == camp)
        ]
        return {"carte": carte, "type": type, "camp": camp, "points": points}

    @app.get("/api/cs2/references", tags=["cs2"])
    def references_cs2(carte: str | None = None) -> dict[str, Any]:
        """Catalogue appris sur démos pros (CS-REF-01) : résumé par carte, ou lancers et
        positions de référence d'une carte."""
        from postgame.games.cs2 import references

        if carte is None:
            return {"cartes": references.resume_catalogue(base)}
        cat = references.charger_catalogue(base, carte)
        return {
            "carte": carte,
            "lancers": json.loads(cat.lancers.to_json(orient="records")),
            "positions": json.loads(cat.positions.to_json(orient="records")),
        }

    @app.get("/api/cs2/replay/{partie_id}", tags=["cs2"])
    def replay_meta(partie_id: int) -> dict[str, Any]:
        """Replay 2D (CS-RPL-01) : carte, joueurs, rounds, silhouette de la carte, radar."""
        donnees = _replay(partie_id)
        return {
            **donnees["meta"],
            "radar": radar_cs2.radar(cfg.dossier_donnees, donnees["meta"]["carte"]),
        }

    @app.get("/api/cs2/replay/{partie_id}/round/{numero}", tags=["cs2"])
    def replay_round(partie_id: int, numero: int) -> dict[str, Any]:
        """Positions (16 images/s) et évènements d'un round."""
        donnees = _replay(partie_id)
        r = donnees["rounds"].get(str(numero))
        if r is None:
            raise HTTPException(404, "round inconnu")
        return r

    @app.get("/api/cs2/radar/{carte}.png", tags=["cs2"])
    def image_radar(carte: str) -> FileResponse:
        image = radar_cs2.chemin_image(cfg.dossier_donnees, carte)
        if image is None:
            raise HTTPException(404, "radar absent : voir A_VALIDER.md")
        return FileResponse(image, media_type="image/png")

    def _replay(partie_id: int) -> dict[str, Any]:
        p = base.partie(partie_id)
        if p is None or p.jeu != "cs2":
            raise HTTPException(404, "partie CS2 inconnue")
        cache = replay_cs2.chemin_cache(cfg.dossier_donnees, partie_id)
        donnees = replay_cs2.lire_cache(cache)
        if donnees is None:
            if not Path(p.fichier).exists():
                raise HTTPException(410, "démo archivée introuvable")
            try:
                match = app.state.extraire_match(Path(p.fichier), cfg.steamid)
            except Exception as exc:
                raise HTTPException(422, f"démo illisible : {exc}") from exc
            donnees = replay_cs2.construire_replay(match)
            replay_cs2.ecrire_cache(cache, donnees)
        return donnees

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

    # Interface web (web/dist) : fichiers statiques et routes de l'application (SPA).
    dossier_web = cfg.dossier_web

    @app.get("/{chemin:path}", include_in_schema=False)
    def interface(chemin: str) -> FileResponse:
        if chemin.startswith("api/") or not (dossier_web / "index.html").exists():
            raise HTTPException(404, "introuvable")
        fichier = (dossier_web / chemin).resolve()
        if chemin and fichier.is_file() and fichier.is_relative_to(dossier_web.resolve()):
            return FileResponse(fichier)
        if chemin.startswith("assets/"):
            # Fichier d'une ancienne version de l'appli : un 404 franc, pas la page HTML.
            raise HTTPException(404, "fichier introuvable")
        return FileResponse(dossier_web / "index.html", headers={"Cache-Control": "no-cache"})

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
