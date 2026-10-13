"""Ce qui fait gagner ou perdre des places (TFT-02) et comparaison au haut classement (TFT-03).

Pour chaque élément joué (trait actif, unité, objet, augment), on calcule la place moyenne
quand il est présent et son écart à la place moyenne globale. Tout est calculé **par set et
par patch** : une unité forte au patch 15.19 peut être affaiblie au 15.20.

La référence de haut classement se construit à partir des parties récentes des joueurs
Challenger (API Riot uniquement, aucun site tiers) — voir games/riot/meta.py.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from postgame.games.tft import composition, patch_tft

MIN_PARTIES = 3


def observations(match: dict[str, Any], puuids: set[str] | None = None) -> list[dict[str, Any]]:
    """Une observation par joueur (ou seulement ceux de `puuids`) : place et éléments joués."""
    info = match["info"]
    obs = []
    for j in info["participants"]:
        if puuids is not None and j["puuid"] not in puuids:
            continue
        compo = composition(j)
        obs.append(
            {
                "set": info.get("tft_set_number"),
                "patch": patch_tft(info.get("game_version")),
                "placement": int(j["placement"]),
                "elements": (
                    [("trait", f"{t['nom']} {t['unites']}") for t in compo["traits"]]
                    + [("unite", u["nom"]) for u in compo["unites"]]
                    + [("objet", o) for u in compo["unites"] for o in u["objets"]]
                    + [("augment", a) for a in compo["augments"]]
                ),
            }
        )
    return obs


def statistiques(obs: list[dict[str, Any]], minimum: int = MIN_PARTIES) -> dict[str, Any]:
    """Par (set, patch) : place moyenne globale et, pour chaque élément, place moyenne,
    nombre de parties et écart à la moyenne (négatif = l'élément fait gagner des places)."""
    groupes: dict[tuple[Any, str], list[dict[str, Any]]] = defaultdict(list)
    for o in obs:
        groupes[(o["set"], o["patch"])].append(o)
    resultat = {}
    for (set_, patch), lot in groupes.items():
        moyenne = statistics.fmean(o["placement"] for o in lot)
        par_element: dict[tuple[str, str], list[int]] = defaultdict(list)
        for o in lot:
            for element in set(o["elements"]):
                par_element[element].append(o["placement"])
        elements = [
            {
                "type": t,
                "nom": n,
                "parties": len(p),
                "place_moyenne": round(statistics.fmean(p), 2),
                "ecart": round(statistics.fmean(p) - moyenne, 2),
                "top4": round(100 * sum(x <= 4 for x in p) / len(p), 1),
            }
            for (t, n), p in par_element.items()
            if len(p) >= minimum
        ]
        elements.sort(key=lambda e: e["ecart"])
        resultat[f"{set_}|{patch}"] = {
            "set": set_,
            "patch": patch,
            "parties": len(lot),
            "place_moyenne": round(moyenne, 2),
            "elements": elements,
        }
    return resultat


def comparer(miennes: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    """Pour chaque (set, patch) : mes éléments face au haut classement du même patch."""
    sortie = {}
    for cle, moi in miennes.items():
        ref = reference.get(cle)
        index = {(e["type"], e["nom"]): e for e in (ref["elements"] if ref else [])}
        lignes = []
        for e in moi["elements"]:
            r = index.get((e["type"], e["nom"]))
            lignes.append(
                {
                    **e,
                    "ref_place_moyenne": r["place_moyenne"] if r else None,
                    "ref_parties": r["parties"] if r else 0,
                }
            )
        # Éléments forts en haut classement que Mathieu ne joue jamais ou presque.
        joues = {(e["type"], e["nom"]) for e in moi["elements"]}
        a_essayer = [
            e
            for e in (ref["elements"] if ref else [])
            if (e["type"], e["nom"]) not in joues and e["ecart"] < -0.5
        ][:10]
        sortie[cle] = {
            **moi,
            "reference": {"parties": ref["parties"]} if ref else None,
            "elements": lignes,
            "a_essayer": a_essayer,
        }
    return sortie
