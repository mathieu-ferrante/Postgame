"""Positionnement CS2 (lot L2 : CS-POS-01, 02, 03).

- Cartes de chaleur : chaque kill et chaque mort de Mathieu est enregistré comme preuve
  avec sa position et son camp ; l'interface agrège ces points sur plusieurs parties.
- Morts isolées : distance au coéquipier vivant le plus proche au moment de la mort.
- Trades : morts de Mathieu vengées ou non, vengeances réussies par Mathieu, occasions
  manquées.

Les mesures d'équipe n'ont pas de sens en deathmatch : elles n'y sont pas calculées.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from postgame.games.cs2.donnees import TICKS_PAR_SECONDE, DonneesMatch, Positions
from postgame.mesures import Preuve, ResultatAnalyse, definir, mesure

FENETRE_TRADE_TICKS = 5 * TICKS_PAR_SECONDE
DISTANCE_TRADABLE = 800.0  # u : un coéquipier plus proche pouvait venger la mort
DISTANCE_ISOLEE = 1000.0  # u : au-delà, la mort est isolée
CAMPS = {2: "T", 3: "CT"}

D_KILLS_POS = definir(
    "cs2.position.kill", 1, "", "Position de chaque kill (carte de chaleur).", sens="neutre"
)
D_MORTS_POS = definir(
    "cs2.position.mort", 1, "", "Position de chaque mort (carte de chaleur).", sens="neutre"
)
D_DIST_COEQ = definir(
    "cs2.position.distance_coequipier_a_la_mort",
    1,
    "u",
    "Distance médiane au coéquipier vivant le plus proche au moment de mourir.",
    sens="bas",
)
D_ISOLEES = definir(
    "cs2.position.part_morts_isolees",
    1,
    "%",
    "Part des morts sans coéquipier vivant à moins de 1000 u.",
    sens="bas",
)
D_TRADEES = definir(
    "cs2.trades.part_morts_tradees",
    1,
    "%",
    "Part des morts de Mathieu dont le tueur est abattu par un coéquipier dans les 5 s.",
)
D_NON_TRADEES = definir(
    "cs2.trades.part_tradables_non_tradees",
    1,
    "%",
    "Part des morts tradables (coéquipier à moins de 800 u) qui ne sont pas vengées.",
    sens="bas",
)
D_REUSSIS = definir(
    "cs2.trades.reussis", 1, "trades", "Coéquipiers vengés par Mathieu dans les 5 s."
)
D_DELAI = definir(
    "cs2.trades.delai_median", 1, "ms", "Délai médian des trades réussis par Mathieu.", sens="bas"
)
D_MANQUES = definir(
    "cs2.trades.occasions_manquees",
    1,
    "occasions",
    "Coéquipiers morts à moins de 800 u de Mathieu (vivant) sans être vengés.",
    sens="bas",
)


def _pct(n: float, total: float) -> float | None:
    return 100.0 * n / total if total else None


def chaleur(d: DonneesMatch, pos: Positions) -> ResultatAnalyse:
    r = ResultatAnalyse()
    for _, m in d.morts.iterrows():
        t = int(m["tick"])
        for role, sid, definition in (
            ("kill", m["attaquant"], D_KILLS_POS),
            ("mort", m["victime"], D_MORTS_POS),
        ):
            if sid != d.moi or (role == "kill" and m["victime"] == d.moi):
                continue
            etat = pos.etat(d.moi, t)
            if etat is None:
                continue
            camp = CAMPS.get(int(etat["equipe"]), "?")
            r.preuves.append(
                Preuve(
                    definition.nom,
                    t,
                    f"{role.capitalize()} ({camp}) avec {m['arme']}",
                    d.numero_round(t),
                    {
                        "x": round(float(etat["x"]), 1),
                        "y": round(float(etat["y"]), 1),
                        "z": round(float(etat["z"]), 1),
                        "camp": camp,
                        "carte": d.carte,
                        "arme": m["arme"],
                    },
                )
            )
    return r


def _coequipiers_vivants(
    d: DonneesMatch, pos: Positions, steamid: str, tick: int
) -> list[tuple[str, str, float]]:
    """(steamid, nom, distance) des coéquipiers vivants de `steamid` au tick donné."""
    moi = pos.etat(steamid, tick)
    if moi is None:
        return []
    resultat = []
    for sid in pos.joueurs():
        if sid == steamid:
            continue
        e = pos.etat(sid, tick)
        if e is None or not bool(e["vivant"]) or int(e["equipe"]) != int(moi["equipe"]):
            continue
        dist = float(np.hypot(e["x"] - moi["x"], e["y"] - moi["y"]))
        resultat.append((sid, str(e["nom"]), dist))
    return sorted(resultat, key=lambda c: c[2])


def _venge(d: DonneesMatch, pos: Positions, tueur: str, tick: int, equipe: int) -> pd.Series | None:
    """Mort du tueur, des mains d'un joueur de `equipe`, dans les 5 s."""
    suite = d.morts[
        (d.morts["victime"] == tueur)
        & (d.morts["tick"] > tick)
        & (d.morts["tick"] <= tick + FENETRE_TRADE_TICKS)
    ]
    for _, m in suite.iterrows():
        if pos.equipe(m["attaquant"], int(m["tick"])) == equipe:
            return m
    return None


def isolement_et_trades(d: DonneesMatch, pos: Positions) -> ResultatAnalyse:
    r = ResultatAnalyse()
    if d.est_deathmatch():
        return r

    # Morts de Mathieu : isolement, vengeance.
    distances, isolees, tradees, tradables, non_tradees = [], 0, 0, 0, 0
    mes_morts = d.morts[(d.morts["victime"] == d.moi) & (d.morts["attaquant"] != d.moi)]
    for _, m in mes_morts.iterrows():
        t = int(m["tick"])
        rnd = d.numero_round(t)
        avant = max(0, t - 1)
        mon_equipe = pos.equipe(d.moi, avant)
        coeq = _coequipiers_vivants(d, pos, d.moi, avant)
        plus_proche = coeq[0][2] if coeq else None
        if plus_proche is not None:
            distances.append(plus_proche)
        if plus_proche is None or plus_proche > DISTANCE_ISOLEE:
            isolees += 1
            loin = f"{plus_proche:.0f} u de {coeq[0][1]}" if coeq else "aucun coéquipier vivant"
            r.preuves.append(
                Preuve(D_ISOLEES.nom, t, f"Mort isolée ({loin})", rnd, {"distance": plus_proche})
            )
        vengeance = _venge(d, pos, m["attaquant"], t, mon_equipe)
        proches = [c for c in coeq if c[2] <= DISTANCE_TRADABLE]
        if vengeance is not None:
            tradees += 1
        if proches:
            tradables += 1
            if vengeance is None:
                non_tradees += 1
                noms = ", ".join(f"{c[1]} ({c[2]:.0f} u)" for c in proches)
                r.preuves.append(
                    Preuve(
                        D_NON_TRADEES.nom,
                        t,
                        f"Mort tradable non vengée : {noms} à proximité",
                        rnd,
                        {"coequipiers": [c[0] for c in proches]},
                    )
                )
    n = len(mes_morts)
    if n:
        r.mesures.append(mesure(D_TRADEES, _pct(tradees, n), n=n))
        r.mesures.append(mesure(D_ISOLEES, _pct(isolees, n), n=n))
    if distances:
        r.mesures.append(mesure(D_DIST_COEQ, float(np.median(distances)), n=len(distances)))
    if tradables:
        r.mesures.append(mesure(D_NON_TRADEES, _pct(non_tradees, tradables), n=tradables))

    # Morts des coéquipiers : trades réussis ou manqués par Mathieu.
    reussis, delais, manques = 0, [], 0
    for _, m in d.morts.iterrows():
        t = int(m["tick"])
        victime, tueur = m["victime"], m["attaquant"]
        avant = max(0, t - 1)
        mon_equipe = pos.equipe(d.moi, avant)
        if victime == d.moi or pos.equipe(victime, avant) != mon_equipe or not tueur:
            continue
        if pos.equipe(tueur, avant) == mon_equipe:
            continue  # tir allié
        moi = pos.etat(d.moi, avant)
        if moi is None or not bool(moi["vivant"]):
            continue
        vengeance = _venge(d, pos, tueur, t, mon_equipe)
        if vengeance is not None and vengeance["attaquant"] == d.moi:
            reussis += 1
            delai = (int(vengeance["tick"]) - t) * 1000 / TICKS_PAR_SECONDE
            delais.append(delai)
            r.preuves.append(
                Preuve(
                    D_REUSSIS.nom,
                    t,
                    f"Trade réussi en {delai:.0f} ms",
                    d.numero_round(t),
                    {"delai_ms": delai},
                )
            )
            continue
        e_victime = pos.etat(victime, avant)
        if e_victime is None:
            continue
        distance = float(np.hypot(e_victime["x"] - moi["x"], e_victime["y"] - moi["y"]))
        if distance <= DISTANCE_TRADABLE and vengeance is None:
            manques += 1
            r.preuves.append(
                Preuve(
                    D_MANQUES.nom,
                    t,
                    f"{e_victime['nom']} meurt à {distance:.0f} u de Mathieu, sans être vengé",
                    d.numero_round(t),
                    {"distance": distance, "victime": victime},
                )
            )
    r.mesures.append(mesure(D_REUSSIS, reussis))
    r.mesures.append(mesure(D_MANQUES, manques))
    if delais:
        r.mesures.append(mesure(D_DELAI, float(np.median(delais)), n=len(delais)))
    return r


def analyser_positionnement(d: DonneesMatch, pos: Positions | None = None) -> ResultatAnalyse:
    pos = pos or Positions(d.ticks)
    r = ResultatAnalyse()
    r.etendre(chaleur(d, pos))
    r.etendre(isolement_et_trades(d, pos))
    return r
