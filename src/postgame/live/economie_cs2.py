"""Recommandation d'achat CS2 pour le second écran (CS-LIVE-01).

Règles de l'économie MR12 (Premier et compétitif) :
- défaite : 1 400 $, puis +500 $ par défaite consécutive, plafonné à 3 400 $ ;
- victoire : 3 250 $ (3 500 $ si la bombe explose ou est désamorcée, non distingué ici) ;
- argent plafonné à 16 000 $.

GSI ne donne pas l'argent des coéquipiers à un joueur (seulement aux spectateurs) : la
recommandation repose sur l'argent de Mathieu, la série de défaites de son équipe et le
moment du match. C'est un conseil, pas une consigne : l'équipe décide.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

ROUNDS_PAR_MOITIE = 12
PRIME_DEFAITE = [1400, 1900, 2400, 2900, 3400]
GAIN_VICTOIRE = 3250
ARGENT_MAX = 16000
# Coût d'un achat complet : fusil + gilet-casque + grenades (+ kit côté CT).
ACHAT_COMPLET = {"T": 2700 + 1000 + 700, "CT": 2900 + 1000 + 400 + 700}
ACHAT_MINIMUM_UTILE = {"T": 1000 + 700, "CT": 1000 + 700}  # gilet + pistolet amélioré


@dataclass
class Recommandation:
    type: str  # complet, force, eco, pistolet, tout
    titre: str
    raison: str
    argent: int
    argent_round_suivant_si_defaite: int

    def en_dict(self) -> dict:
        return asdict(self)


def prime_defaite(defaites_consecutives: int) -> int:
    """Gain si le round en cours est perdu, sachant la série de défaites avant lui."""
    return PRIME_DEFAITE[min(max(defaites_consecutives, 0), len(PRIME_DEFAITE) - 1)]


def recommander(
    argent: int,
    camp: str,
    numero_round: int,
    defaites_consecutives: int,
    score_equipe: int,
    score_adverse: int,
) -> Recommandation:
    """`numero_round` : round à jouer (1 = premier). `defaites_consecutives` : série de
    l'équipe de Mathieu avant ce round."""
    camp = camp if camp in ACHAT_COMPLET else "T"
    complet = ACHAT_COMPLET[camp]
    si_defaite = min(ARGENT_MAX, argent + prime_defaite(defaites_consecutives))
    dernier_de_moitie = numero_round in (ROUNDS_PAR_MOITIE, 2 * ROUNDS_PAR_MOITIE)
    # Balle de match adverse : perdre ce round termine le match, garder de l'argent est inutile.
    balle_de_match = score_adverse >= ROUNDS_PAR_MOITIE

    def reco(type_: str, titre: str, raison: str) -> Recommandation:
        return Recommandation(type_, titre, raison, argent, si_defaite)

    if numero_round in (1, ROUNDS_PAR_MOITIE + 1):
        return reco(
            "pistolet",
            "Round pistolet",
            "Gilet + pistolet de base, ou pistolet amélioré + grenades.",
        )
    if dernier_de_moitie or balle_de_match:
        return reco(
            "tout",
            "Tout dépenser",
            "Dernier round de la moitié ou balle de match adverse : l'argent ne sert plus après.",
        )
    if argent >= complet:
        return reco(
            "complet",
            "Achat complet",
            f"{argent} $ couvrent fusil, gilet-casque et grenades ({complet} $).",
        )
    minimum = ACHAT_MINIMUM_UTILE[camp]
    apres_force = min(ARGENT_MAX, argent - minimum + prime_defaite(defaites_consecutives))
    if argent >= minimum and apres_force >= complet:
        return reco(
            "force",
            "Force possible",
            f"Même en dépensant {minimum} $ et en perdant, tu auras {apres_force} $ au "
            f"prochain round : l'achat complet suivant reste assuré.",
        )
    return reco(
        "eco",
        "Éco",
        f"Garde ton argent : {si_defaite} $ au prochain round en cas de défaite, "
        f"contre {complet} $ pour un achat complet.",
    )
