"""Radars officiels des cartes CS2 : image et paramètres de projection.

Le jeu décrit chaque radar dans resource/overviews/<carte>.txt (KeyValues) :
pos_x, pos_y = coin haut-gauche de l'image en coordonnées du jeu, scale = unités par pixel
d'une image de 1024 px. Pixel = ((x − pos_x) / scale, (pos_y − y) / scale).

Les images sont des fichiers du jeu : Postgame ne les distribue pas. Il les exporte de
l'installation de Mathieu avec Source2Viewer-CLI (outil libre, configuré dans
postgame.toml) vers data/radars/<carte>.png, avec le .txt d'origine. On peut aussi les
exporter à la main (voir A_VALIDER.md). En leur absence, l'interface dessine la
silhouette de la carte à partir des positions parcourues.

Les valeurs par défaut ci-dessous sont celles des fichiers du jeu (resource/overviews,
vérifiées le 2026-10-13 sur le suivi public SteamDatabase/GameTracking-CS2) ; le .txt
exporté du PC de jeu les remplace s'il existe. Pas de carte dessinée par Postgame : sans
l'image officielle, l'interface le dit et n'invente rien.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

journal = logging.getLogger(__name__)

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
    "de_cache": {"pos_x": -2000, "pos_y": 3250, "scale": 5.5},
}

# Cartes à deux étages : sous cette altitude, le jeu affiche le radar « lower ».
ALTITUDE_BAS: dict[str, float] = {"de_nuke": -495, "de_vertigo": 11700}

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
    bas = dossier / f"{carte}_lower.png"
    return {
        "image_bas": f"/api/cs2/radar/{carte}_lower.png" if bas.exists() else None,
        "altitude_bas": ALTITUDE_BAS.get(carte),
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


# --- Export automatique depuis les fichiers du jeu -----------------------------------------

CHEMINS_VPK = "panorama/images/overheadmaps/,resource/overviews/"


def commande_export(outil: Path, vpk: Path, sortie: Path) -> list[str]:
    """Source2Viewer-CLI : décompile radars (vtex_c → png) et descriptions (.txt)."""
    return [
        str(outil),
        "-i",
        str(vpk),
        "-o",
        str(sortie),
        "-d",
        "--vpk_extensions",
        "vtex_c,txt",
        "--vpk_filepath",
        CHEMINS_VPK,
    ]


def _premier(fichiers: list[Path], nom: str) -> Path | None:
    for f in fichiers:
        if f.name.lower() == nom:
            return f
    return None


def ranger(sortie: Path, dossier_donnees: Path, cartes: list[str]) -> dict[str, str]:
    """Copie, pour chaque carte, le radar principal et sa description dans data/radars.
    Les radars d'étage (« _lower ») sont gardés à part sous <carte>_lower.png."""
    dossier = dossier_donnees / "radars"
    dossier.mkdir(parents=True, exist_ok=True)
    images = [f for f in sortie.rglob("*.png")]
    textes = [f for f in sortie.rglob("*.txt") if "overviews" in f.as_posix().lower()]
    bilan = {}
    for carte in cartes:
        image = _premier(images, f"{carte}_radar_psd.png") or _premier(images, f"{carte}_radar.png")
        if image is None:
            bilan[carte] = "radar absent des fichiers du jeu"
            continue
        shutil.copyfile(image, dossier / f"{carte}.png")
        bas = _premier(images, f"{carte}_lower_radar_psd.png")
        if bas is not None:
            shutil.copyfile(bas, dossier / f"{carte}_lower.png")
        texte = _premier(textes, f"{carte}.txt")
        if texte is not None:
            shutil.copyfile(texte, dossier / f"{carte}.txt")
        bilan[carte] = "exporté" + ("" if texte else " (sans description : calage par défaut)")
    return bilan


def manquants(dossier_donnees: Path, cartes: list[str]) -> list[str]:
    return [c for c in cartes if not (dossier_donnees / "radars" / f"{c}.png").exists()]


def exporter(outil: Path, csgo: Path, dossier_donnees: Path, cartes: list[str]) -> dict[str, str]:
    """Exporte les radars des cartes demandées depuis pak01_dir.vpk du PC de jeu."""
    vpk = csgo / "pak01_dir.vpk"
    if not outil.is_file():
        raise FileNotFoundError(f"Source2Viewer-CLI introuvable : {outil}")
    if not vpk.is_file():
        raise FileNotFoundError(f"fichiers du jeu introuvables : {vpk}")
    with tempfile.TemporaryDirectory(prefix="postgame-radars-") as tmp:
        resultat = subprocess.run(
            commande_export(outil, vpk, Path(tmp)),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if resultat.returncode != 0:
            journal.warning("Source2Viewer-CLI : %s", resultat.stderr[-500:])
        return ranger(Path(tmp), dossier_donnees, cartes)
