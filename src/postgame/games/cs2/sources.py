"""Récupération automatique des parties CS2 (AUTO-01) : FACEIT et codes de partage Steam.

FACEIT (CS-SRC-03) — API officielle :
- Data API v4 (clé « serveur » créée librement sur developers.faceit.com) : historique des
  matchs du joueur, détails du match avec l'adresse (privée) de la démo ;
- Downloads API (jeton accordé par FACEIT sur demande, ~30 jours) : transforme cette adresse
  en lien de téléchargement signé. La démo arrive compressée (.gz ou .zst) : on la
  décompresse puis on l'importe comme toute démo.

Steam (Premier / compétitif) — codes de partage :
- l'API Web Steam (`ICSGOPlayers_730/GetNextMatchSharingCode`) donne, avec la clé API de
  Mathieu et son « code d'authentification de l'historique des matchs », le code de partage
  de chaque nouvelle partie classée ;
- le code se décode en identifiants de match (matchid, reservationid, port TV). Obtenir
  l'adresse de la démo demande ensuite le coordinateur de jeu de CS2 via le client Steam
  connecté : non fait à ce jour (voir A_VALIDER.md). En attendant, Postgame sait quelles
  parties n'ont pas de démo et le rappelle.
"""

from __future__ import annotations

import gzip
import json
import logging
import shutil
from pathlib import Path
from typing import Any

import httpx

from postgame.config import Config
from postgame.db import Base
from postgame.importation import importer

journal = logging.getLogger(__name__)

URL_FACEIT = "https://open.faceit.com/data/v4"
URL_TELECHARGEMENT = "https://open.faceit.com/download/v2/demos/download"
URL_STEAM_CODES = "https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1"


class ErreurSource(Exception):
    pass


# --- Codes de partage Steam --------------------------------------------------------------

ALPHABET = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789"


def decoder_code(code: str) -> dict[str, int]:
    """« CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx » → {matchid, reservationid, port_tv}.

    Format public du code de partage : 25 caractères en base 57 (poids faible en tête),
    qui encodent un nombre de 18 octets (grand-boutiste) ; chaque champ y est stocké en
    petit-boutiste : matchid (8 octets), reservationid (8), port TV (2)."""
    brut = code.removeprefix("CSGO-").replace("-", "")
    if len(brut) != 25 or any(c not in ALPHABET for c in brut):
        raise ValueError(f"code de partage invalide : {code}")
    nombre = 0
    for c in reversed(brut):
        nombre = nombre * len(ALPHABET) + ALPHABET.index(c)
    octets = nombre.to_bytes(18, "big")
    return {
        "matchid": int.from_bytes(octets[0:8], "little"),
        "reservationid": int.from_bytes(octets[8:16], "little"),
        "port_tv": int.from_bytes(octets[16:18], "little"),
    }


def encoder_code(matchid: int, reservationid: int, port_tv: int) -> str:
    """Inverse de decoder_code (sert aux tests et au contrôle des codes saisis)."""
    octets = (
        matchid.to_bytes(8, "little")
        + reservationid.to_bytes(8, "little")
        + port_tv.to_bytes(2, "little")
    )
    nombre = int.from_bytes(octets, "big")
    caracteres = []
    for _ in range(25):
        nombre, reste = divmod(nombre, len(ALPHABET))
        caracteres.append(ALPHABET[reste])
    brut = "".join(caracteres)
    return "CSGO-" + "-".join(brut[i : i + 5] for i in range(0, 25, 5))


class CodesSteam:
    """Suit les nouveaux codes de partage des parties classées de Mathieu."""

    def __init__(self, cfg: Config, client: httpx.Client | None = None):
        self.cfg = cfg
        self.client = client or httpx.Client(timeout=20)
        self.fichier = cfg.dossier_donnees / "steam_codes.json"

    def _etat(self) -> dict[str, Any]:
        if self.fichier.exists():
            return json.loads(self.fichier.read_text(encoding="utf-8"))
        return {"codes": [], "dernier": self.cfg.steam_code_connu}

    def synchroniser(self, maximum: int = 50) -> list[str]:
        cle = self.cfg.secret("steam", "cle", "STEAM_API_KEY")
        authentification = self.cfg.secret("steam", "code_historique")
        if not (cle and authentification and self.cfg.steamid):
            raise ErreurSource(
                "clé API Steam, code d'authentification de l'historique et "
                "SteamID64 nécessaires (secrets.toml, postgame.toml)"
            )
        etat = self._etat()
        if not etat.get("dernier"):
            raise ErreurSource("dernier code de partage connu absent ([steam] code_connu)")
        nouveaux = []
        for _ in range(maximum):
            r = self.client.get(
                URL_STEAM_CODES,
                params={
                    "key": cle,
                    "steamid": self.cfg.steamid,
                    "steamidkey": authentification,
                    "knowncode": etat["dernier"],
                },
            )
            if r.status_code == 202:  # pas encore de partie plus récente
                break
            if r.status_code != 200:
                raise ErreurSource(f"API Steam : réponse {r.status_code}")
            suivant = r.json().get("result", {}).get("nextcode", "n/a")
            if suivant in ("n/a", "", None):
                break
            nouveaux.append(suivant)
            etat["dernier"] = suivant
        etat["codes"] = etat.get("codes", []) + [
            {"code": c, **decoder_code(c), "demo": None} for c in nouveaux
        ]
        self.fichier.parent.mkdir(parents=True, exist_ok=True)
        self.fichier.write_text(json.dumps(etat, indent=1), encoding="utf-8")
        return nouveaux

    def sans_demo(self) -> list[dict[str, Any]]:
        return [c for c in self._etat().get("codes", []) if not c.get("demo")]


# --- FACEIT -------------------------------------------------------------------------------


def decompresser(source: Path, cible: Path) -> Path:
    """Démo FACEIT : .zst ou .gz → .dem."""
    if source.suffix == ".zst":
        import zstandard

        with source.open("rb") as entree, cible.open("wb") as sortie:
            zstandard.ZstdDecompressor().copy_stream(entree, sortie)
    elif source.suffix == ".gz":
        with gzip.open(source, "rb") as entree, cible.open("wb") as sortie:
            shutil.copyfileobj(entree, sortie)
    else:
        shutil.copyfile(source, cible)
    return cible


class CollecteurFaceit:
    def __init__(self, base: Base, cfg: Config, client: httpx.Client | None = None):
        self.base, self.cfg = base, cfg
        self.client = client or httpx.Client(timeout=60, follow_redirects=True)
        self.dossier = cfg.dossier_donnees / "faceit"

    def _get(self, chemin: str, params: dict[str, Any] | None = None) -> Any:
        cle = self.cfg.secret("faceit", "cle", "FACEIT_API_KEY")
        if not cle:
            raise ErreurSource("clé FACEIT absente (secrets.toml, section [faceit])")
        r = self.client.get(
            f"{URL_FACEIT}{chemin}", params=params, headers={"Authorization": f"Bearer {cle}"}
        )
        if r.status_code != 200:
            raise ErreurSource(f"FACEIT {chemin} : réponse {r.status_code}")
        return r.json()

    def joueur(self) -> str:
        fichier = self.dossier / "joueur.json"
        if fichier.exists():
            return json.loads(fichier.read_text(encoding="utf-8"))["player_id"]
        if not self.cfg.faceit_pseudo:
            raise ErreurSource("pseudo FACEIT absent ([faceit] pseudo dans postgame.toml)")
        donnees = self._get("/players", {"nickname": self.cfg.faceit_pseudo, "game": "cs2"})
        self.dossier.mkdir(parents=True, exist_ok=True)
        fichier.write_text(json.dumps({"player_id": donnees["player_id"]}), encoding="utf-8")
        return donnees["player_id"]

    def lien_demo(self, adresse: str) -> str:
        jeton = self.cfg.secret("faceit", "jeton_telechargement", "FACEIT_DOWNLOAD_TOKEN")
        if not jeton:
            raise ErreurSource("jeton de téléchargement FACEIT absent (accès à demander)")
        r = self.client.post(
            URL_TELECHARGEMENT,
            json={"resource_url": adresse},
            headers={"Authorization": f"Bearer {jeton}"},
        )
        if r.status_code != 200:
            raise ErreurSource(f"téléchargement FACEIT refusé : {r.status_code}")
        return r.json()["payload"]["download_url"]

    def synchroniser(self, nombre: int = 20) -> dict[str, Any]:
        joueur = self.joueur()
        vus_fichier = self.dossier / "vus.json"
        vus = json.loads(vus_fichier.read_text(encoding="utf-8")) if vus_fichier.exists() else []
        historique = self._get(
            f"/players/{joueur}/history", {"game": "cs2", "offset": 0, "limit": nombre}
        )
        bilan: dict[str, Any] = {"importees": 0, "sans_demo": [], "erreurs": []}
        for item in reversed(historique.get("items", [])):
            match_id = item["match_id"]
            if match_id in vus:
                continue
            try:
                match = self._get(f"/matches/{match_id}")
                if match.get("status") != "FINISHED":
                    continue  # en cours : on repassera
                adresses = match.get("demo_url") or []
                if not adresses:
                    bilan["sans_demo"].append(match_id)
                    continue
                demo = self._telecharger(match_id, self.lien_demo(adresses[0]), adresses[0])
                resultat = importer(demo, self.base, self.cfg)
                bilan["importees"] += resultat.statut == "importe"
                vus.append(match_id)
                self.dossier.mkdir(parents=True, exist_ok=True)
                vus_fichier.write_text(json.dumps(vus), encoding="utf-8")
            except ErreurSource as exc:
                bilan["erreurs"].append(f"{match_id} : {exc}")
        return bilan

    def _telecharger(self, match_id: str, lien: str, adresse: str) -> Path:
        dossier = self.dossier / "entrants"
        dossier.mkdir(parents=True, exist_ok=True)
        extension = (
            ".zst" if adresse.endswith(".zst") else ".gz" if adresse.endswith(".gz") else ".dem"
        )
        compresse = dossier / f"{match_id}{extension}"
        with self.client.stream("GET", lien) as r:
            if r.status_code != 200:
                raise ErreurSource(f"démo FACEIT : réponse {r.status_code}")
            with compresse.open("wb") as f:
                for morceau in r.iter_bytes():
                    f.write(morceau)
        demo = decompresser(compresse, dossier / f"faceit_{match_id}.dem")
        if compresse != demo:
            compresse.unlink(missing_ok=True)
        return demo
