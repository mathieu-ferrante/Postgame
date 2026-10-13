"""Rédaction du débrief par un modèle de langage interchangeable (COM-05, NF-04, NF-05).

Garanties :
- le modèle ne reçoit que des mesures déjà calculées, sans nom de joueur, sans démo, sans
  identifiant (NF-05) : libellé, valeur, unité, référence, cible, taille d'échantillon ;
- il doit citer la source de chaque affirmation ([C1], [C2]…) ;
- tout chiffre de sa réponse absent des données envoyées fait rejeter le texte : on garde
  alors le débrief structuré (« il n'invente aucun chiffre ») ;
- le coût est calculé à partir des jetons réellement facturés (NF-04).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from postgame.debrief.constats import Constat
from postgame.games.cs2.armes import STYLES

CONSIGNES = """Tu es le coach de Mathieu, joueur amateur qui veut progresser. Tu rédiges en \
français le débrief d'une partie à partir de mesures déjà calculées.

Règles strictes :
1. N'utilise QUE les chiffres présents dans les données. N'invente, n'arrondis et ne \
calcule aucun autre chiffre (pas de différence, pas de pourcentage nouveau).
2. Chaque phrase qui s'appuie sur une mesure cite sa source entre crochets : [C1], [C2]…
3. Commence par « ## Priorités » : au plus 3 points, dans l'ordre donné par le champ \
« priorites », chacun en 2 ou 3 phrases : ce qui ne va pas, de combien (valeur, référence \
personnelle, cible), et quoi travailler concrètement à la prochaine session.
4. Juge chaque mesure dans son contexte (arme, champion, rôle, patch) et précise ce
contexte ; une cible « provisoire » est indicative, une cible issue du haut classement ou des
pros est une référence mesurée.
5. Puis « ## Points forts » s'il y en a (une phrase chacun), puis « ## Détail » : une \
ligne par autre constat, la plus courte possible.
6. Pas de généralités (« travaille ton aim ») : toujours la situation précise que décrit \
la mesure. Tutoie Mathieu. Pas d'introduction ni de conclusion."""


@dataclass
class Reponse:
    texte: str
    jetons_entree: int = 0
    jetons_sortie: int = 0


class Redacteur(Protocol):
    nom: str
    modele: str

    def rediger(self, consignes: str, donnees: str) -> Reponse: ...


class ErreurRedaction(Exception):
    pass


# --- Données envoyées au modèle -----------------------------------------------------------


def _arrondi(valeur: float | None) -> float | int | None:
    if valeur is None:
        return None
    v = round(float(valeur), 1)
    return int(v) if v == int(v) else v


def donnees_modele(
    selection: dict[str, list[Constat]], jeu: str, mode: str, carte: str
) -> dict[str, Any]:
    """Ce qui part vers le modèle : uniquement des mesures, sans nom ni identifiant."""

    def resume(c: Constat) -> dict[str, Any]:
        d = {
            "source": c.id,
            "mesure": c.libelle,
            "valeur": _arrondi(c.valeur),
            "unite": c.unite,
            "sens": "plus haut = mieux" if c.sens == "haut" else "plus bas = mieux",
        }
        if c.contexte:
            d["precision"] = c.contexte
            categorie = c.contexte.get("categorie")
            if categorie in STYLES:
                d["style_attendu"] = STYLES[categorie]
        if c.reference is not None:
            d["moyenne_personnelle"] = _arrondi(c.reference)
            d["parties_de_reference"] = c.nb_reference
        if c.cible is not None:
            d["cible"] = _arrondi(c.cible)
            d["origine_cible"] = c.source_cible
        if c.n is not None:
            d["echantillon"] = c.n
        if c.preuves:
            d["moments_du_replay"] = len(c.preuves)
        return d

    return {
        "jeu": jeu,
        "mode": mode,
        "carte": carte,
        "priorites": [resume(c) for c in selection["priorites"]],
        "points_forts": [resume(c) for c in selection["points_forts"]],
        "detail": [resume(c) for c in selection["details"]],
    }


# --- Contrôle des chiffres ----------------------------------------------------------------

NOMBRE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?")


def _normaliser(texte: str) -> str:
    return f"{float(texte.replace(',', '.')):g}"


def chiffres_autorises(donnees: dict[str, Any]) -> set[str]:
    autorises = {str(i) for i in range(0, 11)}

    def parcourir(objet: Any) -> None:
        if isinstance(objet, bool):
            return
        if isinstance(objet, int | float):
            for v in (objet, round(objet), round(objet, 1), round(objet, 2)):
                autorises.add(f"{float(v):g}")
        elif isinstance(objet, str):
            for n in NOMBRE.findall(objet):
                autorises.add(_normaliser(n))
        elif isinstance(objet, dict):
            for v in objet.values():
                parcourir(v)
        elif isinstance(objet, list):
            for v in objet:
                parcourir(v)

    parcourir(donnees)
    return autorises


def chiffres_inventes(texte: str, donnees: dict[str, Any]) -> list[str]:
    autorises = chiffres_autorises(donnees)
    return sorted({n for n in NOMBRE.findall(texte) if _normaliser(n) not in autorises})


# --- Débrief sans modèle ------------------------------------------------------------------


def _format(valeur: float | None, unite: str) -> str:
    if valeur is None:
        return "?"
    v = _arrondi(valeur)
    texte = f"{v}".replace(".", ",")
    return f"{texte} {unite}".strip() if unite else texte


def _ligne(c: Constat) -> str:
    morceaux = [f"{_format(c.valeur, c.unite)}"]
    if c.reference is not None:
        morceaux.append(
            f"ta moyenne : {_format(c.reference, c.unite)} sur {c.nb_reference} partie(s)"
        )
    if c.cible is not None:
        origine = f" ({c.source_cible})" if c.source_cible else ""
        morceaux.append(f"cible : {_format(c.cible, c.unite)}{origine}")
    contexte = ", ".join(f"{k} {v}" for k, v in c.contexte.items())
    titre = c.libelle + (f" ({contexte})" if contexte else "")
    exp = " _(mesure en cours de validation)_" if c.experimental else ""
    return f"{titre} — {' ; '.join(morceaux)} [{c.id}]{exp}"


def texte_structure(selection: dict[str, list[Constat]], masquees: int) -> str:
    lignes = ["## Priorités"]
    if selection["priorites"]:
        lignes += [f"{i}. {_ligne(c)}" for i, c in enumerate(selection["priorites"], start=1)]
    else:
        lignes.append("Aucun point prioritaire sur cette partie.")
    if selection["points_forts"]:
        lignes += ["", "## Points forts"] + [f"- {_ligne(c)}" for c in selection["points_forts"]]
    if selection["details"]:
        lignes += ["", "## Détail"] + [f"- {_ligne(c)}" for c in selection["details"]]
    if masquees:
        lignes += [
            "",
            f"_{masquees} mesure(s) pas encore vérifiée(s) à la main ne sont pas affichées._",
        ]
    return "\n".join(lignes)


# --- Fournisseurs -------------------------------------------------------------------------


class GeminiRedacteur:
    """API Gemini (generateContent). Clé dans secrets.toml ou GEMINI_API_KEY."""

    nom = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"

    def __init__(self, cle: str, modele: str, client: httpx.Client | None = None):
        if not cle:
            raise ErreurRedaction("clé Gemini absente (secrets.toml, section [gemini])")
        self.cle, self.modele = cle, modele
        self.client = client or httpx.Client(timeout=60)

    def rediger(self, consignes: str, donnees: str) -> Reponse:
        corps = {
            "systemInstruction": {"parts": [{"text": consignes}]},
            "contents": [{"role": "user", "parts": [{"text": donnees}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
        }
        try:
            r = self.client.post(
                self.URL.format(modele=self.modele),
                json=corps,
                headers={"x-goog-api-key": self.cle},
            )
            r.raise_for_status()
            reponse = r.json()
            parts = reponse["candidates"][0]["content"]["parts"]
            texte = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ErreurRedaction(f"Gemini : {exc}") from exc
        usage = reponse.get("usageMetadata", {})
        sortie = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
        return Reponse(texte.strip(), usage.get("promptTokenCount", 0), sortie)


class LocalRedacteur:
    """Modèle local servi par Ollama (POST /api/chat). Gratuit, rien ne sort du PC."""

    nom = "local"

    def __init__(self, url: str, modele: str, client: httpx.Client | None = None):
        self.url, self.modele = url.rstrip("/"), modele
        self.client = client or httpx.Client(timeout=300)

    def rediger(self, consignes: str, donnees: str) -> Reponse:
        corps = {
            "model": self.modele,
            "stream": False,
            "options": {"temperature": 0.3},
            "messages": [
                {"role": "system", "content": consignes},
                {"role": "user", "content": donnees},
            ],
        }
        try:
            r = self.client.post(f"{self.url}/api/chat", json=corps)
            r.raise_for_status()
            reponse = r.json()
            texte = reponse["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ErreurRedaction(f"modèle local : {exc}") from exc
        return Reponse(
            texte.strip(), reponse.get("prompt_eval_count", 0), reponse.get("eval_count", 0)
        )


def donnees_en_texte(donnees: dict[str, Any]) -> str:
    return json.dumps(donnees, ensure_ascii=False, indent=1)
