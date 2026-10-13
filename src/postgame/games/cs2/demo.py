"""Lecture d'une démo CS2 avec demoparser2 et construction de la fiche de partie.

Deux étapes séparées pour pouvoir tester sans vraie démo :
- `extraire()` appelle demoparser2 et renvoie des données brutes (`DonneesDemo`) ;
- `construire_fiche()` est une fonction pure qui transforme ces données en `Fiche`.

Noms de propriétés demoparser2 : voir src/parser/src/maps.rs du dépôt LaihoE/demoparser
(ex. `team_rounds_total` = CCSTeam.m_iScore, `is_matchmaking` = m_bIsQueuedMatchmaking).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from postgame.games.base import ErreurLecture, Fiche

TICKS_PAR_SECONDE = 64
EQUIPE_T, EQUIPE_CT = 2, 3

# Évènements utiles à la fiche. On ne demande que ceux présents dans la démo.
EVENEMENTS_FICHE = (
    "round_end",
    "player_death",
    "round_announce_match_start",
    "begin_new_match",
    "cs_win_panel_match",
)

# Propriétés lues au dernier tick, une ligne par joueur.
PROPS_ETAT_FINAL = [
    "team_num",
    "team_rounds_total",
    "kills_total",
    "deaths_total",
    "assists_total",
    "is_matchmaking",
    "match_making_mode",
    "is_valve_dedicated_server",
]
PROPS_ETAT_FINAL_MINIMAL = ["team_num", "team_rounds_total"]


@dataclass
class DonneesDemo:
    """Données brutes nécessaires à la fiche, indépendantes de demoparser2."""

    entete: dict[str, Any]
    evenements: dict[str, pd.DataFrame]
    etat_final: pd.DataFrame  # colonnes : steamid, name, + PROPS_ETAT_FINAL disponibles
    date_fichier: datetime
    avertissements: list[str] = field(default_factory=list)


def extraire(chemin: Path) -> DonneesDemo:
    """Lit la démo avec demoparser2. Lève ErreurLecture si elle est illisible."""
    try:
        from demoparser2 import DemoParser

        parser = DemoParser(str(chemin))
        entete = dict(parser.parse_header())
        presents = set(parser.list_game_events())
    except Exception as exc:  # demoparser2 lève des exceptions génériques
        raise ErreurLecture(f"démo illisible : {exc}") from exc

    avertissements: list[str] = []
    voulus = [e for e in EVENEMENTS_FICHE if e in presents]
    evenements: dict[str, pd.DataFrame] = {}
    if voulus:
        try:
            evenements = dict(parser.parse_events(voulus))
        except Exception as exc:
            raise ErreurLecture(f"évènements illisibles : {exc}") from exc

    dernier_tick = _dernier_tick(evenements)
    etat_final = pd.DataFrame()
    if dernier_tick is not None:
        for props in (PROPS_ETAT_FINAL, PROPS_ETAT_FINAL_MINIMAL):
            try:
                etat_final = parser.parse_ticks(props, ticks=[dernier_tick])
                break
            except Exception as exc:
                avertissements.append(f"parse_ticks({len(props)} props) : {exc}")
    else:
        avertissements.append("aucun évènement : impossible de lire l'état final")

    return DonneesDemo(
        entete=entete,
        evenements=evenements,
        etat_final=etat_final,
        date_fichier=datetime.fromtimestamp(chemin.stat().st_mtime).astimezone(),
        avertissements=avertissements,
    )


def _dernier_tick(evenements: dict[str, pd.DataFrame]) -> int | None:
    ticks = [int(df["tick"].max()) for df in evenements.values() if len(df) and "tick" in df]
    return max(ticks) if ticks else None


def _tick_debut(evenements: dict[str, pd.DataFrame]) -> int:
    """Début du match réel (après l'échauffement) si la démo l'indique, sinon 0."""
    for nom in ("round_announce_match_start", "begin_new_match"):
        df = evenements.get(nom)
        if df is not None and len(df):
            return int(df["tick"].max())
    return 0


def _apres(df: pd.DataFrame | None, tick: int) -> pd.DataFrame:
    if df is None or not len(df):
        return pd.DataFrame(columns=["tick"])
    return df[df["tick"] >= tick]


def _entier(valeur: Any) -> int | None:
    try:
        if pd.isna(valeur):
            return None
        return int(valeur)
    except (TypeError, ValueError):
        return None


def trouver_joueur(donnees: DonneesDemo, steamid: str) -> pd.Series | None:
    """Ligne du joueur suivi dans l'état final : par SteamID64, sinon (démo enregistrée par
    le client) par le nom du client présent dans l'en-tête."""
    etat = donnees.etat_final
    if not len(etat):
        return None
    if steamid and "steamid" in etat:
        lignes = etat[etat["steamid"].astype(str) == str(steamid)]
        if len(lignes):
            return lignes.iloc[0]
    client = str(donnees.entete.get("client_name", "") or "").strip()
    if client and "name" in etat:
        lignes = etat[etat["name"].astype(str) == client]
        if len(lignes):
            return lignes.iloc[0]
    return None


def deduire_mode(nb_joueurs: int, nb_rounds: int, nb_morts: int, score_max: int | None) -> str:
    """Heuristique de mode de jeu, à confirmer sur démos réelles (voir A_VALIDER.md).

    - deathmatch : beaucoup de morts pour au plus un round (réapparitions) ;
    - wingman : 4 joueurs ou moins ;
    - competitif : une équipe atteint 13 rounds (MR12, Premier et compétitif) ;
    - autre : tout le reste (occasionnel, partie inachevée…).
    """
    if nb_rounds <= 1 and nb_morts >= max(10, 2 * nb_joueurs):
        return "deathmatch"
    if 0 < nb_joueurs <= 4:
        return "wingman"
    if score_max is not None and score_max >= 13:
        return "competitif"
    return "autre"


def construire_fiche(donnees: DonneesDemo, steamid: str = "") -> Fiche:
    ev = donnees.evenements
    debut = _tick_debut(ev)
    fin = _dernier_tick(ev)
    rounds = _apres(ev.get("round_end"), debut)
    morts = _apres(ev.get("player_death"), debut)

    etat = donnees.etat_final
    if len(etat) and "team_num" in etat:
        etat = etat[etat["team_num"].isin([EQUIPE_T, EQUIPE_CT])]
    nb_joueurs = int(etat["steamid"].nunique()) if len(etat) and "steamid" in etat else 0

    scores: dict[int, int] = {}
    if len(etat) and "team_rounds_total" in etat:
        for equipe, groupe in etat.groupby("team_num"):
            valeur = _entier(groupe["team_rounds_total"].max())
            if valeur is not None:
                scores[int(equipe)] = valeur
    score_max = max(scores.values()) if scores else None

    mode = deduire_mode(nb_joueurs, len(rounds), len(morts), score_max)
    joueur = trouver_joueur(donnees, steamid)

    details: dict[str, Any] = {
        "serveur": donnees.entete.get("server_name", ""),
        "client": donnees.entete.get("client_name", ""),
        "version_demo": donnees.entete.get("demo_version_name", ""),
        "nb_joueurs": nb_joueurs,
        "nb_rounds": len(rounds),
        "nb_morts": len(morts),
        "joueur_trouve": joueur is not None,
    }
    for prop in ("is_matchmaking", "match_making_mode", "is_valve_dedicated_server"):
        if len(etat) and prop in etat:
            valeur = etat[prop].iloc[0]
            details[prop] = (
                None if pd.isna(valeur) else valeur.item() if hasattr(valeur, "item") else valeur
            )
    if donnees.avertissements:
        details["avertissements"] = donnees.avertissements

    resultat, score_joueur, score_adverse = "inconnu", None, None
    if joueur is not None:
        details["joueur"] = str(joueur.get("name", ""))
        for prop, cle in (
            ("kills_total", "kills"),
            ("deaths_total", "morts"),
            ("assists_total", "assistances"),
        ):
            if prop in joueur:
                details[cle] = _entier(joueur[prop])
        if mode == "deathmatch":
            resultat = "sans_objet"
        else:
            equipe = _entier(joueur.get("team_num"))
            adverse = EQUIPE_CT if equipe == EQUIPE_T else EQUIPE_T
            score_joueur, score_adverse = scores.get(equipe), scores.get(adverse)
            if score_joueur is not None and score_adverse is not None:
                if score_joueur > score_adverse:
                    resultat = "victoire"
                elif score_joueur < score_adverse:
                    resultat = "defaite"
                else:
                    resultat = "nul"
    elif mode == "deathmatch":
        resultat = "sans_objet"

    duree = (fin - debut) / TICKS_PAR_SECONDE if fin is not None else None
    carte = str(donnees.entete.get("map_name", "") or "inconnue")
    return Fiche(
        date_partie=donnees.date_fichier.astimezone(UTC).isoformat(timespec="seconds"),
        mode=mode,
        carte=carte,
        resultat=resultat,
        score_joueur=score_joueur,
        score_adverse=score_adverse,
        duree_s=round(duree, 1) if duree is not None else None,
        details=details,
    )
