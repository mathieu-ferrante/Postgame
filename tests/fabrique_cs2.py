"""Fabrique de matchs CS2 synthétiques pour tester les analyseurs.

DONNÉES DE SUBSTITUTION : scénarios construits à la main, dont le résultat attendu se
calcule sur papier. Ils vérifient la logique des mesures, pas la lecture des vraies démos.

Usage :
    s = Scenario(nb_ticks=2000)
    s.joueur(MOI, equipe=2)
    s.joueur(ADV, equipe=3, x=1000)
    s.regler(MOI, 100, 110, vx=200)       # du tick 100 au tick 110 inclus
    s.tir(MOI, 105, "ak47")
    d = s.donnees()
"""

from __future__ import annotations

import pandas as pd

from postgame.games.cs2.donnees import COLONNES_TICKS, DonneesMatch, construire_rounds

MOI = "76561198000000001"
ADV = "76561198000000002"
ADV2 = "76561198000000003"

DEFAUT = {
    "x": 0.0,
    "y": 0.0,
    "z": 0.0,
    "vx": 0.0,
    "vy": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
    "vivant": True,
    "accroupi": False,
    "arme": "ak47",
    "vu_par_moi": False,
    "punch_pitch": 0.0,
    "punch_yaw": 0.0,
}


class Scenario:
    def __init__(self, nb_ticks: int = 2000):
        self.nb_ticks = nb_ticks
        self._tables: dict[str, pd.DataFrame] = {}
        self.tirs: list[dict] = []
        self.degats: list[dict] = []
        self.morts: list[dict] = []
        self.debuts_rounds: list[int] = [0]
        self.fins_rounds: list[int] = []

    def joueur(self, steamid: str, equipe: int = 2, nom: str | None = None, **etat) -> None:
        valeurs = {**DEFAUT, **etat}
        df = pd.DataFrame({"tick": range(self.nb_ticks)})
        df["steamid"] = steamid
        df["nom"] = nom or f"joueur_{steamid[-2:]}"
        df["equipe"] = equipe
        for cle, valeur in valeurs.items():
            df[cle] = valeur
        self._tables[steamid] = df

    def regler(self, steamid: str, debut: int, fin: int, **etat) -> None:
        df = self._tables[steamid]
        masque = (df["tick"] >= debut) & (df["tick"] <= fin)
        for cle, valeur in etat.items():
            df.loc[masque, cle] = valeur

    def tir(self, steamid: str, tick: int, arme: str = "ak47") -> None:
        self.tirs.append({"tick": tick, "steamid": steamid, "arme": arme})

    def touche(
        self,
        attaquant: str,
        victime: str,
        tick: int,
        arme: str = "ak47",
        zone: str = "torse",
        degats: float = 27.0,
    ) -> None:
        self.degats.append(
            {
                "tick": tick,
                "attaquant": attaquant,
                "victime": victime,
                "arme": arme,
                "degats": degats,
                "zone": zone,
            }
        )

    def mort(
        self, attaquant: str, victime: str, tick: int, arme: str = "ak47", headshot: bool = False
    ) -> None:
        self.morts.append(
            {
                "tick": tick,
                "attaquant": attaquant,
                "victime": victime,
                "arme": arme,
                "headshot": headshot,
            }
        )

    def donnees(self, moi: str = MOI) -> DonneesMatch:
        ticks = pd.concat(self._tables.values(), ignore_index=True)[COLONNES_TICKS]
        return DonneesMatch(
            moi=moi,
            ticks=ticks.sort_values(["tick", "steamid"]).reset_index(drop=True),
            tirs=pd.DataFrame(self.tirs, columns=["tick", "steamid", "arme"]),
            degats=pd.DataFrame(
                self.degats, columns=["tick", "attaquant", "victime", "arme", "degats", "zone"]
            ),
            morts=pd.DataFrame(
                self.morts, columns=["tick", "attaquant", "victime", "arme", "headshot"]
            ),
            rounds=construire_rounds(self.debuts_rounds, self.fins_rounds),
            carte="de_test",
        )
