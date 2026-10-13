"""API HTTP locale (COM-07), pour l'interface web et pour Jarvis.

Documentation interactive générée automatiquement : http://<hôte>:8765/docs
Description lisible : docs/API.md.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
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
from postgame.games.riot.client import ErreurRiot
from postgame.games.riot.collecte import CollecteurRiot
from postgame.importation import importer
from postgame.live.gsi_cs2 import RecepteurGSI, jeton_gsi
from postgame.live.lol import ScruteurLoL
from postgame.mesures import DEFINITIONS
from postgame.performance import Garde, abaisser_priorite
from postgame.surveillance import Surveillant

PERIODES = {"7j": timedelta(days=7), "30j": timedelta(days=30), "tout": None}


class CorpsNote(BaseModel):
    carte: str
    texte: str
    stuff: str | None = None
    jeu: str = "cs2"


class CorpsTexte(BaseModel):
    texte: str


class CorpsRevision(BaseModel):
    reussi: bool


class CorpsFiabilite(BaseModel):
    nom: str
    fiable: bool = True
    note: str = ""


class DemandeRevoir(BaseModel):
    partie_id: int | None = None
    empreinte: str | None = None
    tick: int
    joueur: str | None = None


def creer_app(cfg: Config, base: Base | None = None, surveiller: bool = True) -> FastAPI:
    base = base or Base(cfg.chemin_base)
    garde = Garde(
        dernier_gsi=lambda: (
            getattr(app.state, "recepteur_gsi", None) and app.state.recepteur_gsi.dernier_recu
        )
    )
    surveillant = Surveillant(base, cfg, garde=garde if surveiller else None)

    @asynccontextmanager
    async def cycle_de_vie(_app: FastAPI):
        if surveiller:
            abaisser_priorite()
            surveillant.demarrer()
            if cfg.riot_id and cfg.secret("riot", "cle", "RIOT_API_KEY"):
                app.state.collecteur_riot.demarrer()
            app.state.scruteur_lol.demarrer()
            if cfg.faceit_pseudo or cfg.steam_code_connu:
                threading.Thread(
                    target=app.state.boucle_sources,
                    args=(app.state.arret,),
                    daemon=True,
                    name="sources-cs2",
                ).start()
            if not cfg.hors_ligne:
                from postgame.games.cs2 import cartes

                threading.Thread(
                    target=cartes.actualiser,
                    args=(cfg.dossier_donnees,),
                    daemon=True,
                    name="cartes-cs2",
                ).start()
        yield
        app.state.scruteur_lol.arreter()
        app.state.arret.set()
        surveillant.arreter()
        app.state.collecteur_riot.arreter()

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

    @app.get("/api/comptes", tags=["service"])
    def comptes() -> dict[str, Any]:
        """Comptes liés (Steam, Riot, FACEIT) et évolution des classements (CPT-01)."""
        from postgame.comptes import resume

        return resume(cfg, base)

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
            "jeux_en_cours": sorted(garde.jeux_en_cours()) if surveiller else [],
            "reportes_fin_de_partie": sorted(surveillant.reportes),
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

    @app.get("/api/cs2/cartes", tags=["cs2"])
    def cartes_cs2(actualiser: bool = False) -> dict[str, Any]:
        """Pool actif de CS2 (tenu à jour d'après les notes officielles) et cartes déjà
        jouées par Mathieu."""
        from postgame.games.cs2 import cartes

        etat = (
            cartes.actualiser(cfg.dossier_donnees)
            if actualiser
            else cartes.etat_cartes(cfg.dossier_donnees)
        )
        with base.transaction() as cx:
            jouees = [
                r[0]
                for r in cx.execute(
                    "SELECT carte, COUNT(*) FROM parties WHERE jeu = 'cs2' GROUP BY carte "
                    "ORDER BY COUNT(*) DESC"
                ).fetchall()
            ]
        return {
            **etat,
            "cartes": [
                {"code": c, "nom": cartes.nom_affiche(c), "pool": True} for c in etat["pool"]
            ]
            + [
                {"code": c, "nom": cartes.nom_affiche(c), "pool": False}
                for c in jouees
                if c not in etat["pool"]
            ],
        }

    @app.get("/api/cs2/stuffs", tags=["stuffs"])
    def stuffs_carte(carte: str) -> dict[str, Any]:
        """Stuffs d'une carte (STUFF-01) : catalogue appris sur démos pros, commandes
        d'entraînement, maîtrise en match, révisions, notes ; notes générales de la carte."""
        from postgame.games.cs2 import stuffs

        return {
            "carte": carte,
            "stuffs": stuffs.stuffs_carte(base, carte),
            "notes_carte": [n for n in stuffs.notes(base, carte) if not n["stuff"]],
            "config_entrainement": stuffs.CONFIG_ENTRAINEMENT,
            "radar": radar_cs2.radar(cfg.dossier_donnees, carte),
        }

    @app.get("/api/cs2/stuffs/annotations", tags=["stuffs"])
    def stuffs_annotations(carte: str) -> Response:
        """Fichier d'annotations CS2 de la carte (à charger en entraînement)."""
        from postgame.games.cs2 import annotations_jeu as annotations
        from postgame.games.cs2 import stuffs

        texte = annotations.generer(carte, stuffs.stuffs_carte(base, carte))
        return Response(
            texte,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="postgame_{carte}.txt"'},
        )

    @app.post("/api/cs2/stuffs/annotations", tags=["stuffs"])
    def stuffs_annotations_installer(carte: str) -> dict[str, Any]:
        """Écrit le fichier dans game/csgo/annotations/local du PC de jeu."""
        from postgame.games.cs2 import annotations_jeu as annotations
        from postgame.games.cs2 import stuffs

        dossier = annotations.dossier_annotations(
            cfg.dossiers_cs2, cfg.dossier_donnees / "annotations"
        )
        chemin = annotations.ecrire(carte, stuffs.stuffs_carte(base, carte), dossier)
        return {"fichier": str(chemin), "commande": f"annotation_load postgame_{carte}"}

    @app.post("/api/cs2/stuffs/{cle}/image", tags=["stuffs"])
    async def stuff_image(cle: str, fichier: UploadFile) -> dict[str, Any]:
        """Capture d'écran jointe à un stuff (position, visée…)."""
        from postgame.games.cs2 import stuffs

        try:
            stuffs.enregistrer_image(
                cfg.dossier_donnees, cle, fichier.filename or "", await fichier.read()
            )
        except ValueError as exc:
            raise HTTPException(415, str(exc)) from exc
        return {"image": f"/api/cs2/stuffs/{cle}/image"}

    @app.get("/api/cs2/stuffs/{cle}/image", tags=["stuffs"])
    def stuff_image_lire(cle: str) -> FileResponse:
        from postgame.games.cs2 import stuffs

        image = stuffs.chemin_image(cfg.dossier_donnees, cle)
        if image is None:
            raise HTTPException(404, "pas d'image pour ce stuff")
        return FileResponse(image, media_type=stuffs.FORMATS_IMAGE[image.suffix])

    @app.post("/api/cs2/revoir", tags=["revoir"])
    def revoir(demande: DemandeRevoir) -> dict[str, Any]:
        """Prépare un vrai moment à revoir dans CS2 (une de mes parties ou une démo pro)."""
        from postgame.games.cs2 import revoir as rv

        if demande.partie_id is not None:
            partie = base.partie(demande.partie_id)
            if partie is None or partie.jeu != "cs2":
                raise HTTPException(404, "partie CS2 inconnue")
            demo, nom = Path(partie.fichier), f"partie{partie.id}"
            # Par défaut, la caméra me suit.
            demande.joueur = demande.joueur or partie.details.get("joueur") or None
        elif demande.empreinte:
            demo = rv.chemin_demo_pro(base, demande.empreinte)
            if demo is None or not demande.empreinte.isalnum():
                raise HTTPException(404, "démo pro inconnue")
            nom = f"pro{demande.empreinte[:12]}"
        else:
            raise HTTPException(422, "partie_id ou empreinte attendu")
        try:
            resultat = rv.preparer(
                demo,
                demande.tick,
                demande.joueur,
                rv.dossier_csgo(cfg.dossiers_cs2),
                cfg.dossier_donnees / "revoir",
                nom,
            )
        except FileNotFoundError as exc:
            raise HTTPException(410, f"{exc} (déplacée ou supprimée ?)") from exc
        return resultat.en_dict()

    @app.get("/api/cs2/pros", tags=["revoir"])
    def pros() -> list[dict[str, Any]]:
        """Démos pros lues ; « disponible » si le fichier est toujours là pour la revoir."""
        from postgame.games.cs2 import revoir as rv

        return rv.demos_pros(base)

    @app.get("/api/cs2/pros/proches", tags=["revoir"])
    def pros_proches(
        carte: str, x: float, y: float, camp: str | None = None
    ) -> list[dict[str, Any]]:
        """Vrais rounds pros où un joueur du même camp était au même endroit."""
        from postgame.games.cs2 import revoir as rv

        return rv.moments_proches(base, carte, camp, x, y)

    @app.get("/api/cs2/stuffs/{cle}/pros", tags=["revoir"])
    def stuff_pros(cle: str) -> list[dict[str, Any]]:
        """Vrais lancers pros de ce stuff, à revoir dans CS2."""
        from postgame.games.cs2 import revoir as rv

        try:
            return rv.exemples_stuff(base, cle)
        except KeyError as exc:
            raise HTTPException(404, "stuff inconnu") from exc

    @app.get("/api/cs2/stuffs/a_reviser", tags=["stuffs"])
    def stuffs_a_reviser(carte: str, nombre: int = Query(5, ge=1, le=50)) -> list[dict[str, Any]]:
        from postgame.games.cs2 import stuffs

        return stuffs.a_reviser(base, carte, nombre)

    @app.post("/api/cs2/stuffs/{cle}/revision", tags=["stuffs"])
    def stuff_revision(cle: str, corps: CorpsRevision) -> dict[str, Any]:
        from postgame.games.cs2 import stuffs

        return stuffs.noter_revision(base, cle, corps.reussi)

    @app.post("/api/notes", tags=["stuffs"])
    def note_ajouter(corps: CorpsNote) -> dict[str, Any]:
        """Note de Mathieu sur une carte (ou sur un stuff de cette carte)."""
        from postgame.games.cs2 import stuffs

        return {"id": stuffs.ajouter_note(base, corps.carte, corps.texte, corps.stuff, corps.jeu)}

    @app.put("/api/notes/{note_id}", tags=["stuffs"])
    def note_modifier(note_id: int, corps: CorpsTexte) -> dict[str, Any]:
        from postgame.games.cs2 import stuffs

        if not stuffs.modifier_note(base, note_id, corps.texte):
            raise HTTPException(404, "note inconnue")
        return {"id": note_id}

    @app.delete("/api/notes/{note_id}", tags=["stuffs"])
    def note_supprimer(note_id: int) -> dict[str, Any]:
        from postgame.games.cs2 import stuffs

        if not stuffs.supprimer_note(base, note_id):
            raise HTTPException(404, "note inconnue")
        return {"id": note_id}

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
                match = app.state.extraire_match(Path(p.fichier), cfg.steamid, cfg.noms_joueur)
            except Exception as exc:
                raise HTTPException(422, f"démo illisible : {exc}") from exc
            donnees = replay_cs2.construire_replay(match)
            replay_cs2.ecrire_cache(cache, donnees)
        return donnees

    @app.get("/api/gd/replay/{partie_id}", tags=["gd"])
    def replay_gd(partie_id: int) -> dict[str, Any]:
        """Tous les essais d'une séance superposés sur le niveau, avec les appuis et les
        inputs attendus (GD-07)."""
        from postgame.games.gd import donnees_replay
        from postgame.games.gd.session import lire_session

        p = base.partie(partie_id)
        if p is None or p.jeu != "gd":
            raise HTTPException(404, "séance Geometry Dash inconnue")
        if not Path(p.fichier).exists():
            raise HTTPException(410, "journal archivé introuvable")
        return donnees_replay(lire_session(Path(p.fichier)))

    # --- Riot : LoL et TFT ---------------------------------------------------------------

    collecteur = CollecteurRiot(base, cfg, garde=garde if surveiller else None)
    app.state.collecteur_riot = collecteur

    @app.get("/api/riot/etat", tags=["riot"])
    def etat_riot() -> dict[str, Any]:
        """Compte Riot configuré, dernière synchronisation, erreur éventuelle."""
        return {
            "riot_id": cfg.riot_id or None,
            "plateforme": cfg.riot_plateforme,
            "cle_presente": bool(cfg.secret("riot", "cle", "RIOT_API_KEY")),
            **collecteur.etat,
        }

    @app.post("/api/riot/synchroniser", tags=["riot"])
    def synchroniser_riot() -> dict[str, Any]:
        """Récupère tout de suite les nouvelles parties LoL et TFT."""
        try:
            return collecteur.synchroniser()
        except ErreurRiot as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get("/api/lol/replay/{partie_id}", tags=["lol"])
    def replay_lol(partie_id: int) -> dict[str, Any]:
        """Carte minute par minute d'une partie LoL (LOL-06)."""
        from postgame.games.lol import donnees_replay, lire_fichier

        p = base.partie(partie_id)
        if p is None or p.jeu != "lol" or not Path(p.fichier).exists():
            raise HTTPException(404, "partie LoL inconnue")
        return donnees_replay(lire_fichier(Path(p.fichier)))

    @app.get("/api/tft/stats", tags=["tft"])
    def stats_tft() -> dict[str, Any]:
        """Ce qui fait gagner ou perdre des places à Mathieu, par set et patch, face au haut
        classement du même patch (TFT-02, TFT-03)."""
        from postgame.games.riot.meta import lire_reference_tft
        from postgame.games.tft import lire_fichier as lire_tft
        from postgame.games.tft.stats import comparer, observations, statistiques

        obs = []
        decalage = 0
        while lot := base.lister_parties(jeu="tft", limite=200, decalage=decalage):
            decalage += len(lot)
            for p in lot:
                if Path(p.fichier).exists():
                    d = lire_tft(Path(p.fichier))
                    obs += observations(d["match"], {d["puuid"]})
        return comparer(statistiques(obs), lire_reference_tft(cfg.dossier_donnees / "riot"))

    scruteur_lol = ScruteurLoL(base)
    app.state.scruteur_lol = scruteur_lol

    @app.get("/api/lol/live", tags=["lol"])
    def live_lol() -> dict[str, Any]:
        """Partie LoL en cours (LOL-07), d'après l'API locale du client LoL."""
        return scruteur_lol.resume

    @app.websocket("/api/lol/live/ws")
    async def live_lol_ws(ws: WebSocket) -> None:
        """Même contenu, envoyé dès qu'il change (vérifié 4 fois par seconde)."""
        await ws.accept()
        dernier = None
        try:
            while True:
                if scruteur_lol.resume != dernier:
                    dernier = scruteur_lol.resume
                    await ws.send_json(dernier)
                await asyncio.sleep(0.25)
        except (WebSocketDisconnect, RuntimeError):
            pass

    # --- Récupération automatique des parties CS2 (AUTO-01) ------------------------------

    etat_sources: dict[str, Any] = {"faceit": None, "steam": None, "derniere_synchro": None}

    def synchroniser_sources() -> dict[str, Any]:
        from postgame.db import maintenant
        from postgame.games.cs2.sources import CodesSteam, CollecteurFaceit, ErreurSource

        if cfg.faceit_pseudo:
            try:
                etat_sources["faceit"] = CollecteurFaceit(base, cfg).synchroniser()
            except (ErreurSource, Exception) as exc:  # réseau, clé… : on réessaiera
                etat_sources["faceit"] = {"erreur": str(exc)}
        if cfg.steam_code_connu:
            try:
                codes = CodesSteam(cfg)
                etat_sources["steam"] = {
                    "nouveaux": codes.synchroniser(),
                    "sans_demo": len(codes.sans_demo()),
                }
            except (ErreurSource, Exception) as exc:
                etat_sources["steam"] = {"erreur": str(exc)}
        etat_sources["derniere_synchro"] = maintenant()
        return etat_sources

    def boucle_sources(arret: threading.Event) -> None:
        while not arret.is_set():
            if not garde.doit_attendre("leger"):
                synchroniser_sources()
            arret.wait(cfg.sources_synchro_minutes * 60)

    app.state.boucle_sources = boucle_sources
    app.state.arret = threading.Event()

    @app.get("/api/sources/etat", tags=["import"])
    def sources_etat() -> dict[str, Any]:
        """Récupération automatique : FACEIT, codes de partage Steam (parties sans démo)."""
        return {
            "faceit_pseudo": cfg.faceit_pseudo or None,
            "steam_configure": bool(cfg.steam_code_connu),
            **etat_sources,
        }

    @app.post("/api/sources/synchroniser", tags=["import"])
    def sources_synchroniser() -> dict[str, Any]:
        return synchroniser_sources()

    # --- Second écran CS2 (Game State Integration) ---------------------------------------

    recepteur = RecepteurGSI(cfg.dossier_donnees, jeton_gsi(cfg.dossier_donnees))
    abonnes: set[WebSocket] = set()
    app.state.recepteur_gsi = recepteur

    def message_live() -> dict[str, Any]:
        message = {**recepteur.resume, "rappel": rappel_priorites(base)}
        # Deathmatch sans démo en cours d'écriture : rappeler la touche d'enregistrement.
        enregistre = any(Path(c).name.startswith("postgame_") for c in surveillant.en_attente())
        if (
            message.get("mode") == "deathmatch"
            and message.get("phase_match") == "live"
            and not enregistre
        ):
            message["alerte"] = "Deathmatch non enregistré : appuie sur F8 pour l'analyser ensuite."
        # Au chargement de la carte et pendant les achats : stuffs à réviser et notes.
        carte = message.get("carte")
        if (
            carte
            and message.get("phase_match") in ("warmup", "live")
            and message.get("phase_round") in ("freezetime", "", None)
        ):
            from postgame.games.cs2 import stuffs

            message["stuffs"] = [
                {"nom": s["nom"], "technique": s["technique"]}
                for s in stuffs.a_reviser(base, carte, 3)
            ]
            message["notes_carte"] = [
                n["texte"] for n in stuffs.notes(base, carte) if not n["stuff"]
            ][:3]
        return message

    @app.post("/api/cs2/gsi", tags=["cs2"], include_in_schema=False)
    async def gsi(requete: Request) -> dict[str, str]:
        """Point d'arrivée du flux GSI envoyé par CS2 (config gamestate_integration)."""
        try:
            charge = await requete.json()
        except ValueError as exc:
            raise HTTPException(400, "JSON invalide") from exc
        if not recepteur.recevoir(charge):
            raise HTTPException(401, "jeton GSI invalide")
        message = message_live()
        for ws in list(abonnes):
            try:
                await ws.send_json(message)
            except Exception:
                abonnes.discard(ws)
        return {"statut": "ok"}

    @app.get("/api/cs2/live", tags=["cs2"])
    def live() -> dict[str, Any]:
        """Dernier état de la partie en cours (CS-LIVE-01) et rappel des priorités."""
        return message_live()

    @app.websocket("/api/cs2/live/ws")
    async def live_ws(ws: WebSocket) -> None:
        """Même contenu que /api/cs2/live, poussé à chaque message GSI."""
        await ws.accept()
        abonnes.add(ws)
        try:
            await ws.send_json(message_live())
            while True:
                await ws.receive_text()  # garde la connexion ouverte
        except WebSocketDisconnect:
            pass
        finally:
            abonnes.discard(ws)

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


def rappel_priorites(base: Base) -> list[dict[str, Any]]:
    """Les priorités du dernier débrief CS2 : à garder en tête pendant la partie."""
    derniere = base.lister_parties(jeu="cs2", limite=1)
    if not derniere:
        return []
    debrief = base.dernier_debrief(derniere[0].id)
    if debrief is None:
        return []
    return [
        {
            "id": c["id"],
            "mesure": c["mesure"],
            "libelle": c["libelle"],
            "valeur": c["valeur"],
            "unite": c["unite"],
            "cible": c["cible"],
            "reference": c["reference"],
        }
        for c in debrief["contenu"].get("priorites", [])
    ]


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
