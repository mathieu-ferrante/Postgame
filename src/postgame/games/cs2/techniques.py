"""Technique d'un lancer de grenade, reconnue dans la démo (STUFF-01).

Dans les démos réelles (vérifié sur ESL Pro League S24), le joueur relâche le clic 5 à 10
ticks AVANT l'évènement grenade_thrown. On retrouve donc le vrai lâcher : le dernier tick
où le clic est tenu, + 1. C'est là que comptent la position et la visée (un pro tourne la
tête aussitôt après). Sur les ticks qui précèdent, on regarde :
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

import numpy as np
import pandas as pd

BOUTONS = ["FIRE", "RIGHTCLICK", "JUMP", "FORWARD", "BACK", "LEFT", "RIGHT", "WALK", "DUCK"]
TICKS_AVANT = 24  # fenêtre examinée avant grenade_thrown (le lâcher est dedans)
TICKS_JUMPTHROW = 4  # décollage au plus 4 ticks avant le lâcher : jumpthrow
VITESSE_COURSE = 150.0
VITESSE_MARCHE = 40.0


@dataclass
class Technique:
    clic: str  # gauche, droit, gauche+droit, inconnu
    saut: bool
    deplacement: str  # immobile, avance, marche, deplacement
    accroupi: bool
    jumpthrow: bool = True  # saut et lâcher simultanés (sinon : sauter puis lancer en l'air)

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
        if self.saut and not self.jumpthrow:
            morceaux.append("en l'air")
        elif self.saut and not morceaux:
            return f"jumpthrow ({clic})"
        elif self.saut:
            morceaux.append("saut")
        morceaux.append(clic)
        return " + ".join(morceaux) if len(morceaux) > 1 else f"immobile, {clic}"


def _vrai(serie: pd.Series | None) -> bool:
    return serie is not None and bool(pd.Series(serie).fillna(False).astype(bool).any())


def indice_lacher(avant: pd.DataFrame) -> int:
    """Position (0…n−1) du vrai lâcher dans la fenêtre : la ligne qui suit le dernier tick
    où le clic est tenu ; la dernière ligne si les touches sont absentes."""
    tenu = None
    for b in ("FIRE", "RIGHTCLICK"):
        if b in avant:
            s = pd.Series(avant[b]).fillna(False).astype(bool).to_numpy()
            tenu = s if tenu is None else (tenu | s)
    if tenu is None or not tenu.any():
        return len(avant) - 1
    dernier = int(np.flatnonzero(tenu)[-1])
    return min(dernier + 1, len(avant) - 1)


def reconnaitre(avant: pd.DataFrame) -> Technique:
    """`avant` : les ticks qui précèdent grenade_thrown (colonnes de BOUTONS si disponibles,
    vx, vy, en_l_air, accroupi), dans l'ordre. Le lâcher est retrouvé dans la fenêtre."""
    if not len(avant):
        return Technique("inconnu", False, "immobile", False)
    avant = avant.reset_index(drop=True)
    i = indice_lacher(avant)
    jusqu_au_lacher = avant.iloc[: i + 1]
    autour = avant.iloc[max(0, i - 2) : i + 1]
    col = jusqu_au_lacher.get
    # Clic : les boutons tenus juste avant le lâcher.
    juste_avant = avant.iloc[max(0, i - 3) : i]
    gauche = _vrai(juste_avant.get("FIRE")) if len(juste_avant) else _vrai(col("FIRE"))
    droit = _vrai(juste_avant.get("RIGHTCLICK")) if len(juste_avant) else _vrai(col("RIGHTCLICK"))
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
    lacher = avant.iloc[i]
    vitesse = float((lacher.get("vx", 0.0) ** 2 + lacher.get("vy", 0.0) ** 2) ** 0.5)
    en_l_air = (
        pd.Series(avant["en_l_air"]).fillna(False).astype(bool).to_numpy()
        if "en_l_air" in avant
        else np.zeros(len(avant), dtype=bool)
    )
    # En l'air au lâcher (ou au tick suivant : le décollage et le lâcher sont simultanés).
    saut = _vrai(autour.get("JUMP")) or bool(en_l_air[i : i + 2].any())
    jumpthrow = True
    if saut and en_l_air[: i + 1].any():
        # Décollage = début de la dernière phase en l'air avant le lâcher.
        k = i
        while k > 0 and en_l_air[k - 1]:
            k -= 1
        jumpthrow = (i - k) <= TICKS_JUMPTHROW or not en_l_air[i]
    if _vrai(autour.get("WALK")) and vitesse > 1:
        deplacement = "marche"
    elif _vrai(autour.get("FORWARD")) and vitesse >= VITESSE_COURSE:
        deplacement = "avance"
    elif vitesse >= VITESSE_COURSE:
        deplacement = "deplacement"
    elif vitesse >= VITESSE_MARCHE:
        deplacement = "marche"
    else:
        deplacement = "immobile"
    accroupi = _vrai(autour.get("DUCK")) or bool(lacher.get("accroupi", False))
    return Technique(clic, saut, deplacement, accroupi, jumpthrow)


@dataclass
class Lacher:
    """Le vrai lâcher d'une grenade : tick, position, visée et technique à cet instant."""

    tick: int
    technique: str
    x: float | None = None
    y: float | None = None
    z: float | None = None
    pitch: float | None = None
    yaw: float | None = None


def _valeur(ligne: pd.Series, nom: str) -> float | None:
    v = ligne.get(nom)
    return None if v is None or pd.isna(v) else float(v)


def technique_majoritaire(libelles: list[str | None]) -> tuple[str | None, float | None]:
    """Technique la plus fréquente d'un stuff chez les pros, et sa part."""
    connus = [lib for lib in libelles if lib]
    if not connus:
        return None, None
    libelle, nombre = Counter(connus).most_common(1)[0]
    return libelle, nombre / len(connus)


def lachers(etats: pd.DataFrame, lancers: pd.DataFrame) -> dict[tuple[str, int], Lacher]:
    """(steamid, tick de grenade_thrown) → vrai lâcher, d'après les états qui précèdent."""
    sortie: dict[tuple[str, int], Lacher] = {}
    if not len(etats) or not len(lancers):
        return sortie
    par_joueur = {sid: g.sort_values("tick") for sid, g in etats.groupby("steamid")}
    for _, jet in lancers.iterrows():
        g = par_joueur.get(str(jet["steamid"]))
        if g is None:
            continue
        t = int(jet["tick"])
        avant = g[(g["tick"] <= t) & (g["tick"] >= t - TICKS_AVANT)].reset_index(drop=True)
        if not len(avant):
            avant = g[g["tick"] <= t].tail(1).reset_index(drop=True)
            if not len(avant):
                continue
        ligne = avant.iloc[indice_lacher(avant)]
        sortie[(str(jet["steamid"]), t)] = Lacher(
            tick=int(ligne["tick"]),
            technique=reconnaitre(avant).libelle,
            x=_valeur(ligne, "x"),
            y=_valeur(ligne, "y"),
            z=_valeur(ligne, "z"),
            pitch=_valeur(ligne, "pitch"),
            yaw=_valeur(ligne, "yaw"),
        )
    return sortie


def techniques_des_lancers(
    etats: pd.DataFrame, lancers: pd.DataFrame
) -> dict[tuple[str, int], str]:
    """(steamid, tick du lancer) → libellé de la technique."""
    return {cle: lach.technique for cle, lach in lachers(etats, lancers).items()}


def colonnes_etat(brut: pd.DataFrame) -> dict[str, Any]:
    """Colonnes utiles d'un parse_ticks demoparser2 (boutons inclus s'ils existent)."""
    sortie: dict[str, Any] = {}
    for b in BOUTONS:
        if b in brut:
            sortie[b] = brut[b].fillna(False).astype(bool)
    return sortie
