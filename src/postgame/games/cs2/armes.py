"""Caractéristiques des armes CS2 utiles aux mesures de mécanique.

`vitesse_max` : vitesse de déplacement maximale avec l'arme en main (unités/s), d'après
les fiches d'armes du jeu (items_game). `cadence` : temps entre deux balles (s).
Valeurs à re-vérifier après chaque grosse mise à jour d'équilibrage (risque « mise à jour
d'un jeu ») ; la version des mesures qui en dépendent est à incrémenter si elles changent.

Seuil de précision : une arme est à précision maximale tant que la vitesse du joueur reste
sous 34 % de sa vitesse maximale (règle du moteur, connue depuis CS:GO et conservée dans
CS2). C'est la base de la mesure de contre-strafe (CS-AIM-01).
"""

from __future__ import annotations

from dataclasses import dataclass

PART_VITESSE_PRECISE = 0.34

# Style de jeu de chaque catégorie : ce qu'on attend d'un bon joueur avec ces armes. Il guide
# le débrief (une AWP ne se juge pas sur les headshots, une SMG tolère le tir en mouvement).
STYLES = {
    "fusil": "duels à moyenne distance : contre-strafe, première balle à hauteur de tête, "
    "contrôle du recul en rafale",
    "sniper": "tenir un angle lunette ouverte, tirer immobile, une balle décisive par duel ; "
    "le headshot n'est pas l'objectif (l'AWP tue au corps)",
    "pistolet": "coup par coup : s'arrêter avant chaque balle, viser la tête",
    "smg": "mobilité et rafales à courte distance ; la précision en mouvement pèse moins",
    "pompe": "très courte distance, positions fermées",
    "mitrailleuse": "rafales longues pour tenir une zone",
}
# Vitesses lunette ouverte : valeurs des fiches d'armes de CS:GO, reprises par CS2.
# À vérifier contre items_game du jeu (vitesse « max_player_speed_alt »).


@dataclass(frozen=True)
class Arme:
    code: str
    libelle: str
    categorie: str  # pistolet, fusil, smg, sniper, pompe, mitrailleuse
    vitesse_max: float
    cadence: float
    vitesse_max_lunette: float | None = None  # lunette ouverte (snipers, AUG, SG 553)

    @property
    def vitesse_precise(self) -> float:
        return self.vitesse_max * PART_VITESSE_PRECISE

    def seuil_precis(self, lunette: bool) -> float:
        """Vitesse sous laquelle le tir est à précision maximale, lunette ouverte ou non."""
        if lunette and self.vitesse_max_lunette:
            return self.vitesse_max_lunette * PART_VITESSE_PRECISE
        return self.vitesse_precise

    @property
    def style(self) -> str:
        return STYLES[self.categorie]


_ARMES = [
    # Fusils
    Arme("ak47", "AK-47", "fusil", 215, 0.100),
    Arme("m4a1", "M4A4", "fusil", 225, 0.090),
    Arme("m4a1_silencer", "M4A1-S", "fusil", 225, 0.100),
    Arme("galilar", "Galil AR", "fusil", 215, 0.090),
    Arme("famas", "FAMAS", "fusil", 220, 0.090),
    Arme("sg556", "SG 553", "fusil", 210, 0.090, 150),
    Arme("aug", "AUG", "fusil", 220, 0.090, 150),
    # Fusils de précision
    Arme("awp", "AWP", "sniper", 200, 1.463, 100),
    Arme("ssg08", "SSG 08", "sniper", 230, 1.250, 230),
    Arme("scar20", "SCAR-20", "sniper", 215, 0.250, 120),
    Arme("g3sg1", "G3SG1", "sniper", 215, 0.250, 120),
    # Pistolets
    Arme("deagle", "Desert Eagle", "pistolet", 230, 0.225),
    Arme("revolver", "R8", "pistolet", 220, 0.500),
    Arme("glock", "Glock-18", "pistolet", 240, 0.150),
    Arme("hkp2000", "P2000", "pistolet", 240, 0.170),
    Arme("usp_silencer", "USP-S", "pistolet", 240, 0.170),
    Arme("p250", "P250", "pistolet", 240, 0.150),
    Arme("fiveseven", "Five-SeveN", "pistolet", 240, 0.150),
    Arme("tec9", "Tec-9", "pistolet", 240, 0.120),
    Arme("cz75a", "CZ75-Auto", "pistolet", 240, 0.100),
    Arme("elite", "Dual Berettas", "pistolet", 240, 0.120),
    # Pistolets-mitrailleurs
    Arme("mac10", "MAC-10", "smg", 240, 0.075),
    Arme("mp9", "MP9", "smg", 240, 0.070),
    Arme("mp7", "MP7", "smg", 220, 0.080),
    Arme("mp5sd", "MP5-SD", "smg", 235, 0.080),
    Arme("ump45", "UMP-45", "smg", 230, 0.090),
    Arme("p90", "P90", "smg", 230, 0.070),
    Arme("bizon", "PP-Bizon", "smg", 240, 0.080),
    # Fusils à pompe et mitrailleuses
    Arme("nova", "Nova", "pompe", 220, 0.880),
    Arme("xm1014", "XM1014", "pompe", 215, 0.350),
    Arme("mag7", "MAG-7", "pompe", 225, 0.850),
    Arme("sawedoff", "Sawed-Off", "pompe", 210, 0.850),
    Arme("negev", "Negev", "mitrailleuse", 150, 0.075),
    Arme("m249", "M249", "mitrailleuse", 195, 0.080),
]

ARMES: dict[str, Arme] = {a.code: a for a in _ARMES}
_PAR_LIBELLE = {a.libelle.lower(): a.code for a in _ARMES}
# Variantes de noms rencontrées selon la source (évènement, propriété, ancienne version).
_ALIAS = {
    "m4a4": "m4a1",
    "m4a1-s": "m4a1_silencer",
    "usp-s": "usp_silencer",
    "usp": "usp_silencer",
    "p2000": "hkp2000",
    "galil": "galilar",
    "sg553": "sg556",
    "sg 553": "sg556",
    "desert eagle": "deagle",
    "r8 revolver": "revolver",
    "dual berettas": "elite",
    "five-seven": "fiveseven",
    "cz75": "cz75a",
    "glock-18": "glock",
    "pp-bizon": "bizon",
    "mp5": "mp5sd",
}


def normaliser(nom: object) -> str:
    """Ramène un nom d'arme quelconque (« weapon_ak47 », « AK-47 », « ak47 ») à son code."""
    if nom is None:
        return ""
    texte = str(nom).strip().lower()
    if texte.startswith("weapon_"):
        texte = texte[len("weapon_") :]
    if texte in ARMES:
        return texte
    return _PAR_LIBELLE.get(texte) or _ALIAS.get(texte) or texte


def arme(nom: object) -> Arme | None:
    return ARMES.get(normaliser(nom))


def est_arme_a_feu(nom: object) -> bool:
    return arme(nom) is not None


def est_arme_de_precision_balle(nom: object) -> bool:
    """Armes où la première balle et le contre-strafe ont un sens (pas les pompes)."""
    a = arme(nom)
    return a is not None and a.categorie != "pompe"


def est_arme_de_rafale(nom: object) -> bool:
    """Armes automatiques où l'étude du spray a un sens."""
    a = arme(nom)
    return a is not None and a.categorie in {"fusil", "smg", "mitrailleuse"}
