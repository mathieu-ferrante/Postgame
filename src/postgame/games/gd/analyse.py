"""Analyses Geometry Dash (lot L8 : GD-02 à GD-06).

Principe : tous les essais sont alignés sur la position X dans le niveau.
- Inputs attendus : les appuis de tous les essais sont regroupés par position (écart de
  moins de 12 u entre voisins) ; un groupe présent dans au moins 3 essais est un input
  attendu, centré sur la médiane.
- Décalage d'un appui : instant de l'appui − instant où l'essai atteint le centre du groupe
  (interpolé sur les positions journalisées). Négatif = trop tôt, positif = trop tard.
- Régularité d'un input : écart-type des décalages (ms).

Toutes les mesures sont `fiable=False` jusqu'à vérification sur une vraie séance.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import numpy as np

from postgame.games.gd.session import Session
from postgame.mesures import Preuve, ResultatAnalyse, definir, mesure

ECART_GROUPE = 12.0  # u : deux appuis plus proches appartiennent au même input attendu
MIN_ESSAIS_INPUT = 3
SEUIL_STABLE_MS = 15.0
NB_INSTABLES = 5
SPAM_INTERVALLE_MS = 150.0
SPAM_MIN_APPUIS = 4
NB_SEGMENTS = 10
MIN_ESSAIS_PRACTICE_GAIN = 3

D_REG_ECART = definir(
    "gd.regularite.ecart_type_median",
    1,
    "ms",
    "Écart-type médian du moment de l'appui, sur l'ensemble des inputs attendus du niveau.",
    sens="bas",
)
D_REG_DECALAGE = definir(
    "gd.regularite.decalage_moyen",
    1,
    "ms",
    "Décalage moyen des appuis par rapport à l'habitude ; négatif = trop tôt, positif = trop tard.",
    sens="neutre",
)
D_REG_STABLES = definir(
    "gd.regularite.part_inputs_stables",
    1,
    "%",
    "Part des inputs attendus dont l'écart-type est sous 15 ms.",
)
D_INSTABLES_MORTS = definir(
    "gd.instables.part_morts_apres_instables",
    1,
    "%",
    "Part des morts survenues juste après l'un des 5 inputs les plus irréguliers.",
    sens="neutre",
)
D_MORT = definir("gd.mort", 1, "%", "Position de chaque mort (carte des morts).", sens="neutre")
D_SURVIE = definir(
    "gd.survie.par_segment",
    1,
    "%",
    "Taux de survie par tranche de 10 % du niveau (essais en mode normal qui y arrivent).",
)
D_SPAM_CPS = definir(
    "gd.spam.cps_moyen",
    1,
    "clics/s",
    "Cadence moyenne dans les passages de spam (4 appuis ou plus à moins de 150 ms d'écart).",
    sens="neutre",
)
D_SPAM_IRREG = definir(
    "gd.spam.irregularite",
    1,
    "%",
    "Irrégularité des intervalles dans les passages de spam (écart-type / moyenne).",
    sens="bas",
)
D_MEILLEUR = definir(
    "gd.progression.meilleur_pourcent", 1, "%", "Meilleur pourcentage atteint en mode normal."
)
D_MOYEN = definir(
    "gd.progression.pourcent_moyen",
    1,
    "%",
    "Pourcentage moyen atteint par les essais en mode normal.",
)
D_DISPERSION = definir(
    "gd.progression.ecart_type_pourcent",
    1,
    "%",
    "Écart-type du pourcentage atteint en mode normal (régularité d'un essai à l'autre).",
    sens="bas",
)
D_ESSAIS = definir("gd.progression.essais", 1, "essais", "Essais en mode normal.", sens="neutre")
D_PRACTICE = definir(
    "gd.progression.essais_practice", 1, "essais", "Essais en mode entraînement.", sens="neutre"
)
D_PRACTICE_GAIN = definir(
    "gd.practice.gain",
    1,
    "points",
    "Pourcentage moyen en mode normal après les premiers essais d'entraînement de la séance, "
    "moins celui d'avant.",
)
D_RESOLUTION = definir(
    "gd.technique.resolution_ms",
    1,
    "ms",
    "Pas de temps du jeu déduit des clics (tous les instants en sont des multiples) : "
    "précision de l'horodatage.",
    sens="neutre",
)


def _pct(n: float, total: float) -> float | None:
    return 100.0 * n / total if total else None


@dataclass
class InputAttendu:
    x: float
    decalages: list[float] = field(default_factory=list)  # ms, un par essai
    essais: list[int] = field(default_factory=list)  # index des essais

    @property
    def ecart_type(self) -> float:
        return statistics.pstdev(self.decalages) if len(self.decalages) > 1 else 0.0

    @property
    def decalage(self) -> float:
        return statistics.fmean(self.decalages) if self.decalages else 0.0


def longueur_niveau(session: Session) -> float | None:
    """Position X correspondant à 100 %, déduite des morts (pct = x / longueur) ou d'un
    essai terminé."""
    ratios = [
        e.x_fin / e.pct_fin * 100
        for e in session.essais
        if e.mort and e.pct_fin and e.pct_fin > 1 and e.x_fin
    ]
    if ratios:
        return float(np.median(ratios))
    finis = [e.x_fin for e in session.essais if e.complete and e.x_fin]
    return max(finis) if finis else None


def pourcent(x: float, longueur: float | None) -> float | None:
    return round(100 * x / longueur, 1) if longueur else None


def inputs_attendus(session: Session) -> list[InputAttendu]:
    appuis = sorted((c.x, i) for i, e in enumerate(session.essais) for c in e.appuis)
    if not appuis:
        return []
    groupes: list[list[tuple[float, int]]] = [[appuis[0]]]
    for x, i in appuis[1:]:
        if x - groupes[-1][-1][0] <= ECART_GROUPE:
            groupes[-1].append((x, i))
        else:
            groupes.append([(x, i)])
    attendus = []
    for g in groupes:
        essais = {i for _, i in g}
        if len(essais) >= MIN_ESSAIS_INPUT:
            attendus.append(InputAttendu(x=float(np.median([x for x, _ in g]))))
    # Rattachement : pour chaque essai, l'appui le plus proche de chaque centre (un seul).
    centres = [a.x for a in attendus]
    for k, attendu in enumerate(attendus):
        gauche = (centres[k] - centres[k - 1]) / 2 if k > 0 else ECART_GROUPE * 2
        droite = (centres[k + 1] - centres[k]) / 2 if k + 1 < len(centres) else ECART_GROUPE * 2
        for i, essai in enumerate(session.essais):
            proches = [
                c
                for c in essai.appuis
                if -min(gauche, 2 * ECART_GROUPE)
                <= c.x - attendu.x
                <= min(droite, 2 * ECART_GROUPE)
            ]
            if not proches:
                continue
            clic = min(proches, key=lambda c: abs(c.x - attendu.x))
            arrivee = essai.instant_a(attendu.x)
            if arrivee is None:
                continue
            attendu.decalages.append(clic.t - arrivee)
            attendu.essais.append(i)
    return [a for a in attendus if len(a.decalages) >= MIN_ESSAIS_INPUT]


def regularite(
    session: Session, attendus: list[InputAttendu], longueur: float | None
) -> ResultatAnalyse:
    r = ResultatAnalyse()
    if not attendus:
        return r
    ecarts = [a.ecart_type for a in attendus]
    tous = [d for a in attendus for d in a.decalages]
    r.mesures += [
        mesure(D_REG_ECART, float(np.median(ecarts)), n=len(attendus)),
        mesure(D_REG_DECALAGE, statistics.fmean(tous), n=len(tous)),
        mesure(
            D_REG_STABLES,
            _pct(sum(e <= SEUIL_STABLE_MS for e in ecarts), len(ecarts)),
            n=len(ecarts),
        ),
    ]
    # GD-03 : passages instables et morts qui les suivent.
    instables = sorted(attendus, key=lambda a: a.ecart_type, reverse=True)[:NB_INSTABLES]
    morts = [e for e in session.essais if e.mort and e.x_fin is not None]
    xs = [a.x for a in attendus]
    morts_apres_instable = 0
    for e in morts:
        precedents = [a for a in attendus if a.x <= e.x_fin]
        if precedents and precedents[-1] in instables:
            morts_apres_instable += 1
    if morts:
        r.mesures.append(
            mesure(D_INSTABLES_MORTS, _pct(morts_apres_instable, len(morts)), n=len(morts))
        )
    for a in instables:
        k = xs.index(a.x)
        suivant = xs[k + 1] if k + 1 < len(xs) else float("inf")
        passages = len(a.decalages)
        morts_ici = sum(1 for e in morts if a.x <= e.x_fin < suivant)
        sens = "trop tôt" if a.decalage < 0 else "trop tard"
        ou = pourcent(a.x, longueur)
        unite = "%" if ou is not None else "u"
        r.preuves.append(
            Preuve(
                D_REG_ECART.nom,
                None,
                f"Input à {ou if ou is not None else round(a.x)} {unite} : "
                f"écart-type {a.ecart_type:.0f} ms, en moyenne {abs(a.decalage):.0f} ms {sens}, "
                f"{morts_ici} mort(s) juste après sur {passages} passage(s)",
                None,
                {
                    "x": round(a.x, 1),
                    "pct": ou,
                    "ecart_type": round(a.ecart_type, 1),
                    "decalage": round(a.decalage, 1),
                    "morts": morts_ici,
                },
            )
        )
    return r


def carte_des_morts(session: Session, longueur: float | None) -> ResultatAnalyse:
    r = ResultatAnalyse()
    for e in session.essais:
        if e.mort and e.pct_fin is not None:
            r.preuves.append(
                Preuve(
                    D_MORT.nom,
                    None,
                    f"Essai {e.numero} ({e.mode}) : mort à {e.pct_fin:.1f} %",
                    None,
                    {
                        "pct": round(e.pct_fin, 2),
                        "x": e.x_fin,
                        "mode": e.mode,
                        "essai": e.numero,
                        "objet": e.objet,
                    },
                )
            )
    normaux = [e for e in session.essais if e.mode == "normal" and e.t_fin is not None]
    if not normaux or longueur is None:
        return r
    pire = None
    for s in range(NB_SEGMENTS):
        debut, fin = 100 * s / NB_SEGMENTS, 100 * (s + 1) / NB_SEGMENTS
        arrives = [
            e
            for e in normaux
            if (pourcent(e.x_debut, longueur) or 0) <= debut
            and (e.complete or (e.pct_fin or 0) >= debut)
        ]
        if not arrives:
            continue
        survivants = [e for e in arrives if e.complete or (e.pct_fin or 0) >= fin]
        taux = _pct(len(survivants), len(arrives))
        r.mesures.append(mesure(D_SURVIE, taux, segment=f"{debut:.0f}-{fin:.0f}", n=len(arrives)))
        if pire is None or taux < pire[0]:
            pire = (taux, debut, fin, len(arrives))
    if pire:
        r.preuves.append(
            Preuve(
                D_SURVIE.nom,
                None,
                f"Passage le plus meurtrier : {pire[1]:.0f}-{pire[2]:.0f} %, "
                f"survie {pire[0]:.0f} % sur {pire[3]} essai(s)",
                None,
                {"segment": f"{pire[1]:.0f}-{pire[2]:.0f}"},
            )
        )
    return r


def spam(session: Session, longueur: float | None) -> ResultatAnalyse:
    r = ResultatAnalyse()
    cadences, irregularites = [], []
    for e in session.essais:
        temps = [c.t for c in e.appuis]
        serie = [0]
        for k in range(1, len(temps) + 1):
            if k < len(temps) and temps[k] - temps[k - 1] < SPAM_INTERVALLE_MS:
                serie.append(k)
                continue
            if len(serie) >= SPAM_MIN_APPUIS:
                t = [temps[i] for i in serie]
                intervalles = np.diff(t)
                cadences.append((len(t) - 1) / ((t[-1] - t[0]) / 1000))
                irregularites.append(100 * float(np.std(intervalles) / np.mean(intervalles)))
            serie = [k]
    if cadences:
        r.mesures.append(mesure(D_SPAM_CPS, float(np.mean(cadences)), n=len(cadences)))
        r.mesures.append(mesure(D_SPAM_IRREG, float(np.mean(irregularites)), n=len(cadences)))
    return r


def progression(session: Session) -> ResultatAnalyse:
    r = ResultatAnalyse()
    normaux = [e for e in session.essais if e.mode == "normal" and e.pct_fin is not None]
    practice = [e for e in session.essais if e.mode == "practice"]
    r.mesures.append(mesure(D_ESSAIS, len(normaux)))
    r.mesures.append(mesure(D_PRACTICE, len(practice)))
    if normaux:
        pcts = [e.pct_fin for e in normaux]
        r.mesures += [
            mesure(D_MEILLEUR, max(pcts), n=len(pcts)),
            mesure(D_MOYEN, statistics.fmean(pcts), n=len(pcts)),
        ]
        if len(pcts) > 1:
            r.mesures.append(mesure(D_DISPERSION, statistics.pstdev(pcts), n=len(pcts)))
    if practice and normaux:
        premier = min(e.t_debut for e in practice)
        avant = [e.pct_fin for e in normaux if e.t_debut < premier]
        apres = [e.pct_fin for e in normaux if e.t_debut > premier]
        if len(avant) >= MIN_ESSAIS_PRACTICE_GAIN and len(apres) >= MIN_ESSAIS_PRACTICE_GAIN:
            r.mesures.append(
                mesure(
                    D_PRACTICE_GAIN,
                    statistics.fmean(apres) - statistics.fmean(avant),
                    avant=len(avant),
                    apres=len(apres),
                )
            )
    return r


def pas_commun(valeurs_ms: list[float], tolerance_ms: float = 0.05) -> float | None:
    """Plus grand pas q tel que tous les écarts entre valeurs soient des multiples de q.

    Le plus petit écart observé peut valoir plusieurs pas (2 × 4,17 ms…) : on essaie ses
    sous-multiples jusqu'à en trouver un qui divise tous les écarts."""
    distinctes = sorted(set(round(v, 3) for v in valeurs_ms))
    ecarts = [b - a for a, b in zip(distinctes, distinctes[1:], strict=False) if b - a > 0.01]
    if not ecarts:
        return None
    plus_petit = min(ecarts)
    for k in range(1, 9):
        q = plus_petit / k
        # Ajustement aux moindres carrés : le plus petit écart est lui-même arrondi.
        multiples = [round(e / q) for e in ecarts]
        q = sum(e * n for e, n in zip(ecarts, multiples, strict=True)) / sum(
            n * n for n in multiples
        )
        if all(abs(e - round(e / q) * q) <= tolerance_ms for e in ecarts):
            return q
    return None


def resolution(session: Session) -> ResultatAnalyse:
    """Pas de temps du jeu, déduit des temps de niveau (tn) des clics."""
    r = ResultatAnalyse()
    valeurs = [c.tn * 1000 for e in session.essais for c in e.clics if c.tn is not None]
    q = pas_commun(valeurs)
    if q is not None:
        r.mesures.append(mesure(D_RESOLUTION, q, n=len(set(valeurs))))
    return r


def analyser_session(session: Session) -> ResultatAnalyse:
    r = ResultatAnalyse()
    longueur = longueur_niveau(session)
    if not session.plateforme:
        attendus = inputs_attendus(session)
        r.etendre(regularite(session, attendus, longueur))
        r.etendre(spam(session, longueur))
    r.etendre(carte_des_morts(session, longueur))
    r.etendre(progression(session))
    r.etendre(resolution(session))
    return r
