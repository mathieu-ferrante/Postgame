"""Débrief d'une partie (lot L5) : constats priorisés + rédaction optionnelle par modèle."""

from __future__ import annotations

import logging
from typing import Any

from postgame.config import Config
from postgame.db import Base
from postgame.debrief.constats import construire_constats, selectionner
from postgame.debrief.redaction import (
    CONSIGNES,
    ErreurRedaction,
    GeminiRedacteur,
    LocalRedacteur,
    Redacteur,
    chiffres_inventes,
    donnees_en_texte,
    donnees_modele,
    texte_structure,
)

journal = logging.getLogger(__name__)


def redacteur_configure(cfg: Config) -> Redacteur | None:
    fournisseur = cfg.debrief.fournisseur
    if fournisseur == "gemini":
        return GeminiRedacteur(cfg.secret("gemini", "cle", "GEMINI_API_KEY"), cfg.debrief.modele)
    if fournisseur == "local":
        return LocalRedacteur(cfg.debrief.url_local, cfg.debrief.modele)
    return None


def generer_debrief(
    base: Base, cfg: Config, partie_id: int, redacteur: Redacteur | None | str = "config"
) -> dict[str, Any]:
    """Construit, rédige et enregistre le débrief d'une partie. `redacteur` : un rédacteur,
    None pour le débrief structuré seul, ou « config » pour celui de la configuration."""
    partie = base.partie(partie_id)
    if partie is None:
        raise ValueError(f"partie {partie_id} inconnue")
    constats, masquees = construire_constats(
        base, partie, cfg.debrief.historique, cfg.debrief.mesures_experimentales
    )
    selection = selectionner(constats)
    contenu = {
        "partie": {
            "id": partie.id,
            "jeu": partie.jeu,
            "mode": partie.mode,
            "carte": partie.carte,
            "date": partie.date_partie,
            "resultat": partie.resultat,
        },
        **{cle: [c.en_dict() for c in lot] for cle, lot in selection.items()},
        "mesures_masquees": masquees,
    }
    structure = texte_structure(selection, masquees)
    resultat: dict[str, Any] = {
        "contenu": contenu,
        "texte": structure,
        "fournisseur": "aucun",
        "modele": "",
        "statut": "structure",
        "message": "",
    }

    if redacteur == "config":
        try:
            redacteur = redacteur_configure(cfg)
        except ErreurRedaction as exc:
            redacteur = None
            resultat["message"] = str(exc)
    if redacteur is not None and constats:
        donnees = donnees_modele(selection, partie.jeu, partie.mode, partie.carte)
        try:
            reponse = redacteur.rediger(CONSIGNES, donnees_en_texte(donnees))
            cout = (
                reponse.jetons_entree * cfg.debrief.prix_entree
                + reponse.jetons_sortie * cfg.debrief.prix_sortie
            ) / 1_000_000
            resultat.update(
                fournisseur=redacteur.nom,
                modele=redacteur.modele,
                jetons_entree=reponse.jetons_entree,
                jetons_sortie=reponse.jetons_sortie,
                cout=round(cout, 6),
            )
            inventes = chiffres_inventes(reponse.texte, donnees)
            if inventes:
                resultat.update(
                    statut="rejete", message=f"chiffres absents des mesures : {', '.join(inventes)}"
                )
                contenu["texte_rejete"] = reponse.texte
            else:
                resultat.update(statut="redige", texte=reponse.texte)
        except ErreurRedaction as exc:
            journal.warning("rédaction impossible : %s", exc)
            resultat.update(statut="structure", message=str(exc))
    base.enregistrer_debrief(partie_id, resultat)
    return base.dernier_debrief(partie_id)
