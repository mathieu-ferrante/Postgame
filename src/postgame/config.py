"""Lecture de la configuration locale (postgame.toml).

Le fichier réel est ignoré par git ; `postgame.exemple.toml` sert de modèle. Toutes les
valeurs ont un défaut raisonnable pour que le service démarre même sans fichier.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DOSSIER_CS2 = (
    "C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive/game/csgo"
)


@dataclass
class Config:
    hote: str = "0.0.0.0"
    port: int = 8765
    dossier_donnees: Path = Path("data")
    steamid: str = ""
    dossiers_cs2: list[Path] = field(
        default_factory=lambda: [Path(DOSSIER_CS2) / "replays", Path(DOSSIER_CS2)]
    )
    intervalle_s: float = 5.0
    delai_stabilite_s: float = 10.0

    @property
    def chemin_base(self) -> Path:
        return self.dossier_donnees / "postgame.db"

    @property
    def dossier_archives(self) -> Path:
        return self.dossier_donnees / "archives"


def charger_config(chemin: Path | None = None) -> Config:
    """Charge la configuration depuis `chemin`, $POSTGAME_CONFIG ou ./postgame.toml."""
    if chemin is None:
        chemin = Path(os.environ.get("POSTGAME_CONFIG", "postgame.toml"))
    cfg = Config()
    if not chemin.exists():
        return cfg
    with chemin.open("rb") as f:
        brut = tomllib.load(f)

    service = brut.get("service", {})
    cfg.hote = service.get("hote", cfg.hote)
    cfg.port = int(service.get("port", cfg.port))
    if "dossier_donnees" in service:
        dossier = Path(service["dossier_donnees"])
        # Un chemin relatif est relatif au fichier de configuration, pas au dossier courant.
        cfg.dossier_donnees = dossier if dossier.is_absolute() else chemin.parent / dossier

    cfg.steamid = str(brut.get("joueur", {}).get("steamid", "")).strip()

    cs2 = brut.get("cs2", {})
    if "dossiers_demos" in cs2:
        cfg.dossiers_cs2 = [Path(d) for d in cs2["dossiers_demos"]]

    surv = brut.get("surveillance", {})
    cfg.intervalle_s = float(surv.get("intervalle_s", cfg.intervalle_s))
    cfg.delai_stabilite_s = float(surv.get("delai_stabilite_s", cfg.delai_stabilite_s))
    return cfg
