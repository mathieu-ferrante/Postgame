"""Protection du service local contre les pages web malveillantes.

Le service écoute sur le réseau local (téléphone) et certaines routes écrivent des fichiers
(annotations et commandes dans le dossier de CS2, captures, notes) ou coûtent de l'argent
(débrief Gemini). Une page web ouverte dans le navigateur de Mathieu ne doit pas pouvoir
les déclencher :

- requête venant d'un autre site (en-tête Sec-Fetch-Site « cross-site », ou Origin dont
  l'hôte diffère de celui demandé) → refusée ;
- nom d'hôte inconnu (attaque « DNS rebinding » : un domaine qui pointe vers 127.0.0.1)
  → refusé ; seuls localhost, les adresses IP, le nom de la machine et les noms .local
  sont acceptés.

Les clients hors navigateur (CS2 qui envoie le GSI, scripts) n'envoient ni Origin ni
Sec-Fetch-Site : ils passent, le GSI restant protégé par son jeton.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Receive, Scope, Send

NOM_CARTE = re.compile(r"^[a-z0-9_]{1,64}$")


def hote_seul(valeur: str) -> str:
    """« 192.168.1.20:8765 » → « 192.168.1.20 » ; « [::1]:8765 » → « ::1 »."""
    valeur = valeur.strip().lower()
    if valeur.startswith("["):
        return valeur[1 : valeur.find("]")] if "]" in valeur else valeur
    return valeur.rsplit(":", 1)[0] if valeur.count(":") == 1 else valeur


def hote_autorise(hote: str, noms_machine: set[str]) -> bool:
    if not hote or hote in {"localhost", "testserver"} or hote in noms_machine:
        return True
    if hote.endswith(".local") or hote.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(hote)
        return True
    except ValueError:
        return False


def noms_de_la_machine() -> set[str]:
    nom = socket.gethostname().lower()
    return {nom, nom.split(".")[0]}


class GardeOrigine:
    """Middleware ASGI : refuse les requêtes intersites et les noms d'hôte inconnus."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.noms_machine = noms_de_la_machine()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        entetes = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        hote = hote_seul(entetes.get("host", ""))
        motif = None
        if not hote_autorise(hote, self.noms_machine):
            motif = "nom d'hôte non autorisé"
        elif entetes.get("sec-fetch-site", "") == "cross-site":
            motif = "requête venant d'un autre site"
        elif "origin" in entetes and entetes["origin"] != "null":
            origine = hote_seul(urlsplit(entetes["origin"]).netloc)
            if origine != hote:
                motif = "requête venant d'un autre site"
        elif entetes.get("origin") == "null":
            motif = "origine opaque"
        if motif is None:
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        corps = ('{"detail": "' + motif + '"}').encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(corps)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": corps})
