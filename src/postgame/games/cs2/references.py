"""Références apprises sur démos pros (lot L3 : CS-REF-01, CS-UTL-01, CS-POS-04).

Rien n'est écrit à la main : on relève dans chaque démo pro
- chaque grenade (smoke, flash, molotov) : point d'arrivée, point de lancer, lieux ;
- la position « installée » de chaque joueur 20 s après la fin du freeze (camp, lieu) ;
- des positions échantillonnées avec leur nom de lieu, pour nommer les points d'arrivée.

Ces observations sont stockées (une démo n'est lue qu'une fois), puis regroupées par carte
pour former le catalogue : un lancer de référence = un groupe d'au moins 3 points d'arrivée
à moins de 120 u les uns des autres. Les smokes de Mathieu sont ensuite rattachées à une
référence (reconnue), signalées ratées de N unités, ou hors référence.

Les noms de lieux viennent de la carte elle-même (propriété `last_place_name`).
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from postgame.db import Base, maintenant
from postgame.games.base import ErreurLecture
from postgame.games.cs2.donnees import (
    DELAI_INSTALLATION_TICKS,
    TICKS_PAR_SECONDE,
    DonneesMatch,
    Positions,
    _steamid,
    _tick,
    code_grenade,
    construire_rounds,
    extraire_grenades,
)
from postgame.mesures import Preuve, ResultatAnalyse, definir, mesure

journal = logging.getLogger(__name__)

TYPES_REFERENCE = ("smoke", "flash", "molotov")
RAYON_GROUPE = 120.0  # u : points d'arrivée d'un même lancer
MIN_OCCURRENCES = 3
DISTANCE_RECONNUE = 150.0  # u : smoke de Mathieu rattachée à une référence
DISTANCE_RATEE = 400.0  # u : au-delà, hors référence
PART_POSITION_COURANTE = 0.05  # un lieu tenu dans 5 % des rounds pros est une position courante
RAYON_SMOKE = 144.0  # u : rayon d'une smoke CS2 déployée
DISTANCE_MAX_LIGNE = 3000.0
PAS_ECHANTILLON_TICKS = 5 * TICKS_PAR_SECONDE
PAS_LIGNE_TICKS = TICKS_PAR_SECONDE // 2
CAMPS = {2: "T", 3: "CT"}

D_SMOKE_RECONNUES = definir(
    "cs2.smoke.part_reconnues",
    1,
    "%",
    "Part des smokes de Mathieu qui arrivent à moins de 150 u d'une smoke de référence pro.",
)
D_SMOKE_ECART = definir(
    "cs2.smoke.ecart_median_reference",
    1,
    "u",
    "Écart médian à la smoke de référence la plus proche (smokes à moins de 400 u).",
    sens="bas",
)
D_SMOKE_LIGNE = definir(
    "cs2.smoke.part_ligne_coupee",
    1,
    "%",
    "Part des smokes qui coupent au moins une ligne de vue adversaire–coéquipier pendant leur "
    "durée (approximation 2D, sans murs).",
)
D_MOLO_RECONNUES = definir(
    "cs2.molotov.part_reconnues",
    1,
    "%",
    "Part des molotovs de Mathieu qui arrivent à moins de 150 u d'un molotov de référence.",
)
D_POSITIONS_PRO = definir(
    "cs2.position.part_positions_pro",
    1,
    "%",
    "Part des rounds où le lieu tenu par Mathieu 20 s après le freeze est tenu par les pros "
    "(même carte, même camp) dans au moins 5 % des rounds.",
)

# --- Extraction des observations d'une démo pro -------------------------------------------


def associer_lancers(lancers: pd.DataFrame, grenades: pd.DataFrame) -> pd.DataFrame:
    """Associe à chaque grenade éclatée le lancer correspondant (même joueur, même type, le
    plus ancien non encore utilisé : premier lancé, premier éclaté). Ajoute la colonne
    tick_lancer (ou NaN)."""
    g = grenades.copy()
    g["tick_lancer"] = np.nan
    if not len(lancers) or not len(g):
        return g
    disponibles: dict[tuple[str, str], list[int]] = {}
    for _, jet in lancers.sort_values("tick").iterrows():
        disponibles.setdefault((str(jet["steamid"]), str(jet["type"])), []).append(int(jet["tick"]))
    for i, row in g.sort_values("tick").iterrows():
        file = disponibles.get((str(row["lanceur"]), str(row["type"])), [])
        candidats = [t for t in file if t <= row["tick"]]
        if candidats:
            t = candidats[0]  # premier lancé, premier éclaté
            file.remove(t)
            g.at[i, "tick_lancer"] = t
    return g


def observations_depuis(
    carte: str,
    grenades: pd.DataFrame,
    lancers: pd.DataFrame,
    etats: pd.DataFrame,
    debuts: list[int],
) -> pd.DataFrame:
    """Observations d'une démo à partir de données déjà extraites (fonction pure).

    `etats` : tick, steamid, x, y, z, equipe, vivant, lieu — aux ticks de lancer,
    d'installation et d'échantillonnage.
    """
    colonnes = [
        "carte",
        "genre",
        "type",
        "camp",
        "lieu",
        "x",
        "y",
        "z",
        "lx",
        "ly",
        "lz",
        "lpitch",
        "lyaw",
        "saut",
        "accroupi",
    ]
    lignes = []
    index = etats.set_index(["tick", "steamid"]) if len(etats) else None

    def etat(tick, sid):
        if index is None:
            return None
        try:
            return index.loc[(int(tick), str(sid))]
        except KeyError:
            return None

    for _, g in associer_lancers(lancers, grenades).iterrows():
        if g["type"] not in TYPES_REFERENCE or pd.isna(g["x"]):
            continue
        e = etat(g["tick_lancer"], g["lanceur"]) if pd.notna(g["tick_lancer"]) else None
        lignes.append(
            {
                "carte": carte,
                "genre": "lancer",
                "type": g["type"],
                "camp": CAMPS.get(int(e["equipe"])) if e is not None else None,
                "lieu": e["lieu"] if e is not None else None,
                "x": g["x"],
                "y": g["y"],
                "z": g["z"],
                "lx": e["x"] if e is not None else None,
                "ly": e["y"] if e is not None else None,
                "lz": e["z"] if e is not None else None,
                "lpitch": e.get("pitch") if e is not None else None,
                "lyaw": e.get("yaw") if e is not None else None,
                "saut": int(bool(e.get("en_l_air"))) if e is not None else None,
                "accroupi": int(bool(e.get("accroupi"))) if e is not None else None,
            }
        )
    installations = {d + DELAI_INSTALLATION_TICKS for d in debuts}
    if len(etats):
        for _, e in etats[etats["vivant"]].iterrows():
            genre = "position" if int(e["tick"]) in installations else "lieu"
            if not e["lieu"]:
                continue
            lignes.append(
                {
                    "carte": carte,
                    "genre": genre,
                    "type": None,
                    "camp": CAMPS.get(int(e["equipe"])),
                    "lieu": e["lieu"],
                    "x": e["x"],
                    "y": e["y"],
                    "z": e["z"],
                    "lx": None,
                    "ly": None,
                    "lz": None,
                    "lpitch": None,
                    "lyaw": None,
                    "saut": None,
                    "accroupi": None,
                }
            )
    return pd.DataFrame(lignes, columns=colonnes)


EVENEMENTS_PRO = [
    "grenade_thrown",
    "smokegrenade_detonate",
    "smokegrenade_expired",
    "flashbang_detonate",
    "hegrenade_detonate",
    "molotov_detonate",
    "inferno_startburn",
    "inferno_expire",
    "round_freeze_end",
    "round_end",
]


def extraire_observations(chemin: Path) -> pd.DataFrame:
    """Lit une démo pro avec demoparser2 et en tire les observations."""
    try:
        from demoparser2 import DemoParser

        parser = DemoParser(str(chemin))
        carte = str(parser.parse_header().get("map_name", ""))
        presents = set(parser.list_game_events())
        evts = dict(parser.parse_events([e for e in EVENEMENTS_PRO if e in presents]))
    except Exception as exc:
        raise ErreurLecture(f"démo pro illisible : {exc}") from exc

    grenades = extraire_grenades(evts)
    jets = evts.get("grenade_thrown")
    lancers = pd.DataFrame(columns=["tick", "steamid", "type"])
    if jets is not None and len(jets):
        lancers = pd.DataFrame(
            {
                "tick": _tick(jets),
                "steamid": _steamid(jets["user_steamid"]),
                "type": jets["weapon"].map(code_grenade),
            }
        )
    vide = pd.DataFrame(columns=["tick"])
    debuts = sorted(evts.get("round_freeze_end", vide)["tick"].astype(int).tolist())
    fins = sorted(evts.get("round_end", vide)["tick"].astype(int).tolist())
    rounds = construire_rounds(debuts, fins)
    instants = set(lancers["tick"].astype(int)) | {d + DELAI_INSTALLATION_TICKS for d in debuts}
    for _, r in rounds.iterrows():
        fin = min(int(r["fin"]), int(r["debut"]) + 120 * TICKS_PAR_SECONDE)
        instants |= set(range(int(r["debut"]), fin, PAS_ECHANTILLON_TICKS))
    etats = pd.DataFrame(columns=["tick", "steamid", "x", "y", "z", "equipe", "vivant", "lieu"])
    if instants:
        brut = parser.parse_ticks(
            [
                "X",
                "Y",
                "Z",
                "team_num",
                "is_alive",
                "last_place_name",
                "pitch",
                "yaw",
                "is_airborne",
                "ducked",
            ],
            ticks=sorted(instants),
        )
        etats = pd.DataFrame(
            {
                "tick": brut["tick"].astype("int64"),
                "steamid": _steamid(brut["steamid"]),
                "x": brut["X"].astype(float),
                "y": brut["Y"].astype(float),
                "z": brut["Z"].astype(float),
                "equipe": brut["team_num"].fillna(0).astype(int),
                "vivant": brut["is_alive"].fillna(False).astype(bool),
                "lieu": brut["last_place_name"].fillna("").astype(str),
                "pitch": brut["pitch"].astype(float),
                "yaw": brut["yaw"].astype(float),
                "en_l_air": brut["is_airborne"].fillna(False).astype(bool),
                "accroupi": brut["ducked"].fillna(False).astype(bool),
            }
        )
    return observations_depuis(carte, grenades, lancers, etats, debuts)


# --- Regroupement et catalogue ------------------------------------------------------------


def regrouper(points: np.ndarray, rayon: float = RAYON_GROUPE, iterations: int = 5) -> np.ndarray:
    """Regroupement simple et déterministe : chaque point rejoint le centre le plus proche à
    moins de `rayon`, sinon crée un groupe ; les centres sont recalculés quelques fois.
    Renvoie l'étiquette de groupe de chaque point."""
    if not len(points):
        return np.array([], dtype=int)
    centres: list[np.ndarray] = []
    etiquettes = np.full(len(points), -1)
    for i, p in enumerate(points):
        if centres:
            d = np.linalg.norm(np.array(centres) - p, axis=1)
            j = int(np.argmin(d))
            if d[j] <= rayon:
                etiquettes[i] = j
                continue
        centres.append(p.astype(float))
        etiquettes[i] = len(centres) - 1
    for _ in range(iterations):
        c = np.array(
            [
                points[etiquettes == k].mean(axis=0)
                if (etiquettes == k).any()
                else np.array([np.inf, np.inf])
                for k in range(len(centres))
            ]
        )
        d = np.linalg.norm(points[:, None, :] - c[None, :, :], axis=2)
        nouvelles = np.argmin(d, axis=1)
        nouvelles[d[np.arange(len(points)), nouvelles] > rayon] = -1
        # Un point orphelin garde son groupe d'origine.
        nouvelles = np.where(nouvelles == -1, etiquettes, nouvelles)
        if np.array_equal(nouvelles, etiquettes):
            break
        etiquettes = nouvelles
    return etiquettes


def yaw_moyen(yaws: pd.Series) -> float:
    """Moyenne circulaire (−170° et 170° → 180°, pas 0°)."""
    r = np.radians(yaws.astype(float).to_numpy())
    return float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())))


def _lieu_le_plus_proche(lieux: pd.DataFrame, x: float, y: float) -> str | None:
    if not len(lieux):
        return None
    d2 = (lieux["x"] - x) ** 2 + (lieux["y"] - y) ** 2
    return str(lieux.loc[d2.idxmin(), "lieu"])


def construire_catalogue(
    observations: pd.DataFrame, nb_demos_par_obs: pd.Series | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(lancers de référence, positions de référence) à partir des observations."""
    lancers_ref, positions_ref = [], []
    for carte, obs in observations.groupby("carte"):
        lieux = obs[obs["genre"].isin(["lieu", "position"])]
        for type_ in TYPES_REFERENCE:
            lots = obs[(obs["genre"] == "lancer") & (obs["type"] == type_)]
            if len(lots) < MIN_OCCURRENCES:
                continue
            etiquettes = regrouper(lots[["x", "y"]].to_numpy(float))
            for k in np.unique(etiquettes):
                groupe = lots[etiquettes == k]
                if len(groupe) < MIN_OCCURRENCES:
                    continue
                x, y, z = groupe[["x", "y", "z"]].mean()
                lieux_lancer = groupe["lieu"].dropna()
                angles = groupe.dropna(subset=["lyaw"]) if "lyaw" in groupe else groupe.iloc[0:0]
                lancers_ref.append(
                    {
                        "carte": carte,
                        "type": type_,
                        "x": x,
                        "y": y,
                        "z": z,
                        "lx": groupe["lx"].mean(),
                        "ly": groupe["ly"].mean(),
                        "lz": groupe["lz"].mean(),
                        "lieu_arrivee": _lieu_le_plus_proche(lieux, x, y),
                        "lieu_lancer": Counter(lieux_lancer).most_common(1)[0][0]
                        if len(lieux_lancer)
                        else None,
                        "nb": len(groupe),
                        "nb_demos": int(groupe["empreinte"].nunique())
                        if "empreinte" in groupe
                        else 1,
                        "lpitch": float(angles["lpitch"].median()) if len(angles) else None,
                        "lyaw": yaw_moyen(angles["lyaw"]) if len(angles) else None,
                        "part_saut": float(angles["saut"].mean()) if len(angles) else None,
                        "part_accroupi": float(angles["accroupi"].mean()) if len(angles) else None,
                    }
                )
        installes = obs[(obs["genre"] == "position") & obs["camp"].notna()]
        for camp, lot in installes.groupby("camp"):
            total = len(lot)
            for lieu, g in lot.groupby("lieu"):
                positions_ref.append(
                    {
                        "carte": carte,
                        "camp": camp,
                        "lieu": lieu,
                        "x": g["x"].mean(),
                        "y": g["y"].mean(),
                        "nb": len(g),
                        "part": len(g) / total,
                    }
                )
    colonnes_l = [
        "carte",
        "type",
        "x",
        "y",
        "z",
        "lx",
        "ly",
        "lz",
        "lieu_arrivee",
        "lieu_lancer",
        "nb",
        "nb_demos",
        "lpitch",
        "lyaw",
        "part_saut",
        "part_accroupi",
    ]
    colonnes_p = ["carte", "camp", "lieu", "x", "y", "nb", "part"]
    return (
        pd.DataFrame(lancers_ref, columns=colonnes_l),
        pd.DataFrame(positions_ref, columns=colonnes_p),
    )


# --- Stockage -----------------------------------------------------------------------------


MIN_ECHANTILLON_PRO = 3  # mesure d'un joueur retenue si l'échantillon du match atteint 3


def mesures_des_joueurs(chemin: Path) -> list[tuple[str, str, dict, float, int | None]]:
    """Analyse la mécanique de **chaque joueur** d'une démo avec le code qui analyse Mathieu :
    (joueur, mesure, contexte discriminant, valeur, échantillon)."""
    from postgame.debrief.constats import contexte_discriminant
    from postgame.games.cs2.donnees import extraire_match
    from postgame.games.cs2.mecanique import analyser_mecanique

    try:
        from demoparser2 import DemoParser

        infos = DemoParser(str(chemin)).parse_player_info()
        premier = str(infos["steamid"].iloc[0])
        d = extraire_match(chemin, premier)
    except Exception as exc:
        raise ErreurLecture(f"démo pro illisible : {exc}") from exc
    sortie = []
    for joueur in sorted(set(d.ticks["steamid"])):
        for m in analyser_mecanique(d.pour(joueur)).mesures:
            n = m.contexte.get("n")
            if m.valeur is None or (n is not None and n < MIN_ECHANTILLON_PRO):
                continue
            sortie.append((joueur, m.nom, contexte_discriminant(m.contexte), m.valeur, n))
    return sortie


def ajouter_demo_pro(base: Base, chemin: Path) -> str:
    """Lit une démo pro et stocke ses observations (une seule fois par démo)."""
    from postgame.importation import empreinte_fichier

    empreinte = empreinte_fichier(chemin)
    with base.transaction() as cx:
        if cx.execute("SELECT 1 FROM cs2_ref_demos WHERE empreinte = ?", (empreinte,)).fetchone():
            return "deja_connue"
    obs = extraire_observations(chemin)
    carte = str(obs["carte"].iloc[0]) if len(obs) else ""
    with base.transaction() as cx:
        cx.execute(
            "INSERT INTO cs2_ref_demos VALUES (?, ?, ?, ?)",
            (empreinte, chemin.name, carte, maintenant()),
        )
        cx.executemany(
            "INSERT INTO cs2_ref_observations (empreinte, carte, genre, type, camp, lieu, x, y, "
            "z, lx, ly, lz, lpitch, lyaw, saut, accroupi) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (empreinte, *[None if pd.isna(v) else v for v in ligne])
                for ligne in obs.reindex(
                    columns=[
                        "carte",
                        "genre",
                        "type",
                        "camp",
                        "lieu",
                        "x",
                        "y",
                        "z",
                        "lx",
                        "ly",
                        "lz",
                        "lpitch",
                        "lyaw",
                        "saut",
                        "accroupi",
                    ]
                ).itertuples(index=False)
            ],
        )
    try:
        mesures = mesures_des_joueurs(chemin)
    except ErreurLecture as exc:
        journal.warning("mesures pros : %s", exc)
        mesures = []
    with base.transaction() as cx:
        cx.executemany(
            "INSERT INTO cs2_ref_mesures (empreinte, joueur, nom, contexte, valeur, n) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (empreinte, j, nom, json.dumps(ctx, sort_keys=True, ensure_ascii=False), v, n)
                for j, nom, ctx, v, n in mesures
            ],
        )
    return f"ajoutee ({len(obs)} observations, {len(mesures)} mesures de joueurs, {carte})"


def references_mecanique(base: Base, minimum: int = 5) -> int:
    """Médiane des pros par mesure et par contexte (arme, catégorie…) → cibles du débrief."""
    with base.transaction() as cx:
        lignes = cx.execute("SELECT nom, contexte, valeur FROM cs2_ref_mesures").fetchall()
    groupes: dict[tuple[str, str], list[float]] = {}
    for nom, contexte, valeur in lignes:
        groupes.setdefault((nom, contexte), []).append(float(valeur))
    references = [
        {
            "jeu": "cs2",
            "nom": nom,
            "contexte": json.loads(contexte),
            "patch": "",
            "valeur": float(np.median(v)),
            "n": len(v),
            "source": "joueurs des démos pros",
        }
        for (nom, contexte), v in groupes.items()
        if len(v) >= minimum
    ]
    base.enregistrer_references(references)
    return len(references)


def cles_stables(nouveaux: pd.DataFrame, anciens: pd.DataFrame) -> list[str]:
    """Un stuff garde sa clé (et donc les notes et révisions de Mathieu) quand le catalogue
    est recalculé : on reprend la clé de l'ancien stuff de même carte et même type arrivé à
    moins de RAYON_GROUPE ; sinon nouvelle clé."""
    import uuid

    cles, prises = [], set()
    for _, n in nouveaux.iterrows():
        cle = None
        if len(anciens):
            memes = anciens[
                (anciens["carte"] == n["carte"])
                & (anciens["type"] == n["type"])
                & anciens["cle"].notna()
                & ~anciens["cle"].isin(prises)
            ]
            if len(memes):
                d = np.hypot(memes["x"] - n["x"], memes["y"] - n["y"])
                if d.min() <= RAYON_GROUPE:
                    cle = str(memes.loc[d.idxmin(), "cle"])
        cle = cle or uuid.uuid4().hex[:10]
        prises.add(cle)
        cles.append(cle)
    return cles


def reconstruire_catalogue(base: Base) -> dict[str, int]:
    with base.transaction() as cx:
        obs = pd.read_sql_query("SELECT * FROM cs2_ref_observations", cx)
    lancers, positions = construire_catalogue(obs)
    with base.transaction() as cx:
        anciens = pd.read_sql_query("SELECT carte, type, x, y, cle FROM cs2_ref_lancers", cx)
    lancers["cle"] = cles_stables(lancers, anciens)
    horodatage = maintenant()
    with base.transaction() as cx:
        cx.execute("DELETE FROM cs2_ref_lancers")
        cx.execute("DELETE FROM cs2_ref_positions")
        for _, ref in lancers.iterrows():
            cx.execute(
                "INSERT INTO cs2_ref_lancers (carte, type, x, y, z, lx, ly, lz, lieu_arrivee, "
                "lieu_lancer, nb, nb_demos, lpitch, lyaw, part_saut, part_accroupi, cle, "
                "construit_le) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    *[
                        None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
                        for v in ref.tolist()
                    ],
                    horodatage,
                ),
            )
        for _, p in positions.iterrows():
            cx.execute(
                "INSERT INTO cs2_ref_positions (carte, camp, lieu, x, y, nb, part, construit_le) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (*[v.item() if hasattr(v, "item") else v for v in p.tolist()], horodatage),
            )
    return {
        "lancers": len(lancers),
        "positions": len(positions),
        "references_mecanique": references_mecanique(base),
    }


@dataclass
class Catalogue:
    lancers: pd.DataFrame = field(default_factory=pd.DataFrame)
    positions: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def vide(self) -> bool:
        return not len(self.lancers) and not len(self.positions)


def charger_catalogue(base: Base, carte: str) -> Catalogue:
    with base.transaction() as cx:
        lancers = pd.read_sql_query(
            "SELECT * FROM cs2_ref_lancers WHERE carte = ?", cx, params=(carte,)
        )
        positions = pd.read_sql_query(
            "SELECT * FROM cs2_ref_positions WHERE carte = ?", cx, params=(carte,)
        )
    return Catalogue(lancers, positions)


def resume_catalogue(base: Base) -> list[dict]:
    with base.transaction() as cx:
        lignes = cx.execute(
            "SELECT d.carte, COUNT(DISTINCT d.empreinte) AS demos, "
            "(SELECT COUNT(*) FROM cs2_ref_lancers l WHERE l.carte = d.carte) AS lancers, "
            "(SELECT COUNT(*) FROM cs2_ref_positions p WHERE p.carte = d.carte) AS positions "
            "FROM cs2_ref_demos d GROUP BY d.carte ORDER BY d.carte"
        ).fetchall()
    return [dict(lg) for lg in lignes]


# --- Analyse des parties de Mathieu --------------------------------------------------------


def _distance_segment(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """Distance du point p au segment [a, b], et seulement si sa projection tombe dedans."""
    ab = b - a
    longueur2 = float(ab @ ab)
    if longueur2 == 0:
        return float("inf")
    t = float((p - a) @ ab) / longueur2
    if t <= 0 or t >= 1:
        return float("inf")
    return float(np.linalg.norm(a + t * ab - p))


def lignes_coupees(d: DonneesMatch, pos: Positions, smoke: pd.Series) -> set[tuple[str, str]]:
    """Paires (adversaire, allié) dont la ligne de vue 2D traverse la smoke pendant sa durée."""
    centre = np.array([smoke["x"], smoke["y"]], dtype=float)
    coupees: set[tuple[str, str]] = set()
    joueurs = pos.joueurs()
    for t in range(int(smoke["tick"]), int(smoke["fin"]) + 1, PAS_LIGNE_TICKS):
        mon_equipe = pos.equipe(d.moi, t)
        etats = {sid: pos.etat(sid, t) for sid in joueurs}
        vivants = {sid: e for sid, e in etats.items() if e is not None and bool(e["vivant"])}
        allies = [s for s, e in vivants.items() if int(e["equipe"]) == mon_equipe]
        adversaires = [s for s, e in vivants.items() if int(e["equipe"]) != mon_equipe]
        for adv in adversaires:
            a = np.array([vivants[adv]["x"], vivants[adv]["y"]], dtype=float)
            for allie in allies:
                b = np.array([vivants[allie]["x"], vivants[allie]["y"]], dtype=float)
                if np.linalg.norm(a - b) > DISTANCE_MAX_LIGNE:
                    continue
                if _distance_segment(centre, a, b) <= RAYON_SMOKE:
                    coupees.add((adv, allie))
    return coupees


def _rattacher(g: pd.Series, refs: pd.DataFrame) -> tuple[pd.Series | None, float]:
    if not len(refs):
        return None, float("inf")
    d = np.hypot(refs["x"] - g["x"], refs["y"] - g["y"])
    i = d.idxmin()
    return refs.loc[i], float(d.loc[i])


def _nom_reference(ref: pd.Series) -> str:
    vers = ref["lieu_arrivee"] or "?"
    depuis = f" depuis {ref['lieu_lancer']}" if ref.get("lieu_lancer") else ""
    return f"{ref['type']} {vers}{depuis}"


def analyser_references(
    d: DonneesMatch, catalogue: Catalogue, pos: Positions | None = None
) -> ResultatAnalyse:
    pos = pos or Positions(d.ticks)
    r = ResultatAnalyse()
    if d.est_deathmatch():
        return r

    # Smokes : rattachement au catalogue et lignes de vue coupées.
    mes_smokes = d.grenades[(d.grenades["type"] == "smoke") & (d.grenades["lanceur"] == d.moi)]
    refs_smokes = (
        catalogue.lancers[catalogue.lancers["type"] == "smoke"]
        if len(catalogue.lancers)
        else pd.DataFrame()
    )
    reconnues, ecarts, coupant = 0, [], 0
    for _, s in mes_smokes.iterrows():
        t = int(s["tick"])
        paires = lignes_coupees(d, pos, s)
        coupant += bool(paires)
        texte = f"Smoke ({len(paires)} ligne(s) de vue coupée(s))"
        if len(refs_smokes):
            ref, dist = _rattacher(s, refs_smokes)
            stuff = {"stuff": ref.get("cle"), "ecart": round(dist, 1)} if ref is not None else {}
            if dist <= DISTANCE_RECONNUE:
                reconnues += 1
                ecarts.append(dist)
                texte = f"Smoke reconnue : {_nom_reference(ref)}, à {dist:.0f} u — " + texte
            elif dist <= DISTANCE_RATEE:
                ecarts.append(dist)
                texte = f"Smoke ratée de {dist:.0f} u : {_nom_reference(ref)} — " + texte
            else:
                texte = "Smoke hors référence — " + texte
        r.preuves.append(
            Preuve(
                D_SMOKE_RECONNUES.nom,
                t,
                texte,
                d.numero_round(t),
                {
                    "x": s["x"],
                    "y": s["y"],
                    "lignes": len(paires),
                    **(stuff if len(refs_smokes) else {}),
                },
            )
        )
    n = len(mes_smokes)
    if n:
        r.mesures.append(mesure(D_SMOKE_LIGNE, 100.0 * coupant / n, n=n))
        if len(refs_smokes):
            r.mesures.append(mesure(D_SMOKE_RECONNUES, 100.0 * reconnues / n, n=n))
            if ecarts:
                r.mesures.append(mesure(D_SMOKE_ECART, float(np.median(ecarts)), n=len(ecarts)))

    # Molotovs : rattachement seulement.
    mes_molos = d.grenades[(d.grenades["type"] == "molotov") & (d.grenades["lanceur"] == d.moi)]
    refs_molos = (
        catalogue.lancers[catalogue.lancers["type"] == "molotov"]
        if len(catalogue.lancers)
        else pd.DataFrame()
    )
    if len(mes_molos) and len(refs_molos):
        ok = sum(_rattacher(m, refs_molos)[1] <= DISTANCE_RECONNUE for _, m in mes_molos.iterrows())
        r.mesures.append(mesure(D_MOLO_RECONNUES, 100.0 * ok / len(mes_molos), n=len(mes_molos)))

    # Positions installées comparées aux pros (CS-POS-04).
    if len(catalogue.positions) and len(d.lieux):
        tenues, courantes = 0, 0
        for _, rnd in d.rounds.iterrows():
            t = int(rnd["debut"]) + DELAI_INSTALLATION_TICKS
            if t > int(rnd["fin"]):
                continue
            ligne = d.lieux[(d.lieux["steamid"] == d.moi) & (d.lieux["tick"] == t)]
            etat = pos.etat(d.moi, t)
            if not len(ligne) or etat is None or not bool(etat["vivant"]):
                continue
            lieu = str(ligne["lieu"].iloc[0])
            camp = CAMPS.get(int(etat["equipe"]))
            refs = catalogue.positions[(catalogue.positions["camp"] == camp)]
            part = float(refs.loc[refs["lieu"] == lieu, "part"].sum()) if len(refs) else 0.0
            tenues += 1
            courante = part >= PART_POSITION_COURANTE
            courantes += courante
            habituels = refs.nlargest(3, "part")["lieu"].tolist() if len(refs) else []
            texte = (
                f"Round {int(rnd['numero'])} ({camp}) : {lieu or 'lieu inconnu'}, tenu par "
                f"les pros dans {100 * part:.0f} % des rounds"
            )
            if not courante and habituels:
                texte += f" (positions pros les plus courantes : {', '.join(habituels)})"
            r.preuves.append(
                Preuve(
                    D_POSITIONS_PRO.nom,
                    t,
                    texte,
                    int(rnd["numero"]),
                    {"lieu": lieu, "camp": camp, "part": part},
                )
            )
        if tenues:
            r.mesures.append(mesure(D_POSITIONS_PRO, 100.0 * courantes / tenues, n=tenues))
    return r


def catalogue_pour(cfg_chemin_base: Path, carte: str) -> Catalogue:
    """Charge le catalogue depuis la base du service (vide si absent)."""
    if not Path(cfg_chemin_base).exists():
        return Catalogue()
    base = Base(cfg_chemin_base)
    try:
        return charger_catalogue(base, carte)
    finally:
        base.fermer()
