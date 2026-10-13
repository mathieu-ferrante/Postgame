"""Technique d'un lancer de grenade, reconnue dans la démo (STUFF-01).

Au moment du lancer (évènement grenade_thrown = relâchement du bouton), on regarde l'état
du lanceur sur les quelques ticks précédents :
- clic : gauche seul (lancer fort), droit seul (lancer court, « underhand »), les deux
  (lancer moyen) — touches FIRE et RIGHTCLICK ;
- saut : touche JUMP pressée juste avant le lancer, ou joueur en l'air ;
- déplacement : touche avant (W) avec vitesse, marche (Maj), ou immobile ;
- accroupi : touche DUCK ou joueur accroupi.

Les touches viennent des commandes du joueur enregistrées dans la démo (props « boutons »
de demoparser2). Quand une démo ne les contient pas, on retombe sur la vitesse et l'état
« en l'air » / « accroupi », et le clic reste inconnu.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd

BOUTONS = ["FIRE", "RIGHTCLICK", "JUMP", "FORWARD", "BACK", "LEFT", "RIGHT", "WALK", "DUCK"]
TICKS_AVANT = 3  # état examiné sur les 3 ticks qui précèdent le lancer
VITESSE_COURSE = 150.0
VITESSE_MARCHE = 40.0


@dataclass
class Technique:
    clic: str  # gauche, droit, gauche+droit, inconnu
    saut: bool
    deplacement: str  # immobile, avance, marche, deplacement
    accroupi: bool

    @property
    def libelle(self) -> str:
        """Libellé court et stable, ex. « W + saut + clic gauche », « jumpthrow (clic gauche) »."""
        morceaux = []
        if self.deplacement == "avance":
            morceaux.append("W")
        elif self.deplacement == "marche":
            morceaux.append("en marchant")
        elif self.deplacement == "deplacement":
            morceaux.append("en se déplaçant")
        if self.accroupi:
            morceaux.append("accroupi")
        clic = {
            "gauche": "clic gauche",
            "droit": "clic droit",
            "gauche+droit": "clic gauche + droit",
        }.get(self.clic, "clic ?")
        if self.saut and not morceaux:
            return f"jumpthrow ({clic})"
        if self.saut:
            morceaux.append("saut")
        morceaux.append(clic)
        return " + ".join(morceaux) if len(morceaux) > 1 else f"immobile, {clic}"


def _vrai(serie: pd.Series | None) -> bool:
    return serie is not None and bool(pd.Series(serie).fillna(False).astype(bool).any())


def reconnaitre(avant: pd.DataFrame) -> Technique:
    """`avant` : les ticks qui précèdent le lancer (colonnes de BOUTONS si disponibles,
    vx, vy, en_l_air, accroupi). La dernière ligne est la plus proche du lancer."""
    if not len(avant):
        return Technique("inconnu", False, "immobile", False)
    col = avant.get
    gauche, droit = _vrai(col("FIRE")), _vrai(col("RIGHTCLICK"))
    if "FIRE" in avant or "RIGHTCLICK" in avant:
        clic = (
            "gauche+droit"
            if gauche and droit
            else "droit"
            if droit
            else "gauche"
            if gauche
            else "inconnu"
        )
    else:
        clic = "inconnu"
    dernier = avant.iloc[-1]
    vitesse = float((dernier.get("vx", 0.0) ** 2 + dernier.get("vy", 0.0) ** 2) ** 0.5)
    saut = _vrai(col("JUMP")) or bool(dernier.get("en_l_air", False))
    if _vrai(col("WALK")) and vitesse > 1:
        deplacement = "marche"
    elif _vrai(col("FORWARD")) and vitesse >= VITESSE_COURSE:
        deplacement = "avance"
    elif vitesse >= VITESSE_COURSE:
        deplacement = "deplacement"
    elif vitesse >= VITESSE_MARCHE:
        deplacement = "marche"
    else:
        deplacement = "immobile"
    accroupi = _vrai(col("DUCK")) or bool(dernier.get("accroupi", False))
    return Technique(clic, saut, deplacement, accroupi)


def technique_majoritaire(libelles: list[str | None]) -> tuple[str | None, float | None]:
    """Technique la plus fréquente d'un stuff chez les pros, et sa part."""
    connus = [lib for lib in libelles if lib]
    if not connus:
        return None, None
    libelle, nombre = Counter(connus).most_common(1)[0]
    return libelle, nombre / len(connus)


def techniques_des_lancers(
    etats: pd.DataFrame, lancers: pd.DataFrame
) -> dict[tuple[str, int], str]:
    """(steamid, tick du lancer) → libellé, à partir des états des ticks qui précèdent."""
    sortie: dict[tuple[str, int], str] = {}
    if not len(etats) or not len(lancers):
        return sortie
    par_joueur = {sid: g.sort_values("tick") for sid, g in etats.groupby("steamid")}
    for _, jet in lancers.iterrows():
        g = par_joueur.get(str(jet["steamid"]))
        if g is None:
            continue
        t = int(jet["tick"])
        avant = g[(g["tick"] < t) & (g["tick"] >= t - TICKS_AVANT)]
        if not len(avant):
            avant = g[g["tick"] <= t].tail(1)
        sortie[(str(jet["steamid"]), t)] = reconnaitre(avant).libelle
    return sortie


def colonnes_etat(brut: pd.DataFrame) -> dict[str, Any]:
    """Colonnes utiles d'un parse_ticks demoparser2 (boutons inclus s'ils existent)."""
    sortie: dict[str, Any] = {}
    for b in BOUTONS:
        if b in brut:
            sortie[b] = brut[b].fillna(False).astype(bool)
    return sortie
