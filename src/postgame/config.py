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
DOSSIER_STEAM = "C:/Program Files (x86)/Steam"
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
    # Pseudos en jeu de Mathieu : repli quand le SteamID64 n'est pas renseigné.
    noms_joueur: list[str] = field(default_factory=list)
    dossiers_cs2: list[Path] = field(
        default_factory=lambda: [Path(DOSSIER_CS2) / "replays", Path(DOSSIER_CS2)]
    )
    dossiers_gd: list[Path] = field(
        default_factory=lambda: [Path(os.environ.get("LOCALAPPDATA", "")) / DOSSIER_GD]
    )
    # Source2Viewer-CLI.exe (outil libre ValveResourceFormat) : exporte les radars officiels
    # depuis les fichiers du jeu. Vide = pas d'export automatique.
    source2viewer: Path | None = None
    # Dossiers de démos / extraits pros importés automatiquement (ex. Google Drive).
    dossiers_pros: list[Path] = field(default_factory=list)
    dossier_steam: Path = Path(DOSSIER_STEAM)  # captures d'écran Steam (F12)
    faceit_pseudo: str = ""
    steam_code_connu: str = ""  # un code de partage déjà connu (point de départ de l'API)
    sources_synchro_minutes: float = 10.0
    riot_id: str = ""  # « Pseudo#TAG »
    riot_plateforme: str = "euw1"
    riot_region: str = "europe"
    riot_synchro_minutes: float = 10.0
    # Pas d'accès réseau aux données statiques (Data Dragon) : utile aux tests et hors ligne.
    hors_ligne: bool = False
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
    cfg.noms_joueur = [str(n) for n in brut.get("joueur", {}).get("noms", [])]

    cs2 = brut.get("cs2", {})
    if "dossiers_demos" in cs2:
        cfg.dossiers_cs2 = [Path(d) for d in cs2["dossiers_demos"]]
    cfg.dossiers_pros = [Path(os.path.expandvars(d)) for d in cs2.get("dossiers_pros", [])]
    if cs2.get("source2viewer"):
        cfg.source2viewer = Path(cs2["source2viewer"])

    gd = brut.get("gd", {})
    if "dossiers_journaux" in gd:
        cfg.dossiers_gd = [Path(os.path.expandvars(d)) for d in gd["dossiers_journaux"]]

    cfg.faceit_pseudo = str(brut.get("faceit", {}).get("pseudo", "")).strip()
    cfg.steam_code_connu = str(brut.get("steam", {}).get("code_connu", "")).strip()
    if brut.get("steam", {}).get("dossier"):
        cfg.dossier_steam = Path(brut["steam"]["dossier"])

    riot = brut.get("riot", {})
    cfg.riot_id = str(riot.get("riot_id", cfg.riot_id)).strip()
    cfg.riot_plateforme = str(riot.get("plateforme", cfg.riot_plateforme))
    cfg.riot_region = str(riot.get("region", cfg.riot_region))
    cfg.riot_synchro_minutes = float(riot.get("synchro_minutes", cfg.riot_synchro_minutes))

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
    from postgame.comptes import appliquer

    appliquer(cfg)  # identifiants appris par Postgame (SteamID64 retrouvé par le pseudo…)
    return cfg


def charger_secrets(chemin: Path) -> dict[str, dict[str, str]]:
    """secrets.toml (ignoré par git) : [gemini] cle = "…", [riot] cle = "…"."""
    if not chemin.exists():
        return {}
    with chemin.open("rb") as f:
        return tomllib.load(f)
