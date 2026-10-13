"""Lecture de la configuration locale (postgame.toml).

Le fichier réel est ignoré par git ; `postgame.exemple.toml` sert de modèle. Toutes les
valeurs ont un défaut raisonnable pour que le service démarre même sans fichier.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_GD = "GeometryDash/geode/mods/mathieu.postgame-journal/sessions"
DOSSIER_CS2 = (
    "C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive/game/csgo"
)


@dataclass
class ConfigDebrief:
    fournisseur: str = "gemini"  # gemini, local, aucun
    modele: str = "gemini-3.1-flash-lite"
    url_local: str = "http://localhost:11434"  # serveur Ollama
    # Prix en dollars par million de jetons (page de tarifs Gemini, octobre 2026).
    prix_entree: float = 0.25
    prix_sortie: float = 1.50
    automatique: bool = True  # rédiger le débrief dès l'import d'une partie
    # Inclure les mesures pas encore vérifiées à la main (NF-06) : à n'activer que pendant
    # la phase de validation, elles sont alors signalées comme telles.
    mesures_experimentales: bool = False
    historique: int = 10  # parties précédentes servant de référence personnelle


@dataclass
class Config:
    hote: str = "0.0.0.0"
    port: int = 8765
    dossier_donnees: Path = Path("data")
    steamid: str = ""
    dossiers_cs2: list[Path] = field(
        default_factory=lambda: [Path(DOSSIER_CS2) / "replays", Path(DOSSIER_CS2)]
    )
    dossiers_gd: list[Path] = field(
        default_factory=lambda: [Path(os.environ.get("LOCALAPPDATA", "")) / DOSSIER_GD]
    )
    intervalle_s: float = 5.0
    delai_stabilite_s: float = 10.0
    debrief: ConfigDebrief = field(default_factory=lambda: ConfigDebrief())
    # Secrets (clé Gemini, clé Riot…) : lus dans secrets.toml ou l'environnement, jamais
    # dans postgame.toml ni dans le dépôt.
    secrets: dict[str, dict[str, str]] = field(default_factory=dict)

    def secret(self, section: str, cle: str, variable: str | None = None) -> str:
        if variable and os.environ.get(variable):
            return os.environ[variable]
        return str(self.secrets.get(section, {}).get(cle, "")).strip()

    # HTTPS (nécessaire pour installer l'interface comme appli sur le téléphone) :
    # certificat et clé générés avec mkcert, voir A_VALIDER.md.
    certificat: Path | None = None
    cle_privee: Path | None = None
    dossier_web: Path = RACINE / "web" / "dist"

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
        cfg.secrets = charger_secrets(chemin.parent / "secrets.toml")
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

    for nom in ("certificat", "cle_privee"):
        if service.get(nom):
            fichier = Path(service[nom])
            setattr(cfg, nom, fichier if fichier.is_absolute() else chemin.parent / fichier)

    cfg.steamid = str(brut.get("joueur", {}).get("steamid", "")).strip()

    cs2 = brut.get("cs2", {})
    if "dossiers_demos" in cs2:
        cfg.dossiers_cs2 = [Path(d) for d in cs2["dossiers_demos"]]

    gd = brut.get("gd", {})
    if "dossiers_journaux" in gd:
        cfg.dossiers_gd = [Path(os.path.expandvars(d)) for d in gd["dossiers_journaux"]]

    surv = brut.get("surveillance", {})
    cfg.intervalle_s = float(surv.get("intervalle_s", cfg.intervalle_s))
    cfg.delai_stabilite_s = float(surv.get("delai_stabilite_s", cfg.delai_stabilite_s))

    deb = brut.get("debrief", {})
    for nom, type_ in (
        ("fournisseur", str),
        ("modele", str),
        ("url_local", str),
        ("prix_entree", float),
        ("prix_sortie", float),
        ("automatique", bool),
        ("mesures_experimentales", bool),
        ("historique", int),
    ):
        if nom in deb:
            setattr(cfg.debrief, nom, type_(deb[nom]))

    cfg.secrets = charger_secrets(chemin.parent / "secrets.toml")
    return cfg


def charger_secrets(chemin: Path) -> dict[str, dict[str, str]]:
    """secrets.toml (ignoré par git) : [gemini] cle = "…", [riot] cle = "…"."""
    if not chemin.exists():
        return {}
    with chemin.open("rb") as f:
        return tomllib.load(f)
