"""Recommandation d'achat CS2 pour le second écran (CS-LIVE-01).

Structure du match selon le mode (guides CS2, octobre 2026) :
- Premier et compétitif : MR12 (moitiés de 12 rounds, 13 pour gagner), puis prolongations
  en deux moitiés de 3 rounds (4 rounds sur 6 pour gagner), argent remis à 12 500 $ ;
- Wingman : moitiés de 8 rounds, 9 pour gagner, pas de prolongation.

Règles de l'économie (Premier et compétitif) :
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
MOITIE_PROLONGATION = 3


@dataclass(frozen=True)
class Structure:
    moitie: int  # rounds par moitié du temps réglementaire
    prolongation: bool


STRUCTURES = {"scrimcomp2v2": Structure(8, False)}  # Wingman
STRUCTURE_STANDARD = Structure(ROUNDS_PAR_MOITIE, True)


def structure(mode: str | None) -> Structure:
    return STRUCTURES.get(mode or "", STRUCTURE_STANDARD)


def moment(numero_round: int, score_adverse: int, s: Structure) -> tuple[bool, bool, bool]:
    """(round pistolet, dernier round d'une moitié, balle de match adverse)."""
    reglementaire = 2 * s.moitie
    if numero_round <= reglementaire or not s.prolongation:
        pistolet = numero_round in (1, s.moitie + 1)
        dernier = numero_round in (s.moitie, reglementaire)
        balle = score_adverse == s.moitie  # un round de plus et l'adversaire gagne
        return pistolet, dernier, balle
    # Prolongation k (0, 1, …) : rounds reglementaire + 6k + 1 … + 6 ; on gagne à 4 sur 6.
    k, rang = divmod(numero_round - reglementaire - 1, 2 * MOITIE_PROLONGATION)
    dernier = rang + 1 in (MOITIE_PROLONGATION, 2 * MOITIE_PROLONGATION)
    balle = score_adverse == s.moitie + MOITIE_PROLONGATION * k + MOITIE_PROLONGATION
    return False, dernier, balle


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
    mode: str | None = None,
) -> Recommandation:
    """`numero_round` : round à jouer (1 = premier). `defaites_consecutives` : série de
    l'équipe de Mathieu avant ce round."""
    camp = camp if camp in ACHAT_COMPLET else "T"
    complet = ACHAT_COMPLET[camp]
    si_defaite = min(ARGENT_MAX, argent + prime_defaite(defaites_consecutives))
    # Balle de match adverse : perdre ce round termine le match, garder de l'argent est inutile.
    pistolet, dernier_de_moitie, balle_de_match = moment(
        numero_round, score_adverse, structure(mode)
    )

    def reco(type_: str, titre: str, raison: str) -> Recommandation:
        return Recommandation(type_, titre, raison, argent, si_defaite)

    if pistolet:
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
