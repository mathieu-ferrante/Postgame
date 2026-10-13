"""Données du replay 2D (CS-RPL-01) : positions et évènements, round par round.

Construit à partir de `DonneesMatch` (la même extraction que les analyses), sous-échantillonné
à 16 images par seconde, puis mis en cache dans data/replays/<partie>.json.gz : la démo
n'est relue qu'une fois.

Format compact (coordonnées arrondies à l'unité, angles au degré) :
meta   : carte, joueurs [{id, steamid, nom, moi}], rounds [{numero, debut, fin, gagnant}],
         fond (grille des zones parcourues, pour dessiner la carte sans image de radar)
round  : ticks [t…], joueurs {id: {equipe, x[], y[], yaw[], vivant[], arme[]}},
         tirs [[tick, id]], morts [[tick, tueur, victime, arme, headshot]],
         grenades [[type, x, y, debut, fin, lanceur]], bombe [[tick, evenement, x, y]]
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from postgame.games.cs2.donnees import TICKS_PAR_SECONDE, DonneesMatch, Positions

PAS_TICKS = 4  # 64 / 4 = 16 images par seconde
PAS_FOND_TICKS = 32
CELLULE_FOND = 64.0  # u


def _identifiants(d: DonneesMatch) -> dict[str, int]:
    ordre = d.ticks.drop_duplicates("steamid").sort_values(["equipe", "nom"])["steamid"]
    return {sid: i for i, sid in enumerate(ordre)}


def fond_de_carte(d: DonneesMatch) -> dict[str, Any] | None:
    """Grille des cellules où au moins un joueur vivant est passé : silhouette de la carte."""
    echantillon = d.ticks[(d.ticks["tick"] % PAS_FOND_TICKS == 0) & d.ticks["vivant"]]
    if not len(echantillon):
        return None
    xmin, ymin = float(echantillon["x"].min()), float(echantillon["y"].min())
    i = ((echantillon["x"] - xmin) // CELLULE_FOND).astype(int)
    j = ((echantillon["y"] - ymin) // CELLULE_FOND).astype(int)
    cellules = sorted({(int(a), int(b)) for a, b in zip(i, j, strict=True)})
    # Hauteur du sol par cellule (médiane des z des pieds) : étages de la carte.
    hauteurs = echantillon.assign(i=i, j=j).groupby(["i", "j"])["z"].median().round()
    return {
        "xmin": round(xmin),
        "ymin": round(ymin),
        "cellule": CELLULE_FOND,
        "largeur": int(i.max()) + 1,
        "hauteur": int(j.max()) + 1,
        "cellules": [[a, b] for a, b in cellules],
        "hauteurs": [int(hauteurs[(a, b)]) for a, b in cellules],
    }


def construire_meta(d: DonneesMatch) -> dict[str, Any]:
    ids = _identifiants(d)
    noms = d.ticks.drop_duplicates("steamid").set_index("steamid")["nom"]
    rounds = (
        d.rounds
        if len(d.rounds)
        else pd.DataFrame(
            [
                {
                    "numero": 1,
                    "debut": int(d.ticks["tick"].min()),
                    "fin": int(d.ticks["tick"].max()),
                    "gagnant": None,
                }
            ]
        )
    )
    fin_max = int(d.ticks["tick"].max()) if len(d.ticks) else 0
    return {
        "carte": d.carte,
        "tickrate": TICKS_PAR_SECONDE,
        "joueurs": [
            {"id": i, "steamid": sid, "nom": str(noms.get(sid, sid)), "moi": sid == d.moi}
            for sid, i in ids.items()
        ],
        "rounds": [
            {
                "numero": int(r["numero"]),
                "debut": int(r["debut"]),
                "fin": min(int(r["fin"]), fin_max),
                "gagnant": None
                if r.get("gagnant") is None or pd.isna(r.get("gagnant"))
                else int(r["gagnant"]),
            }
            for _, r in rounds.iterrows()
        ],
        "fond": fond_de_carte(d),
    }


def construire_round(
    d: DonneesMatch, debut: int, fin: int, pos: Positions | None = None
) -> dict[str, Any]:
    ids = _identifiants(d)
    pos = pos or Positions(d.ticks)
    # Quelques secondes avant le début du round (fin du freeze) pour voir l'installation.
    depart = max(int(d.ticks["tick"].min()), debut - 5 * TICKS_PAR_SECONDE)
    lot = d.ticks[
        (d.ticks["tick"] >= depart)
        & (d.ticks["tick"] <= fin)
        & ((d.ticks["tick"] - depart) % PAS_TICKS == 0)
    ]
    ticks = sorted(int(t) for t in lot["tick"].unique())
    joueurs: dict[str, Any] = {}
    for sid, g in lot.groupby("steamid"):
        g = g.set_index("tick").reindex(ticks)
        joueurs[str(ids[sid])] = {
            "equipe": int(g["equipe"].dropna().iloc[-1]) if g["equipe"].notna().any() else 0,
            "x": g["x"].round().fillna(0).astype(int).tolist(),
            "y": g["y"].round().fillna(0).astype(int).tolist(),
            "yaw": g["yaw"].round().fillna(0).astype(int).tolist(),
            "z": g["z"].round().fillna(0).astype(int).tolist(),
            "pitch": g["pitch"].round().fillna(0).astype(int).tolist(),
            "vivant": g["vivant"].fillna(False).astype(bool).astype(int).tolist(),
            "arme": g["arme"].fillna("").astype(str).tolist(),
        }

    def dans(df: pd.DataFrame) -> pd.DataFrame:
        return df[(df["tick"] >= depart) & (df["tick"] <= fin)] if len(df) else df

    tirs = [[int(t.tick), ids[t.steamid]] for t in dans(d.tirs).itertuples() if t.steamid in ids]
    morts = [
        [
            int(m.tick),
            ids.get(m.attaquant, -1),
            ids.get(m.victime, -1),
            str(m.arme),
            bool(m.headshot),
        ]
        for m in dans(d.morts).itertuples()
    ]
    grenades = [
        [
            str(g.type),
            round(float(g.x)),
            round(float(g.y)),
            int(g.tick),
            int(g.fin),
            ids.get(g.lanceur, -1),
        ]
        for g in d.grenades.itertuples()
        if int(g.fin) >= depart and int(g.tick) <= fin and not np.isnan(g.x)
    ]
    bombe = []
    for b in dans(d.bombe).itertuples():
        etat = pos.etat(b.steamid, int(b.tick)) if b.steamid else None
        x, y = (round(float(etat["x"])), round(float(etat["y"]))) if etat is not None else (0, 0)
        bombe.append([int(b.tick), str(b.evenement), x, y])
    return {
        "debut": debut,
        "fin": fin,
        "depart": depart,
        "ticks": ticks,
        "joueurs": joueurs,
        "tirs": tirs,
        "morts": morts,
        "grenades": grenades,
        "bombe": bombe,
    }


FORMAT = 2  # 2 : altitude et inclinaison du regard (replay 3D)


def construire_replay(d: DonneesMatch) -> dict[str, Any]:
    meta = construire_meta(d)
    meta["format"] = FORMAT
    pos = Positions(d.ticks)
    rounds = {
        str(r["numero"]): construire_round(d, r["debut"], r["fin"], pos) for r in meta["rounds"]
    }
    return {"meta": meta, "rounds": rounds}


def chemin_cache(dossier_donnees: Path, partie_id: int) -> Path:
    return dossier_donnees / "replays" / f"{partie_id}.json.gz"


def ecrire_cache(chemin: Path, replay: dict[str, Any]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(chemin, "wt", encoding="utf-8") as f:
        json.dump(replay, f, ensure_ascii=False, separators=(",", ":"))


def lire_cache(chemin: Path) -> dict[str, Any] | None:
    if not chemin.exists():
        return None
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        donnees = json.load(f)
    # Cache d'un ancien format : on le reconstruit.
    return donnees if donnees.get("meta", {}).get("format") == FORMAT else None
