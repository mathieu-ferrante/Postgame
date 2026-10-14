"""Analyses League of Legends (lot L9 : LOL-02 à LOL-05).

Chaque mesure porte son contexte : champion, rôle, classe du champion (Data Dragon) et
patch. Une valeur ne se juge jamais hors de ce contexte : 6 sbires/min est faible pour un
tireur au milieu de partie, normal pour un support (qui n'en a pas besoin).

Benchmarks :
- dans la partie : l'adversaire direct (même poste), placé au même niveau par le matchmaking ;
- dans le temps : l'historique de Mathieu sur le même champion et le même rôle ;
- méta : les références de haut classement du même patch (references.py), quand elles
  existent.

Limites des données Riot : positions connues seulement à chaque minute ; balises posées
sans position. Les mesures qui en dépendent sont des approximations (docs/MESURES_LOL_TFT.md).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from postgame.mesures import Preuve, ResultatAnalyse, definir, mesure

MINUTE_MS = 60_000
DISTANCE_ISOLEE = 2500.0  # unités de la carte (≈ 15 000 de côté)
FENETRE_OBJECTIF_MS = 60_000
FENETRE_BALISE_MS = 120_000
DISTANCE_PARTICIPATION = 3000.0
POSTES = {
    "TOP": "haut",
    "JUNGLE": "jungle",
    "MIDDLE": "milieu",
    "BOTTOM": "tireur",
    "UTILITY": "support",
}
# Le farm ne se juge pas pour un support : il ne fait pas partie de son rôle.
POSTES_SANS_FARM = {"UTILITY"}

D_CS = definir("lol.farm.cs", 1, "sbires", "Sbires et monstres tués à la minute indiquée.")
D_ECART_CS = definir(
    "lol.farm.ecart_cs", 1, "sbires", "Écart de farm avec l'adversaire direct à la minute indiquée."
)
D_CS_MIN = definir("lol.farm.cs_par_minute", 1, "sbires/min", "Farm par minute sur la partie.")
D_ECART_OR = definir(
    "lol.or.ecart", 1, "or", "Écart d'or avec l'adversaire direct à la minute indiquée."
)
D_ECART_XP = definir(
    "lol.xp.ecart", 1, "xp", "Écart d'expérience avec l'adversaire direct à la minute indiquée."
)
D_MORTS = definir("lol.morts.nombre", 1, "morts", "Morts dans la partie.", sens="bas")
D_ISOLEES = definir(
    "lol.morts.part_isolees",
    1,
    "%",
    "Part des morts sans allié à moins de 2500 unités (positions à la minute la plus proche).",
    sens="bas",
)
D_AVANT_OBJ = definir(
    "lol.morts.part_avant_objectif",
    1,
    "%",
    "Part des morts suivies, dans la minute, d'un objectif pris par l'équipe adverse "
    "(dragon, nashor, héraut, tour…).",
    sens="bas",
)
D_SANS_BALISE = definir(
    "lol.morts.part_sans_balise_recente",
    1,
    "%",
    "Part des morts sans balise posée par Mathieu dans les 2 minutes précédentes "
    "(approximation de la vision).",
    sens="bas",
)
D_VISION_MIN = definir("lol.vision.score_par_minute", 1, "pts/min", "Score de vision par minute.")
D_ECART_VISION = definir(
    "lol.vision.ecart_score", 1, "pts", "Écart de score de vision avec l'adversaire direct."
)
D_BALISES = definir("lol.vision.balises_posees", 1, "balises", "Balises posées.")
D_DETRUITES = definir("lol.vision.balises_detruites", 1, "balises", "Balises adverses détruites.")
D_PINKS = definir("lol.vision.balises_controle", 1, "balises", "Balises de contrôle achetées.")
D_PART_MONSTRES = definir(
    "lol.objectifs.participation_monstres",
    1,
    "%",
    "Part des dragons, nashors et hérauts de l'équipe auxquels Mathieu participe (tueur, "
    "assistance, ou à moins de 3000 unités).",
)
D_PART_TOURS = definir(
    "lol.objectifs.participation_tours",
    1,
    "%",
    "Part des structures adverses détruites auxquelles Mathieu participe.",
)
D_PART_KILLS = definir(
    "lol.combat.participation_kills",
    1,
    "%",
    "Part des kills de l'équipe auxquels Mathieu participe.",
)
D_DEGATS_MIN = definir(
    "lol.combat.degats_par_minute", 1, "dégâts/min", "Dégâts infligés aux champions par minute."
)

MONSTRES = {
    "DRAGON": "dragon",
    "BARON_NASHOR": "nashor",
    "RIFTHERALD": "héraut",
    "HORDE": "larves",
    "ATAKHAN": "Atakhan",
}


def patch_de(version: str | None) -> str:
    """« 15.20.712.3456 » → « 15.20 »."""
    morceaux = str(version or "").split(".")
    return ".".join(morceaux[:2]) if len(morceaux) >= 2 else "inconnu"


POSTES_VALIDES = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}


def poste_valide(poste: Any) -> str:
    """« MIDDLE » → « MIDDLE » ; vide, « Invalid », « NONE » (ARAM, bots…) → « »."""
    return str(poste) if str(poste or "").upper() in POSTES_VALIDES else ""


@dataclass
class Contexte:
    match: dict[str, Any]
    chrono: dict[str, Any]
    puuid: str
    classes: dict[str, list[str]] = field(default_factory=dict)  # champion → ["Mage", …]

    def __post_init__(self) -> None:
        info = self.match["info"]
        self.participants = info["participants"]
        self.moi = next(p for p in self.participants if p["puuid"] == self.puuid)
        self.pid = int(self.moi["participantId"])
        self.equipe = int(self.moi["teamId"])
        # Poste : seulement teamPosition (calculé par Riot pour la partie). En ARAM ou en
        # mode sans postes, il est vide ; individualPosition vaut alors « Invalid ».
        self.poste = poste_valide(self.moi.get("teamPosition"))
        self.adversaire = next(
            (
                p
                for p in self.participants
                if p["teamId"] != self.equipe
                and self.poste
                and poste_valide(p.get("teamPosition")) == self.poste
            ),
            None,
        )
        self.frames = self.chrono.get("info", {}).get("frames", [])
        self.evenements = [e for f in self.frames for e in f.get("events", [])]
        self.allies = {
            int(p["participantId"]) for p in self.participants if p["teamId"] == self.equipe
        }
        self.patch = patch_de(info.get("gameVersion"))
        champion = self.moi["championName"]
        # Contexte joint à chaque mesure : seuls champion et rôle servent à comparer avec
        # l'historique ; classe, patch et adversaire décrivent (voir debrief/constats.py).
        self.cadre = {
            "champion": champion,
            "role": self.poste,
            "patch": self.patch,
            "classe": "/".join(self.classes.get(champion, [])) or None,
            "adversaire": self.adversaire["championName"] if self.adversaire else None,
        }

    def frame(self, minute: int) -> dict[str, Any] | None:
        """Frame de la minute donnée. La timeline ajoute une dernière frame à l'heure de fin :
        pour une partie finie à 19:40, il n'y a pas de frame « 20 min »."""
        if not 0 <= minute < len(self.frames):
            return None
        f = self.frames[minute]
        horodatage = f.get("timestamp")
        # Les frames régulières tombent quelques millisecondes après la minute pile ; une
        # frame nettement avant (fin de partie) ou bien après n'est pas « la minute N ».
        if horodatage is not None and not (
            minute * MINUTE_MS - 5_000 <= horodatage <= minute * MINUTE_MS + MINUTE_MS / 2
        ):
            return None
        return f

    def etat(self, pid: int, minute: int) -> dict[str, Any] | None:
        f = self.frame(minute)
        return f["participantFrames"].get(str(pid)) if f else None

    def position(self, pid: int, t_ms: float) -> tuple[float, float] | None:
        e = self.etat(pid, round(t_ms / MINUTE_MS))
        if not e or "position" not in e:
            return None
        return float(e["position"]["x"]), float(e["position"]["y"])

    @property
    def minutes(self) -> float:
        duree = float(self.match["info"].get("gameDuration", 0))
        if duree > 100_000:  # anciennes parties : millisecondes
            duree /= 1000
        return duree / 60

    def m(self, definition, valeur, **contexte):
        """Mesure avec le cadre de la partie (champion, rôle, classe, patch)."""
        return mesure(definition, valeur, **{**self.cadre, **contexte})


def horloge(t_ms: float) -> str:
    s = int(t_ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


def _cs(etat: dict[str, Any]) -> int:
    return int(etat.get("minionsKilled", 0)) + int(etat.get("jungleMinionsKilled", 0))


def farm_or_xp(c: Contexte) -> ResultatAnalyse:
    r = ResultatAnalyse()
    farm = c.poste not in POSTES_SANS_FARM
    total = int(c.moi.get("totalMinionsKilled", 0)) + int(c.moi.get("neutralMinionsKilled", 0))
    if c.minutes and farm:
        r.mesures.append(c.m(D_CS_MIN, total / c.minutes))
    for minute in (10, 15, 20):
        moi = c.etat(c.pid, minute)
        if moi is None:
            continue
        if farm:
            r.mesures.append(c.m(D_CS, _cs(moi), minute=minute))
        if c.adversaire is None:
            continue
        adv = c.etat(int(c.adversaire["participantId"]), minute)
        if adv is None:
            continue
        ecart_cs = _cs(moi) - _cs(adv)
        if farm:
            r.mesures.append(c.m(D_ECART_CS, ecart_cs, minute=minute))
        r.mesures += [
            c.m(
                D_ECART_OR,
                int(moi.get("totalGold", 0)) - int(adv.get("totalGold", 0)),
                minute=minute,
            ),
            c.m(D_ECART_XP, int(moi.get("xp", 0)) - int(adv.get("xp", 0)), minute=minute),
        ]
        if minute == 10 and farm:
            r.preuves.append(
                Preuve(
                    D_ECART_CS.nom,
                    minute * MINUTE_MS,
                    f"À 10:00 : {_cs(moi)} sbires avec {c.moi['championName']} contre {_cs(adv)} "
                    f"pour {c.adversaire['championName']} ({ecart_cs:+d})",
                    None,
                )
            )
    return r


def _objectif_adverse(c: Contexte, e: dict[str, Any]) -> bool:
    if e.get("type") == "ELITE_MONSTER_KILL":
        return int(e.get("killerTeamId", 0)) not in (0, c.equipe)
    if e.get("type") == "BUILDING_KILL":
        return int(e.get("teamId", 0)) == c.equipe  # notre structure détruite
    return False


def _nom_objectif(e: dict[str, Any]) -> str:
    if e.get("type") == "ELITE_MONSTER_KILL":
        return "le " + MONSTRES.get(str(e.get("monsterType")), str(e.get("monsterType")).lower())
    return "une tour" if e.get("buildingType") == "TOWER_BUILDING" else "une structure"


def morts(c: Contexte) -> ResultatAnalyse:
    r = ResultatAnalyse()
    mes_morts = [
        e for e in c.evenements if e.get("type") == "CHAMPION_KILL" and e.get("victimId") == c.pid
    ]
    pertes = [e for e in c.evenements if _objectif_adverse(c, e)]
    balises = [
        e["timestamp"]
        for e in c.evenements
        if e.get("type") == "WARD_PLACED" and e.get("creatorId") == c.pid
    ]
    isolees = avant_objectif = sans_balise = 0
    for e in mes_morts:
        t = e["timestamp"]
        pos = e.get("position")
        distance = None
        if pos:
            distances = [
                math.dist((pos["x"], pos["y"]), p)
                for a in c.allies - {c.pid}
                if (p := c.position(a, t)) is not None
            ]
            distance = min(distances) if distances else None
        isolee = distance is None or distance > DISTANCE_ISOLEE
        objectif = next((o for o in pertes if 0 <= o["timestamp"] - t <= FENETRE_OBJECTIF_MS), None)
        balise = any(0 <= t - b <= FENETRE_BALISE_MS for b in balises)
        isolees += isolee
        avant_objectif += objectif is not None
        sans_balise += not balise
        details = []
        if isolee:
            details.append(
                "isolée"
                + (f" (allié le plus proche à {distance:.0f})" if distance is not None else "")
            )
        if objectif is not None:
            details.append(
                f"{(objectif['timestamp'] - t) / 1000:.0f} s avant "
                f"{_nom_objectif(objectif)} pris par l'adversaire"
            )
        if not balise:
            details.append("aucune balise posée dans les 2 minutes")
        tueur = next(
            (p["championName"] for p in c.participants if p["participantId"] == e.get("killerId")),
            "?",
        )
        r.preuves.append(
            Preuve(
                D_MORTS.nom,
                t,
                f"{horloge(t)} — tué par {tueur}" + (f" : {', '.join(details)}" if details else ""),
                None,
                {
                    "x": pos["x"] if pos else None,
                    "y": pos["y"] if pos else None,
                    "isolee": isolee,
                    "avant_objectif": objectif is not None,
                },
            )
        )
    n = len(mes_morts)
    r.mesures.append(c.m(D_MORTS, n))
    if n:
        r.mesures += [
            c.m(D_ISOLEES, 100 * isolees / n, n=n),
            c.m(D_AVANT_OBJ, 100 * avant_objectif / n, n=n),
            c.m(D_SANS_BALISE, 100 * sans_balise / n, n=n),
        ]
    return r


def vision(c: Contexte) -> ResultatAnalyse:
    r = ResultatAnalyse()
    score = float(c.moi.get("visionScore", 0))
    if c.minutes:
        r.mesures.append(c.m(D_VISION_MIN, score / c.minutes))
    r.mesures += [
        c.m(D_BALISES, c.moi.get("wardsPlaced", 0)),
        c.m(D_DETRUITES, c.moi.get("wardsKilled", 0)),
        c.m(D_PINKS, c.moi.get("visionWardsBoughtInGame", c.moi.get("detectorWardsPlaced", 0))),
    ]
    if c.adversaire is not None:
        r.mesures.append(c.m(D_ECART_VISION, score - float(c.adversaire.get("visionScore", 0))))
    return r


def combat(c: Contexte) -> ResultatAnalyse:
    r = ResultatAnalyse()
    kills_equipe = sum(int(p.get("kills", 0)) for p in c.participants if p["teamId"] == c.equipe)
    if kills_equipe:
        part = int(c.moi.get("kills", 0)) + int(c.moi.get("assists", 0))
        r.mesures.append(c.m(D_PART_KILLS, 100 * part / kills_equipe, n=kills_equipe))
    if c.minutes:
        r.mesures.append(
            c.m(D_DEGATS_MIN, float(c.moi.get("totalDamageDealtToChampions", 0)) / c.minutes)
        )
    return r


def objectifs(c: Contexte) -> ResultatAnalyse:
    r = ResultatAnalyse()
    resultats = {"monstres": [0, 0], "tours": [0, 0]}
    for e in c.evenements:
        if e.get("type") == "ELITE_MONSTER_KILL" and int(e.get("killerTeamId", 0)) == c.equipe:
            cle = "monstres"
        elif e.get("type") == "BUILDING_KILL" and int(e.get("teamId", 0)) not in (0, c.equipe):
            cle = "tours"
        else:
            continue
        resultats[cle][1] += 1
        acteurs = {e.get("killerId")} | set(e.get("assistingParticipantIds", []))
        present = c.pid in acteurs
        pos, moi = e.get("position"), c.position(c.pid, e["timestamp"])
        if not present and pos and moi:
            present = math.dist((pos["x"], pos["y"]), moi) <= DISTANCE_PARTICIPATION
        resultats[cle][0] += present
        if not present and cle == "monstres":
            r.preuves.append(
                Preuve(
                    D_PART_MONSTRES.nom,
                    e["timestamp"],
                    f"{horloge(e['timestamp'])} — {_nom_objectif(e)} pris sans Mathieu",
                    None,
                )
            )
    for cle, definition in (("monstres", D_PART_MONSTRES), ("tours", D_PART_TOURS)):
        present, total = resultats[cle]
        if total:
            r.mesures.append(c.m(definition, 100 * present / total, n=total))
    return r


def analyser_lol(
    match: dict[str, Any],
    chrono: dict[str, Any],
    puuid: str,
    classes: dict[str, list[str]] | None = None,
) -> ResultatAnalyse:
    c = Contexte(match, chrono, puuid, classes or {})
    r = ResultatAnalyse()
    for analyse in (farm_or_xp, morts, vision, combat, objectifs):
        r.etendre(analyse(c))
    return r
