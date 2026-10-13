"""Angles et directions dans le repère du moteur Source 2.

Conventions du moteur : yaw en degrés, croissant vers la gauche (sens trigonométrique vu du
dessus) ; pitch en degrés, **positif vers le bas**. La position d'un joueur est celle de
ses pieds ; ses yeux sont 64 unités plus haut (46 accroupi).
"""

from __future__ import annotations

import math

HAUTEUR_YEUX = 64.0
HAUTEUR_YEUX_ACCROUPI = 46.0
# Le tir part de l'angle de vue corrigé du recul : vue + 2 × aim punch (weapon_recoil_scale).
ECHELLE_RECUL = 2.0


def hauteur_yeux(accroupi: bool) -> float:
    return HAUTEUR_YEUX_ACCROUPI if accroupi else HAUTEUR_YEUX


def ecart_angulaire(a: float, b: float) -> float:
    """a − b ramené dans ]−180, 180]."""
    d = (a - b) % 360.0
    return d - 360.0 if d > 180.0 else d


def direction(dx: float, dy: float, dz: float) -> tuple[float, float]:
    """(yaw, pitch) qui regarde le long du vecteur (dx, dy, dz)."""
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = -math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return yaw, pitch


def vecteur(yaw: float, pitch: float) -> tuple[float, float, float]:
    y, p = math.radians(yaw), math.radians(pitch)
    return math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p)


def angle_entre(yaw1: float, pitch1: float, yaw2: float, pitch2: float) -> float:
    """Angle (degrés) entre deux directions de visée."""
    a, b = vecteur(yaw1, pitch1), vecteur(yaw2, pitch2)
    prod = sum(i * j for i, j in zip(a, b, strict=True))
    if prod != prod:  # angle inconnu (NaN) : ne pas le ramener à 0°
        return math.nan
    prod = max(-1.0, min(1.0, prod))
    return math.degrees(math.acos(prod))
