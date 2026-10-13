"""Vrais lineups pros : ce qui est reproduit, quand, et pourquoi à ce moment-là.

Beaucoup de grenades d'un match sont lancées « à l'arrache » (en plein combat, au jugé).
Un lineup, c'est un lancer que les pros reproduisent : même point de lancer, même visée,
même arrivée, plusieurs fois. On ne garde que ceux-là.

Pour chacun, tout vient des démos, rien n'est supposé :
- le moment du lancer dans le round (secondes depuis la fin du freezetime) ;
- ce qui suit : pose de la bombe (où, combien de secondes après), round gagné ou perdu ;
- l'effet obtenu : adversaires aveuglés (durée de flash relevée sur chaque joueur),
  dégâts du molotov ou de la HE, durée réelle de la smoke ;
- la trajectoire réelle de la grenade en vol.

La « raison du timing » est une phrase construite uniquement à partir de ces faits
(ex. « bombe posée sur A 9 s plus tard dans 6 rounds sur 7 ; la smoke dure 18 s »).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

TICKS = 64
RAYON_LANCER = 48.0  # u : même point de lancer (jumpthrow compris)
ECART_VISEE = 3.0  # degrés : même visée (yaw et pitch)
MIN_LINEUP = 3  # lancers identiques, ou 2 par deux joueurs différents
AVEUGLE_S = 1.0  # aveuglé au moins 1 s : flash utile
DELAI_EXECUTION_S = 15.0  # bombe posée dans les 15 s : le lancer prépare l'exécution
DEBUT_ROUND_S = 20.0
PAS_TRAJECTOIRE = 4  # ticks entre deux points de trajectoire gardés


@dataclass
class ContexteDemo:
    """Ce qui se passe autour des lancers d'une démo."""

    gagnants: dict[int, int] = field(default_factory=dict)  # numéro de round → équipe
    poses: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=["tick", "site"]))
    # (lanceur, tick du lancer) → {"effet", "allies", "duree"}
    effets: dict[tuple[str, int], dict[str, float | None]] = field(default_factory=dict)
    # (lanceur, tick du lancer) → trajectoire JSON [[t, x, y, z], …]
    trajectoires: dict[tuple[str, int], str] = field(default_factory=dict)


# --- Lecture du contexte dans une démo -----------------------------------------------------


def site_de(lieu: Any) -> str | None:
    texte = str(lieu or "")
    if texte.endswith("A") and "Bombsite" in texte:
        return "A"
    if texte.endswith("B") and "Bombsite" in texte:
        return "B"
    return None


def gagnants_rounds(parser: Any, debuts: list[int], dernier_tick: int) -> dict[int, int]:
    """Équipe gagnante de chaque round : celle dont le score (team_rounds_total) augmente
    entre le début de ce round et le suivant (les démos GOTV n'ont pas round_end)."""
    if not debuts:
        return {}
    bornes = [max(0, d - 1) for d in debuts] + [dernier_tick]
    try:
        brut = parser.parse_ticks(["team_rounds_total", "team_num"], ticks=sorted(set(bornes)))
    except Exception:
        return {}
    scores = (
        brut.dropna(subset=["team_rounds_total"])
        .groupby(["tick", "team_num"])["team_rounds_total"]
        .max()
    )
    gagnants = {}
    for i in range(len(debuts)):
        avant, apres = bornes[i], bornes[i + 1]
        for equipe in (2, 3):
            try:
                if scores[(apres, equipe)] > scores[(avant, equipe)]:
                    gagnants[i + 1] = equipe
            except KeyError:
                continue
    return gagnants


def poses_bombe(evts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    df = evts.get("bomb_planted")
    if df is None or not len(df):
        return pd.DataFrame(columns=["tick", "site"])
    lieu = (
        df["user_last_place_name"] if "user_last_place_name" in df else pd.Series([None] * len(df))
    )
    return pd.DataFrame({"tick": df["tick"].astype(int), "site": [site_de(v) for v in lieu]})


def effets_grenades(
    parser: Any, g: pd.DataFrame, evts: dict[str, pd.DataFrame]
) -> dict[tuple[str, int], dict[str, float | None]]:
    """Effet réel de chaque grenade associée à son lancer (colonne tick_lancer)."""
    sortie: dict[tuple[str, int], dict[str, float | None]] = {}
    g = g.dropna(subset=["tick_lancer"])
    if not len(g):
        return sortie
    flashs = g[g["type"] == "flash"]
    aveuglement = pd.DataFrame()
    if len(flashs):
        try:
            aveuglement = parser.parse_ticks(
                ["flash_duration", "team_num"], ticks=sorted({int(t) + 2 for t in flashs["tick"]})
            )
            aveuglement["steamid"] = aveuglement["steamid"].astype(str)
        except Exception:
            aveuglement = pd.DataFrame()
    blesses = evts.get("player_hurt")
    for _, r in g.iterrows():
        cle = (str(r["lanceur"]), int(r["tick_lancer"]))
        effet: dict[str, float | None] = {"effet": None, "allies": None, "duree": None}
        if r["type"] == "smoke" and pd.notna(r.get("fin")) and int(r["fin"]) > int(r["tick"]):
            effet["duree"] = round((int(r["fin"]) - int(r["tick"])) / TICKS, 1)
        elif r["type"] == "flash" and len(aveuglement):
            a = aveuglement[aveuglement["tick"] == int(r["tick"]) + 2]
            equipe = a.loc[a["steamid"] == str(r["lanceur"]), "team_num"]
            if len(equipe):
                touches = a[
                    (a["flash_duration"].fillna(0) >= AVEUGLE_S)
                    & (a["steamid"] != str(r["lanceur"]))
                ]
                effet["effet"] = float((touches["team_num"] != equipe.iloc[0]).sum())
                effet["allies"] = float((touches["team_num"] == equipe.iloc[0]).sum())
        elif r["type"] in ("molotov", "he") and blesses is not None and len(blesses):
            arme = "inferno" if r["type"] == "molotov" else "hegrenade"
            fin = int(r["fin"]) if pd.notna(r.get("fin")) else int(r["tick"]) + 7 * TICKS
            fin = max(fin, int(r["tick"]) + 8)
            b = blesses[
                (blesses["attacker_steamid"].astype(str) == str(r["lanceur"]))
                & (blesses["weapon"] == arme)
                & (blesses["tick"] >= int(r["tick"]) - 4)
                & (blesses["tick"] <= fin)
            ]
            effet["effet"] = float(b["dmg_health"].sum())
        sortie[cle] = effet
    return sortie


def trajectoires_lancers(brut: pd.DataFrame, lancers: pd.DataFrame) -> dict[tuple[str, int], str]:
    """parse_grenades → trajectoire réelle de chaque lancer (même lanceur, apparue au lancer)."""
    sortie: dict[tuple[str, int], str] = {}
    if brut is None or not len(brut) or not len(lancers):
        return sortie
    df = brut.dropna(subset=["x", "y"]).sort_values(["grenade_entity_id", "tick"])
    df = df.assign(steamid=df["steamid"].astype(str).str.replace(r"\.0$", "", regex=True))
    # Le jeu réutilise les identifiants de projectile : un trou de plus de 16 ticks ou un
    # autre lanceur commence une nouvelle grenade.
    nouveau = (
        (df["grenade_entity_id"] != df["grenade_entity_id"].shift())
        | (df["tick"].diff() > 16)
        | (df["steamid"] != df["steamid"].shift())
    )
    df = df.assign(vol=nouveau.cumsum())
    debuts = df.groupby("vol").agg(debut=("tick", "min"), steamid=("steamid", "first"))
    for _, jet in lancers.iterrows():
        sid, t = str(jet["steamid"]), int(jet["tick"])
        candidats = debuts[(debuts["steamid"] == sid) & ((debuts["debut"] - t).abs() <= 8)]
        if not len(candidats):
            continue
        entite = (candidats["debut"] - t).abs().idxmin()
        vol = df[df["vol"] == entite].drop_duplicates("tick").sort_values("tick")
        # Fin du vol : la grenade ne bouge plus (smoke posée, molotov éclaté…).
        bouge = np.hypot(vol["x"].diff(), vol["y"].diff()).fillna(1.0) + vol[
            "z"
        ].diff().abs().fillna(0)
        immobile = (bouge < 0.5).to_numpy()
        for i in range(len(vol) - 8):
            if immobile[i : i + 8].all():
                vol = vol.iloc[: i + 1]
                break
        vol = pd.concat([vol.iloc[::PAS_TRAJECTOIRE], vol.iloc[[-1]]]).drop_duplicates("tick")
        sortie[(sid, t)] = json.dumps(
            [
                [int(a), round(float(x)), round(float(y)), round(float(z))]
                for a, x, y, z in zip(vol["tick"], vol["x"], vol["y"], vol["z"], strict=True)
            ],
            separators=(",", ":"),
        )
    return sortie


def contexte_lancer(
    ctx: ContexteDemo,
    lanceur: str,
    tick: int,
    tick_lacher: int | None,
    numero_round: int | None,
    debut_round: int | None,
    fin_round: int | None,
    equipe: int | None,
) -> dict[str, Any]:
    """Colonnes de contexte d'une observation de lancer."""
    t = tick_lacher if tick_lacher is not None else tick
    sortie: dict[str, Any] = {
        "tick_lacher": tick_lacher,
        "temps": round((t - debut_round) / TICKS, 1) if debut_round is not None else None,
        "avant_pose": None,
        "site_pose": None,
        "apres_pose": None,
        "gagne": None,
    }
    if numero_round is not None and equipe in (2, 3) and numero_round in ctx.gagnants:
        sortie["gagne"] = int(ctx.gagnants[numero_round] == equipe)
    if debut_round is not None and len(ctx.poses):
        borne = fin_round if fin_round is not None else debut_round + 200 * TICKS
        dans_round = ctx.poses[(ctx.poses["tick"] >= debut_round) & (ctx.poses["tick"] <= borne)]
        if len(dans_round):
            pose = dans_round.iloc[0]
            sortie["site_pose"] = pose["site"]
            sortie["apres_pose"] = int(t >= int(pose["tick"]))
            if t < int(pose["tick"]):
                sortie["avant_pose"] = round((int(pose["tick"]) - t) / TICKS, 1)
        else:
            sortie["apres_pose"] = 0
    effet = ctx.effets.get((lanceur, tick), {})
    sortie.update({k: effet.get(k) for k in ("effet", "allies", "duree")})
    sortie["trajectoire"] = ctx.trajectoires.get((lanceur, tick))
    return sortie


# --- Lineups : filtre et explication -------------------------------------------------------


def _ecart_angle(a: np.ndarray, reference: float) -> np.ndarray:
    return np.abs((a - reference + 180.0) % 360.0 - 180.0)


def lineups(lots: pd.DataFrame) -> list[pd.DataFrame]:
    """Parmi les lancers arrivés au même endroit (même type, même carte), les groupes
    reproduits : même point de lancer (48 u), même visée (3°), assez répétés."""
    from postgame.games.cs2.references import regrouper

    lots = lots.dropna(subset=["lx", "ly"])
    if len(lots) < 2:
        return []
    groupes = []
    etiquettes = regrouper(lots[["lx", "ly"]].to_numpy(float), rayon=RAYON_LANCER)
    for k in np.unique(etiquettes):
        g = lots[etiquettes == k]
        if "lyaw" in g and g["lyaw"].notna().all() and g["lpitch"].notna().all():
            yaw = float(
                np.degrees(
                    np.arctan2(
                        np.sin(np.radians(g["lyaw"])).median(),
                        np.cos(np.radians(g["lyaw"])).median(),
                    )
                )
            )
            pitch = float(g["lpitch"].median())
            g = g[
                (_ecart_angle(g["lyaw"].to_numpy(float), yaw) <= ECART_VISEE)
                & (np.abs(g["lpitch"].to_numpy(float) - pitch) <= ECART_VISEE)
            ]
        joueurs = g["joueur"].nunique() if "joueur" in g else 1
        if len(g) >= MIN_LINEUP or (len(g) >= 2 and joueurs >= 2):
            groupes.append(g)
    return groupes


def phase(
    camp: str | None,
    temps: float | None,
    avant_pose: float | None,
    apres_pose: int | None,
    site_pose: str | None,
) -> str:
    if apres_pose:
        return "retake" if camp == "CT" else "après la pose"
    if camp == "T" and avant_pose is not None and avant_pose <= DELAI_EXECUTION_S:
        return f"exécution {site_pose}" if site_pose else "exécution"
    if temps is not None and temps <= DEBUT_ROUND_S:
        return "début de round"
    return "milieu de round"


def _s(v: float) -> str:
    """Nombre court à la française : 9, 22,1, 0,7."""
    r = round(float(v), 1)
    return f"{r:.0f}" if r == int(r) else f"{r:.1f}".replace(".", ",")


def expliquer(groupe: pd.DataFrame, type_: str) -> dict[str, Any]:
    """Timing, phase et raison d'un lineup, à partir de ses lancers réels."""
    n = len(groupe)
    col = groupe.get
    phases = [
        phase(c, t, a, p, s)
        for c, t, a, p, s in zip(
            col("camp", pd.Series([None] * n)),
            col("temps", pd.Series([None] * n)),
            col("avant_pose", pd.Series([None] * n)),
            col("apres_pose", pd.Series([None] * n)),
            col("site_pose", pd.Series([None] * n)),
            strict=True,
        )
    ]
    principale, nb_phase = Counter(phases).most_common(1)[0]
    temps = pd.to_numeric(col("temps", pd.Series(dtype=float)), errors="coerce").dropna()
    phrases = []
    sortie: dict[str, Any] = {
        "phase": principale,
        "part_phase": nb_phase / n,
        "temps_median": float(temps.median()) if len(temps) else None,
        "temps_q1": float(temps.quantile(0.25)) if len(temps) else None,
        "temps_q3": float(temps.quantile(0.75)) if len(temps) else None,
    }
    if len(temps):
        phrases.append(
            f"Lancée à {_s(temps.median())} s du début du round"
            + (
                f" (la moitié des fois entre {_s(temps.quantile(0.25))} et "
                f"{_s(temps.quantile(0.75))} s)"
                if n >= 4
                else ""
            )
            + "."
        )
    avant = pd.to_numeric(col("avant_pose", pd.Series(dtype=float)), errors="coerce")
    duree = pd.to_numeric(col("duree", pd.Series(dtype=float)), errors="coerce").dropna()
    sortie["duree_moyenne"] = float(duree.mean()) if len(duree) else None
    if principale.startswith("exécution"):
        lots = avant[[p == principale for p in phases]].dropna()
        site = principale.removeprefix("exécution").strip()
        phrase = (
            f"Dans {nb_phase} round{'s' if nb_phase > 1 else ''} sur {n}, la bombe est posée"
            + (f" sur {site}" if site else "")
            + f" {_s(lots.median())} s plus tard : elle prépare l'exécution."
        )
        if type_ == "smoke" and len(duree):
            reste = duree.median() - lots.median()
            phrase += (
                f" La smoke dure {_s(duree.median())} s : lancée à ce moment, elle tient encore "
                f"{_s(reste)} s après la pose."
                if reste > 0
                else f" La smoke dure {_s(duree.median())} s : elle est déjà dissipée à la pose."
            )
        phrases.append(phrase)
    elif principale in ("après la pose", "retake"):
        phrases.append(
            f"Lancée après la pose de la bombe dans {nb_phase} round{'s' if nb_phase > 1 else ''} "
            f"sur {n}"
            + (" (retake CT)." if principale == "retake" else " (défense de la bombe posée).")
        )
    elif principale == "début de round":
        phrases.append(f"Lancée en début de round dans {nb_phase} cas sur {n}.")
    effet = pd.to_numeric(col("effet", pd.Series(dtype=float)), errors="coerce").dropna()
    sortie["effet_moyen"] = float(effet.mean()) if len(effet) else None
    if type_ == "flash" and len(effet):
        allies = pd.to_numeric(col("allies", pd.Series(dtype=float)), errors="coerce").dropna()
        phrases.append(
            f"Aveugle en moyenne {_s(effet.mean())} adversaire(s) plus d'1 s"
            + (
                f", et {_s(allies.mean())} coéquipier(s)"
                if len(allies) and allies.mean() > 0
                else ""
            )
            + "."
        )
    elif type_ in ("molotov", "he") and len(effet):
        phrases.append(f"Inflige en moyenne {_s(effet.mean())} dégâts.")
    gagne = pd.to_numeric(col("gagne", pd.Series(dtype=float)), errors="coerce").dropna()
    sortie["part_victoire"] = float(gagne.mean()) if len(gagne) else None
    if len(gagne):
        phrases.append(
            f"Round gagné par l'équipe du lanceur {int(gagne.sum())} fois sur {len(gagne)}."
        )
    sortie["raison"] = " ".join(phrases)
    return sortie


def exemple(groupe: pd.DataFrame) -> pd.Series:
    """Le lancer le plus représentatif (le plus proche des médianes) : celui à revoir."""
    if "lyaw" not in groupe or groupe["lyaw"].isna().all():
        return groupe.iloc[0]
    d = (
        np.hypot(groupe["lx"] - groupe["lx"].median(), groupe["ly"] - groupe["ly"].median())
        + _ecart_angle(groupe["lyaw"].to_numpy(float), float(groupe["lyaw"].median())) * 10
    )
    return groupe.iloc[int(np.argmin(d.to_numpy()))]
