"""Fichier d'annotations officielles de CS2 pour les stuffs d'une carte (STUFF-01).

CS2 sait afficher, en partie d'entraînement, des « annotations » de grenades : un marqueur
au sol là où se placer, un point à viser avec un texte (la technique), et la zone d'arrivée.
Format : KeyValues 3 (MapAnnotationNode, Type « grenade », sous-types main / aim_target /
destination), relevé sur des fichiers publiés par la communauté (2024) ; à confirmer avec
la version actuelle du jeu (A_VALIDER.md).

Le fichier est écrit dans game/csgo/annotations/local/ ; en jeu : `annotation_load
postgame_<carte>` (ou annotation_reload). Fonction officielle, hors ligne : rien ne touche
au jeu en partie classée.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from postgame.games.cs2.geometrie import HAUTEUR_YEUX, vecteur

ENTETE = (
    "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} "
    "format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->"
)
DISTANCE_VISEE = 100.0  # u : le point à viser est placé à cette distance de l'œil
COULEURS = {
    "smoke": "[ 200, 200, 210 ]",
    "flash": "[ 255, 255, 255 ]",
    "molotov": "[ 255, 120, 40 ]",
}
TYPES_JEU = {"smoke": "smoke", "flash": "flash", "molotov": "molotov"}


def _id(cle: str, role: str) -> str:
    """Identifiant stable : régénérer le fichier ne duplique rien."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"postgame/{cle}/{role}"))


def _vec(valeurs: tuple[float, float, float]) -> str:
    return "[ " + ", ".join(f"{v:.6f}" for v in valeurs) + " ]"


def _texte(texte: str) -> str:
    return texte.replace("\\", "\\\\").replace('"', "'")


def _bloc_texte(nom: str, texte: str, taille: int, apparition: float, disparition: float) -> str:
    return (
        f'\t\t{nom} = \n\t\t{{\n\t\t\tText = "{_texte(texte)}"\n\t\t\tFontSize = {taille}\n'
        f"\t\t\tFadeInDist = {apparition:.1f}\n\t\t\tFadeOutDist = {disparition:.1f}\n"
        f"\t\t\tShowBackground = true\n\t\t}}\n"
    )


def est_jumpthrow(stuff: dict[str, Any]) -> bool:
    technique = str(stuff.get("technique") or "")
    return "saut" in technique or "jumpthrow" in technique or (stuff.get("part_saut") or 0) >= 0.5


def noeuds(stuff: dict[str, Any], index: int) -> list[str]:
    """Trois nœuds par stuff : main (où se placer), aim_target (où viser), destination."""
    cle = str(stuff["cle"])
    lx, ly, lz = float(stuff["lx"]), float(stuff["ly"]), float(stuff["lz"])
    pitch, yaw = float(stuff["lpitch"]), float(stuff["lyaw"])
    dx, dy, dz = vecteur(yaw, pitch)
    oeil = (lx, ly, lz + HAUTEUR_YEUX)
    visee = (
        oeil[0] + DISTANCE_VISEE * dx,
        oeil[1] + DISTANCE_VISEE * dy,
        oeil[2] + DISTANCE_VISEE * dz,
    )
    titre = stuff.get("nom") or "Stuff"
    technique = stuff.get("technique") or ("jumpthrow" if est_jumpthrow(stuff) else "")
    part = stuff.get("part_technique")
    detail = f"{technique}" + (f" ({round(100 * part)} % des pros)" if part else "")
    principal = _id(cle, "main")
    couleur = COULEURS.get(stuff["type"], "[ 255, 239, 111 ]")
    sortie = [
        (
            f'\tMapAnnotationNode{index} = \n\t{{\n\t\tEnabled = true\n\t\tType = "grenade"\n'
            f'\t\tId = "{principal}"\n\t\tSubType = "main"\n'
            f"\t\tPosition = {_vec((lx, ly, lz))}\n\t\tAngles = {_vec((0.0, yaw, 0.0))}\n"
            f"\t\tVisiblePfx = true\n\t\tColor = {couleur}\n"
            f"\t\tTextPositionOffset = [ 0.0, 0.0, 60.0 ]\n\t\tTextFacePlayer = true\n"
            f'\t\tTextHorizontalAlign = "center"\n\t\tRevealOnSuccess = false\n'
            + _bloc_texte("Title", titre, 125, 600.0, 40.0)
            + _bloc_texte("Desc", detail, 75, 300.0, 40.0)
            + f"\t\tStreakLimitGuidesOn = 2\n\t\tStreakLimitGuidesOff = 2\n"
            f"\t\tJumpThrow = {'true' if est_jumpthrow(stuff) else 'false'}\n"
            f'\t\tGrenadeType = "{TYPES_JEU.get(stuff["type"], "smoke")}"\n\t}}\n'
        ),
        (
            f'\tMapAnnotationNode{index + 1} = \n\t{{\n\t\tEnabled = true\n\t\tType = "grenade"\n'
            f'\t\tId = "{_id(cle, "aim")}"\n\t\tSubType = "aim_target"\n'
            f"\t\tPosition = {_vec(visee)}\n\t\tAngles = {_vec((pitch, yaw, 0.0))}\n"
            f"\t\tVisiblePfx = true\n\t\tTextPositionOffset = [ 0.0, 0.0, 30.0 ]\n"
            f'\t\tTextFacePlayer = false\n\t\tTextHorizontalAlign = "center"\n'
            f"\t\tRevealOnSuccess = false\n"
            + _bloc_texte("Title", titre, 125, 50.0, -1.0)
            + _bloc_texte("Desc", detail, 75, 50.0, -1.0)
            + f'\t\tMasterNodeId = "{principal}"\n\t}}\n'
        ),
        (
            f'\tMapAnnotationNode{index + 2} = \n\t{{\n\t\tEnabled = true\n\t\tType = "grenade"\n'
            f'\t\tId = "{_id(cle, "destination")}"\n\t\tSubType = "destination"\n'
            f"\t\tPosition = {_vec((float(stuff['x']), float(stuff['y']), float(stuff['z'])))}\n"
            f"\t\tAngles = {_vec((pitch, yaw, 0.0))}\n\t\tVisiblePfx = true\n"
            f"\t\tTextPositionOffset = [ 0.0, 0.0, 0.0 ]\n\t\tTextFacePlayer = false\n"
            f'\t\tTextHorizontalAlign = "center"\n\t\tRevealOnSuccess = false\n'
            + _bloc_texte("Title", "", 75, 50.0, -1.0)
            + _bloc_texte("Desc", "", 75, 50.0, -1.0)
            + f'\t\tMasterNodeId = "{principal}"\n\t\tDistanceThreshold = 80.0\n\t}}\n'
        ),
    ]
    return sortie


def generer(carte: str, stuffs: list[dict[str, Any]]) -> str:
    utilisables = [
        s for s in stuffs if all(s.get(k) is not None for k in ("lx", "ly", "lz", "lpitch", "lyaw"))
    ]
    corps = []
    for i, s in enumerate(utilisables):
        corps += noeuds(s, 3 * i)
    return (
        f'{ENTETE}\n{{\n\tMapName = "{carte}"\n\tScreenText = \n\t{{\n\t}}\n'
        + "".join(corps)
        + "}\n"
    )


def dossier_annotations(dossiers_cs2: list[Path], repli: Path) -> Path:
    """game/csgo/annotations/local s'il existe (PC de jeu), sinon un dossier de repli."""
    for d in dossiers_cs2:
        candidat = (d.parent if d.name == "replays" else d) / "annotations" / "local"
        if candidat.parent.parent.is_dir():
            return candidat
    return repli


def ecrire(carte: str, stuffs: list[dict[str, Any]], dossier: Path) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"postgame_{carte}.txt"
    chemin.write_text(generer(carte, stuffs), encoding="utf-8")
    return chemin
