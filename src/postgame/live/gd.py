"""Second écran Geometry Dash (GD-08) : la séance en cours, lue au fil du journal du mod.

Le mod écrit et vide son journal ligne par ligne. Le service lit seulement les lignes
ajoutées depuis la dernière lecture (quelques octets par seconde) : aucun calcul lourd
pendant le jeu, aucune interaction avec le jeu. L'analyse complète reste faite après la
séance (PERF-01).

Affiché : niveau, essai en cours et sa position, meilleur %, moyenne des 10 derniers
essais, zones de mort de la séance, et — tiré des séances précédentes sur ce niveau —
les passages les plus irréguliers et les zones où Mathieu meurt le plus.
"""

from __future__ import annotations

import json
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

from postgame.db import Base

FRAICHEUR_S = 60.0  # un journal non modifié depuis 1 min n'est plus une séance en cours
TRANCHE = 10  # zones de mort par tranche de 10 %


class SeanceEnDirect:
    """État de la séance, mis à jour ligne par ligne."""

    def __init__(self) -> None:
        self.niveau: str | None = None
        self.niveau_id: int | None = None
        self.plateforme = False
        self.essai = 0
        self.mode = "normal"
        self.x = 0.0
        self.morts_pct: list[float] = []  # essais normaux
        self.essais_practice = 0
        self.complete = False
        self.longueurs: list[float] = []
        self.finie = False
        self.t = 0.0

    def lire(self, ligne: str) -> None:
        try:
            ev = json.loads(ligne)
        except json.JSONDecodeError:
            return
        type_ = ev.get("type")
        self.t = float(ev.get("t", self.t))
        if type_ == "session":
            niveau = ev.get("niveau", {})
            self.niveau = str(niveau.get("nom", "inconnu"))
            self.niveau_id = int(niveau.get("id", 0))
            self.plateforme = bool(ev.get("plateforme", False))
        elif type_ == "essai":
            self.essai = int(ev.get("n", self.essai + 1))
            self.mode = str(ev.get("mode", "normal"))
            self.x = float(ev.get("x", 0.0))
            if self.mode == "practice":
                self.essais_practice += 1
        elif type_ in ("pos", "input"):
            self.x = max(self.x, float(ev.get("x", self.x)))
        elif type_ == "mort":
            pct = float(ev.get("pct", 0.0))
            if pct > 1 and ev.get("x"):
                self.longueurs.append(float(ev["x"]) / pct * 100)
            if self.mode == "normal":
                self.morts_pct.append(pct)
        elif type_ == "fin":
            if self.mode == "normal":
                self.complete = True
                self.morts_pct.append(100.0)
        elif type_ == "fin_session":
            self.finie = True

    def pct_courant(self) -> float | None:
        if not self.longueurs:
            return None
        longueur = sorted(self.longueurs)[len(self.longueurs) // 2]
        return round(min(100.0, 100 * self.x / longueur), 1)

    def resume(self) -> dict[str, Any]:
        recents = self.morts_pct[-10:]
        zones = Counter(
            min(int(p // TRANCHE) * TRANCHE, 100 - TRANCHE) for p in self.morts_pct if p < 100
        )
        return {
            "actif": not self.finie and self.niveau is not None,
            "niveau": self.niveau,
            "plateforme": self.plateforme,
            "essai": self.essai,
            "mode": self.mode,
            "pct": self.pct_courant(),
            "essais_normaux": len(self.morts_pct),
            "essais_practice": self.essais_practice,
            "meilleur": max(self.morts_pct) if self.morts_pct else None,
            "moyenne_10": round(sum(recents) / len(recents), 1) if recents else None,
            "complete": self.complete,
            "zones_mort": [
                {"de": z, "a": z + TRANCHE, "morts": n} for z, n in zones.most_common(3)
            ],
            "duree_s": round(self.t / 1000),
        }


def historique(base: Base, niveau: str | None) -> dict[str, Any]:
    """Ce que les séances précédentes sur ce niveau ont appris (analyses déjà faites)."""
    if not niveau:
        return {}
    instables = [
        p
        for p in base.preuves_toutes_parties("gd.regularite.ecart_type_median", jeu="gd")
        if p["carte"] == niveau and p["donnees"].get("pct") is not None
    ]
    if instables:
        derniere = instables[-1]["partie_id"]
        instables = [p for p in instables if p["partie_id"] == derniere]
    morts = [
        p["donnees"]["pct"]
        for p in base.preuves_toutes_parties("gd.mort", jeu="gd")
        if p["carte"] == niveau and p["donnees"].get("mode") == "normal"
    ]
    zones = Counter(min(int(p // TRANCHE) * TRANCHE, 100 - TRANCHE) for p in morts if p < 100)
    return {
        "seances": len({p["partie_id"] for p in instables}) if instables else None,
        "passages_irreguliers": [
            {
                "pct": p["donnees"]["pct"],
                "ecart_type": p["donnees"].get("ecart_type"),
                "sens": "trop tôt" if (p["donnees"].get("decalage") or 0) < 0 else "trop tard",
                "decalage": abs(p["donnees"].get("decalage") or 0),
            }
            for p in sorted(instables, key=lambda p: p["donnees"]["pct"])
        ],
        "zones_mort": [{"de": z, "a": z + TRANCHE, "morts": n} for z, n in zones.most_common(3)],
        "morts_total": len(morts),
    }


class SuiviGD:
    """Suit le journal le plus récent des dossiers de séances GD."""

    def __init__(self, base: Base, dossiers: list[Path], intervalle: float = 0.5) -> None:
        self.base, self.dossiers, self.intervalle = base, dossiers, intervalle
        self.resume: dict[str, Any] = {"actif": False}
        self._fichier: Path | None = None
        self._position = 0
        self._reste = ""
        self._seance = SeanceEnDirect()
        self._historique: dict[str, Any] = {}
        self._arret = threading.Event()
        self._fil: threading.Thread | None = None

    def _journal_en_cours(self) -> Path | None:
        recents = []
        for d in self.dossiers:
            if d.is_dir():
                for f in d.glob("*.gdsession"):
                    try:
                        recents.append((f.stat().st_mtime, f))
                    except OSError:
                        continue
        if not recents:
            return None
        mtime, f = max(recents)
        return f if time.time() - mtime <= FRAICHEUR_S else None

    def passe(self) -> None:
        f = self._journal_en_cours()
        if f is None:
            self.resume = {"actif": False}
            return
        if f != self._fichier:
            self._fichier, self._position, self._reste = f, 0, ""
            self._seance, self._historique = SeanceEnDirect(), {}
        try:
            with f.open("rb") as flux:
                flux.seek(self._position)
                nouveau = flux.read()
        except OSError:
            return
        self._position += len(nouveau)
        texte = self._reste + nouveau.decode("utf-8", errors="replace")
        *lignes, self._reste = texte.split("\n")  # la dernière ligne peut être incomplète
        niveau_avant = self._seance.niveau
        for ligne in lignes:
            if ligne.strip():
                self._seance.lire(ligne)
        if self._seance.niveau != niveau_avant:
            self._historique = historique(self.base, self._seance.niveau)
        self.resume = {**self._seance.resume(), "historique": self._historique}

    def demarrer(self) -> None:
        if self._fil and self._fil.is_alive():
            return
        self._arret.clear()
        self._fil = threading.Thread(target=self._boucle, name="live-gd", daemon=True)
        self._fil.start()

    def arreter(self) -> None:
        self._arret.set()

    def _boucle(self) -> None:
        while not self._arret.is_set():
            self.passe()
            self._arret.wait(self.intervalle if self.resume.get("actif") else 5.0)
