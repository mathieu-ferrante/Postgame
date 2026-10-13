"""Radars officiels des cartes CS2 : image et paramètres de projection.

Le jeu décrit chaque radar dans resource/overviews/<carte>.txt (KeyValues) :
pos_x, pos_y = coin haut-gauche de l'image en coordonnées du jeu, scale = unités par pixel
d'une image de 1024 px. Pixel = ((x − pos_x) / scale, (pos_y − y) / scale).

Les images sont des fichiers du jeu : Postgame ne les distribue pas. Mathieu les exporte de
son installation (voir A_VALIDER.md) dans data/radars/<carte>.png, avec le .txt d'origine
s'il le souhaite. En leur absence, l'interface dessine la silhouette de la carte à partir
des positions parcourues.

Les valeurs par défaut ci-dessous sont celles connues des outils d'analyse CS2 ; elles sont
À VÉRIFIER contre les fichiers du jeu et remplacées par data/radars/<carte>.txt s'il existe.
"""

from __future__ import annotations

import re
from pathlib import Path

PARAMETRES_DEFAUT: dict[str, dict[str, float]] = {
    "de_mirage": {"pos_x": -3230, "pos_y": 1713, "scale": 5.0},
    "de_dust2": {"pos_x": -2476, "pos_y": 3239, "scale": 4.4},
    "de_inferno": {"pos_x": -2087, "pos_y": 3870, "scale": 4.9},
    "de_nuke": {"pos_x": -3453, "pos_y": 2887, "scale": 7.0},
    "de_overpass": {"pos_x": -4831, "pos_y": 1781, "scale": 5.2},
    "de_ancient": {"pos_x": -2953, "pos_y": 2164, "scale": 5.0},
    "de_anubis": {"pos_x": -2796, "pos_y": 3328, "scale": 5.22},
    "de_vertigo": {"pos_x": -3168, "pos_y": 1762, "scale": 4.0},
    "de_train": {"pos_x": -2308, "pos_y": 2078, "scale": 4.082},
}

CLE_VALEUR = re.compile(r'"(pos_x|pos_y|scale)"\s+"(-?[\d.]+)"', re.IGNORECASE)


def lire_overview(texte: str) -> dict[str, float]:
    return {cle.lower(): float(valeur) for cle, valeur in CLE_VALEUR.findall(texte)}


def radar(dossier_donnees: Path, carte: str) -> dict[str, object]:
    dossier = dossier_donnees / "radars"
    parametres = dict(PARAMETRES_DEFAUT.get(carte, {}))
    source = "defaut" if parametres else None
    fichier_txt = dossier / f"{carte}.txt"
    if fichier_txt.exists():
        lus = lire_overview(fichier_txt.read_text(encoding="utf-8", errors="replace"))
        if {"pos_x", "pos_y", "scale"} <= lus.keys():
            parametres, source = lus, "jeu"
    image = dossier / f"{carte}.png"
    return {
        "carte": carte,
        "parametres": parametres or None,
        "source_parametres": source,
        "image": f"/api/cs2/radar/{carte}.png" if image.exists() else None,
        "taille_image": 1024,
    }


def chemin_image(dossier_donnees: Path, carte: str) -> Path | None:
    if not re.fullmatch(r"[a-z0-9_]+", carte):
        return None
    image = dossier_donnees / "radars" / f"{carte}.png"
    return image if image.exists() else None
