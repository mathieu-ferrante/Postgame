"""Décisions et stratégie CS2 (lot L4 : CS-DEC-01 à 05, CS-STR-01).

Tout est calculé round par round, à partir du déroulé des morts (qui est encore vivant à
chaque instant), de la bombe et du vainqueur du round. Rien en deathmatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from postgame.games.cs2.donnees import TICKS_PAR_SECONDE, DonneesMatch, Positions
from postgame.mesures import Preuve, ResultatAnalyse, definir, mesure

CAMPS = {2: "T", 3: "CT"}
DISTANCE_SITE_ARRIVEE = 1000.0  # u : Mathieu est « sur le site » de la bombe
DISTANCE_SITE_LOIN = 1200.0  # u : au-delà, Mathieu doit tourner
PAS_ROTATION_TICKS = TICKS_PAR_SECONDE // 4
ECART_PERDU = 2  # adversaires de plus que l'équipe…
MAX_VIVANTS_PERDU = 2  # … et au plus 2 coéquipiers vivants (Mathieu compris)
ROUNDS_PAR_MOITIE = 12  # MR12 (Premier et compétitif)

D_OUV_IMPLIQUE = definir(
    "cs2.ouverture.part_impliquee",
    1,
    "%",
    "Part des rounds où Mathieu prend part au premier duel (tue ou meurt en premier).",
    sens="neutre",
)
D_OUV_VICTOIRE = definir(
    "cs2.ouverture.taux_victoire", 1, "%", "Part des duels d'ouverture de Mathieu qu'il gagne."
)
D_OUV_APRES_V = definir(
    "cs2.ouverture.rounds_gagnes_apres_victoire",
    1,
    "%",
    "Part des rounds gagnés par l'équipe quand Mathieu gagne le duel d'ouverture.",
)
D_OUV_APRES_D = definir(
    "cs2.ouverture.rounds_gagnes_apres_defaite",
    1,
    "%",
    "Part des rounds gagnés par l'équipe quand Mathieu perd le duel d'ouverture.",
)
D_ROT_DELAI = definir(
    "cs2.rotation.delai_median",
    1,
    "s",
    "CT loin du site à la pose de la bombe : délai médian pour arriver à moins de 1000 u.",
    sens="bas",
)
D_ROT_ARRIVEE = definir(
    "cs2.rotation.part_arrivee",
    1,
    "%",
    "Part des rotations après la pose où Mathieu arrive sur le site avant la fin du round.",
)
D_SAVE_NB = definir(
    "cs2.save.situations",
    1,
    "rounds",
    "Rounds où l'équipe de Mathieu (vivant) est à au plus 2 contre au moins 2 de plus.",
    sens="neutre",
)
D_SAVE_SAUVE = definir(
    "cs2.save.part_sauvegardes",
    1,
    "%",
    "Dans ces situations, part des rounds où Mathieu survit (arme sauvée).",
    sens="neutre",
)
D_SAVE_INUTILE = definir(
    "cs2.save.part_morts_inutiles",
    1,
    "%",
    "Dans ces situations perdues, part des rounds où Mathieu meurt sans tuer personne.",
    sens="bas",
)
D_SAVE_VALEUR = definir(
    "cs2.save.valeur_perdue",
    1,
    "$",
    "Valeur d'équipement perdue dans ces morts inutiles.",
    sens="bas",
)
D_POSE_VICTOIRE = definir(
    "cs2.apres_pose.taux_victoire",
    1,
    "%",
    "Rounds gagnés après une pose, Mathieu T vivant à la pose.",
)
D_POSE_SURVIE = definir(
    "cs2.apres_pose.survie", 1, "%", "Part de ces rounds où Mathieu est encore vivant à la fin."
)
D_POSE_KILLS = definir(
    "cs2.apres_pose.kills_moyens", 1, "kills", "Kills moyens de Mathieu après la pose."
)
D_RETAKE_VICTOIRE = definir(
    "cs2.retake.taux_victoire",
    1,
    "%",
    "Rounds gagnés après une pose adverse, Mathieu CT vivant à la pose.",
)
D_RETAKE_SURVIE = definir(
    "cs2.retake.survie", 1, "%", "Part de ces rounds où Mathieu est encore vivant à la fin."
)
D_RETAKE_KILLS = definir(
    "cs2.retake.kills_moyens", 1, "kills", "Kills moyens de Mathieu après la pose adverse."
)
D_CLUTCH_NB = definir(
    "cs2.clutch.situations",
    1,
    "rounds",
    "Rounds où Mathieu se retrouve seul en vie contre 1 adversaire ou plus.",
    sens="neutre",
)
D_CLUTCH_VICTOIRE = definir(
    "cs2.clutch.taux_victoire", 1, "%", "Part des clutchs gagnés (aussi par nombre d'adversaires)."
)
D_STR_POSES = definir(
    "cs2.strat.part_poses_site",
    1,
    "%",
    "Rounds T de l'équipe de Mathieu : part des poses sur chaque site (ou sans pose).",
    sens="neutre",
)
D_STR_VICTOIRE = definir(
    "cs2.strat.taux_victoire_site",
    1,
    "%",
    "Rounds T de l'équipe : taux de victoire selon le site de pose.",
)
D_STR_REPETITION = definir(
    "cs2.strat.repetition_max",
    1,
    "rounds",
    "Plus longue série de rounds T consécutifs joués sur le même site.",
    sens="neutre",
)
D_STR_ADVERSE = definir(
    "cs2.strat.adverse_part_poses_site",
    1,
    "%",
    "Rounds T des adversaires : part des poses sur chaque site (ou sans pose).",
    sens="neutre",
)
D_STR_MOITIE = definir(
    "cs2.strat.taux_victoire_moitie", 1, "%", "Taux de victoire de l'équipe par moitié de match."
)


def _pct(n: float, total: float) -> float | None:
    return 100.0 * n / total if total else None


def site_depuis_lieu(lieu: str | None) -> str:
    if not lieu:
        return "?"
    m = re.search(r"bombsite\s*_?([ab])", lieu, re.IGNORECASE)
    return m.group(1).upper() if m else lieu


@dataclass
class Round:
    """Déroulé d'un round du point de vue de Mathieu."""

    numero: int
    debut: int
    fin: int
    gagnant: int | None
    mon_equipe: int
    vivants_debut: dict[int, set[str]]
    morts: pd.DataFrame  # morts du round, dans l'ordre
    pose: pd.Series | None = None
    poseur: str | None = None
    mes_kills: list[int] = field(default_factory=list)
    ma_mort: int | None = None

    @property
    def gagne(self) -> bool | None:
        return None if self.gagnant is None else self.gagnant == self.mon_equipe

    @property
    def adverse(self) -> int:
        return 3 if self.mon_equipe == 2 else 2

    def vivants_a(self, tick: int) -> dict[int, set[str]]:
        """Joueurs vivants par équipe juste après les morts survenues jusqu'à `tick` inclus."""
        vivants = {e: set(s) for e, s in self.vivants_debut.items()}
        for _, m in self.morts[self.morts["tick"] <= tick].iterrows():
            for equipe in vivants:
                vivants[equipe].discard(m["victime"])
        return vivants


def decouper_rounds(d: DonneesMatch, pos: Positions) -> list[Round]:
    rounds = []
    for _, r in d.rounds.iterrows():
        debut, fin = int(r["debut"]), int(r["fin"])
        mon_equipe = pos.equipe(d.moi, debut)
        if mon_equipe not in (2, 3):
            continue
        vivants: dict[int, set[str]] = {2: set(), 3: set()}
        for sid in pos.joueurs():
            e = pos.etat(sid, debut)
            if e is not None and bool(e["vivant"]) and int(e["equipe"]) in vivants:
                vivants[int(e["equipe"])].add(sid)
        morts = d.morts[(d.morts["tick"] >= debut) & (d.morts["tick"] <= fin)].sort_values("tick")
        poses = d.bombe[
            (d.bombe["evenement"] == "pose") & (d.bombe["tick"] >= debut) & (d.bombe["tick"] <= fin)
        ]
        gagnant = r.get("gagnant")
        rnd = Round(
            numero=int(r["numero"]),
            debut=debut,
            fin=fin,
            gagnant=None if gagnant is None or pd.isna(gagnant) else int(gagnant),
            mon_equipe=mon_equipe,
            vivants_debut=vivants,
            morts=morts,
            pose=poses.iloc[0] if len(poses) else None,
            poseur=str(poses.iloc[0]["steamid"]) if len(poses) else None,
            mes_kills=[
                int(t)
                for t in morts.loc[
                    (morts["attaquant"] == d.moi) & (morts["victime"] != d.moi), "tick"
                ]
            ],
        )
        mienne = morts[morts["victime"] == d.moi]
        rnd.ma_mort = int(mienne["tick"].iloc[0]) if len(mienne) else None
        rounds.append(rnd)
    return rounds


# --- CS-DEC-01 : duels d'ouverture ---------------------------------------------------------


def ouvertures(d: DonneesMatch, rounds: list[Round]) -> ResultatAnalyse:
    r = ResultatAnalyse()
    impliques, gagnes, apres_v, apres_d = 0, 0, [], []
    for rnd in rounds:
        duels = rnd.morts[
            rnd.morts["attaquant"].isin(rnd.vivants_debut[rnd.adverse])
            | rnd.morts["victime"].isin(rnd.vivants_debut[rnd.adverse])
        ]
        duels = duels[duels["attaquant"] != duels["victime"]]
        if not len(duels):
            continue
        premier = duels.iloc[0]
        if d.moi not in (premier["attaquant"], premier["victime"]):
            continue
        impliques += 1
        gagne_duel = premier["attaquant"] == d.moi
        gagnes += gagne_duel
        if rnd.gagne is not None:
            (apres_v if gagne_duel else apres_d).append(rnd.gagne)
        if not gagne_duel:
            r.preuves.append(
                Preuve(
                    D_OUV_VICTOIRE.nom,
                    int(premier["tick"]),
                    f"Round {rnd.numero} : duel d'ouverture perdu ({premier['arme']})"
                    + (
                        ""
                        if rnd.gagne is None
                        else (", round gagné" if rnd.gagne else ", round perdu")
                    ),
                    rnd.numero,
                )
            )
    if rounds:
        r.mesures.append(mesure(D_OUV_IMPLIQUE, _pct(impliques, len(rounds)), n=len(rounds)))
    if impliques:
        r.mesures.append(mesure(D_OUV_VICTOIRE, _pct(gagnes, impliques), n=impliques))
    if apres_v:
        r.mesures.append(mesure(D_OUV_APRES_V, _pct(sum(apres_v), len(apres_v)), n=len(apres_v)))
    if apres_d:
        r.mesures.append(mesure(D_OUV_APRES_D, _pct(sum(apres_d), len(apres_d)), n=len(apres_d)))
    return r


# --- CS-DEC-02 : rotations ----------------------------------------------------------------


def rotations(d: DonneesMatch, rounds: list[Round], pos: Positions) -> ResultatAnalyse:
    r = ResultatAnalyse()
    delais, arrivees, total = [], 0, 0
    for rnd in rounds:
        if rnd.pose is None or rnd.mon_equipe != 3 or not rnd.poseur:
            continue
        t_pose = int(rnd.pose["tick"])
        if rnd.ma_mort is not None and rnd.ma_mort <= t_pose:
            continue
        poseur = pos.etat(rnd.poseur, t_pose)
        moi = pos.etat(d.moi, t_pose)
        if poseur is None or moi is None:
            continue
        bombe = np.array([poseur["x"], poseur["y"]], dtype=float)
        if np.hypot(moi["x"] - bombe[0], moi["y"] - bombe[1]) <= DISTANCE_SITE_LOIN:
            continue
        total += 1
        limite = min(rnd.fin, rnd.ma_mort if rnd.ma_mort is not None else rnd.fin)
        arrivee = None
        for t in range(t_pose, limite + 1, PAS_ROTATION_TICKS):
            e = pos.etat(d.moi, t)
            if (
                e is not None
                and np.hypot(e["x"] - bombe[0], e["y"] - bombe[1]) <= DISTANCE_SITE_ARRIVEE
            ):
                arrivee = t
                break
        if arrivee is not None:
            arrivees += 1
            delai = (arrivee - t_pose) / TICKS_PAR_SECONDE
            delais.append(delai)
            texte = f"Round {rnd.numero} : rotation en {delai:.1f} s après la pose"
        else:
            texte = f"Round {rnd.numero} : jamais arrivé sur le site après la pose"
        r.preuves.append(Preuve(D_ROT_DELAI.nom, t_pose, texte, rnd.numero))
    if delais:
        r.mesures.append(mesure(D_ROT_DELAI, float(np.median(delais)), n=len(delais)))
    if total:
        r.mesures.append(mesure(D_ROT_ARRIVEE, _pct(arrivees, total), n=total))
    return r


# --- CS-DEC-03 : sauver ou rejouer ----------------------------------------------------------


def _valeur_equipement(d: DonneesMatch, tick: int) -> int | None:
    lignes = d.economie[(d.economie["steamid"] == d.moi) & (d.economie["tick"] == tick)]
    return int(lignes["valeur_equipement"].iloc[0]) if len(lignes) else None


def saves(d: DonneesMatch, rounds: list[Round]) -> ResultatAnalyse:
    r = ResultatAnalyse()
    situations, sauves, inutiles, valeur_perdue = 0, 0, 0, 0
    for rnd in rounds:
        moment = None
        for _, m in rnd.morts.iterrows():
            v = rnd.vivants_a(int(m["tick"]))
            mes, leurs = v[rnd.mon_equipe], v[rnd.adverse]
            if d.moi not in mes:
                break
            if len(mes) <= MAX_VIVANTS_PERDU and len(leurs) >= len(mes) + ECART_PERDU:
                moment = int(m["tick"])
                break
        if moment is None:
            continue
        situations += 1
        v = rnd.vivants_a(moment)
        etat = f"{len(v[rnd.mon_equipe])}v{len(v[rnd.adverse])}"
        kills_apres = [t for t in rnd.mes_kills if t > moment]
        if rnd.ma_mort is None:
            sauves += 1
            valeur = _valeur_equipement(d, rnd.fin)
            texte = f"Round {rnd.numero} ({etat}) : survie" + (
                f", {valeur} $ d'équipement gardés" if valeur else ""
            )
        elif not kills_apres and not rnd.gagne:
            inutiles += 1
            valeur = _valeur_equipement(d, rnd.ma_mort - 1) or 0
            valeur_perdue += valeur
            texte = f"Round {rnd.numero} ({etat}) : mort sans kill, {valeur} $ perdus"
        else:
            texte = f"Round {rnd.numero} ({etat}) : rejoué, {len(kills_apres)} kill(s)" + (
                ", round gagné" if rnd.gagne else ""
            )
        r.preuves.append(Preuve(D_SAVE_INUTILE.nom, moment, texte, rnd.numero))
    if situations:
        r.mesures += [
            mesure(D_SAVE_NB, situations),
            mesure(D_SAVE_SAUVE, _pct(sauves, situations), n=situations),
            mesure(D_SAVE_INUTILE, _pct(inutiles, situations), n=situations),
            mesure(D_SAVE_VALEUR, valeur_perdue, n=situations),
        ]
    return r


# --- CS-DEC-04 : après pose et retakes -----------------------------------------------------


def apres_pose_et_retakes(d: DonneesMatch, rounds: list[Round]) -> ResultatAnalyse:
    r = ResultatAnalyse()
    stats = {2: ([], [], []), 3: ([], [], [])}  # victoires, survies, kills
    for rnd in rounds:
        if rnd.pose is None or rnd.gagne is None:
            continue
        t_pose = int(rnd.pose["tick"])
        if rnd.ma_mort is not None and rnd.ma_mort <= t_pose:
            continue
        victoires, survies, kills = stats[rnd.mon_equipe]
        victoires.append(rnd.gagne)
        survies.append(rnd.ma_mort is None)
        k = len([t for t in rnd.mes_kills if t > t_pose])
        kills.append(k)
        lieu = d.lieux[(d.lieux["steamid"] == d.moi) & (d.lieux["tick"] == t_pose)]
        ou = f" à {lieu['lieu'].iloc[0]}" if len(lieu) and lieu["lieu"].iloc[0] else ""
        site = site_depuis_lieu(_lieu_poseur(d, rnd))
        phase = "Après pose" if rnd.mon_equipe == 2 else "Retake"
        definition = D_POSE_VICTOIRE if rnd.mon_equipe == 2 else D_RETAKE_VICTOIRE
        r.preuves.append(
            Preuve(
                definition.nom,
                t_pose,
                f"{phase} round {rnd.numero} (site {site}) : Mathieu{ou}, {k} kill(s), "
                f"{'survit' if rnd.ma_mort is None else 'meurt'}, round "
                f"{'gagné' if rnd.gagne else 'perdu'}",
                rnd.numero,
            )
        )
    for equipe, (dv, ds, dk) in (
        (2, (D_POSE_VICTOIRE, D_POSE_SURVIE, D_POSE_KILLS)),
        (3, (D_RETAKE_VICTOIRE, D_RETAKE_SURVIE, D_RETAKE_KILLS)),
    ):
        victoires, survies, kills = stats[equipe]
        if victoires:
            n = len(victoires)
            r.mesures += [
                mesure(dv, _pct(sum(victoires), n), n=n),
                mesure(ds, _pct(sum(survies), n), n=n),
                mesure(dk, float(np.mean(kills)), n=n),
            ]
    return r


def _lieu_poseur(d: DonneesMatch, rnd: Round) -> str | None:
    if rnd.pose is None or not rnd.poseur:
        return None
    lignes = d.lieux[
        (d.lieux["steamid"] == rnd.poseur) & (d.lieux["tick"] == int(rnd.pose["tick"]))
    ]
    return str(lignes["lieu"].iloc[0]) if len(lignes) else None


# --- CS-DEC-05 : clutchs ------------------------------------------------------------------


def clutchs(d: DonneesMatch, rounds: list[Round]) -> ResultatAnalyse:
    r = ResultatAnalyse()
    issues: list[tuple[int, bool]] = []
    for rnd in rounds:
        if rnd.gagne is None:
            continue
        for _, m in rnd.morts.iterrows():
            t = int(m["tick"])
            v = rnd.vivants_a(t)
            if d.moi not in v[rnd.mon_equipe]:
                break
            if v[rnd.mon_equipe] == {d.moi} and v[rnd.adverse]:
                x = len(v[rnd.adverse])
                kills = len([k for k in rnd.mes_kills if k > t])
                issues.append((x, bool(rnd.gagne)))
                r.preuves.append(
                    Preuve(
                        D_CLUTCH_VICTOIRE.nom,
                        t,
                        f"Round {rnd.numero} : 1v{x} {'gagné' if rnd.gagne else 'perdu'}, "
                        f"{kills} kill(s)",
                        rnd.numero,
                        {"adversaires": x},
                    )
                )
                break
    if issues:
        r.mesures.append(mesure(D_CLUTCH_NB, len(issues)))
        r.mesures.append(
            mesure(D_CLUTCH_VICTOIRE, _pct(sum(g for _, g in issues), len(issues)), n=len(issues))
        )
        for x in sorted({x for x, _ in issues}):
            lot = [g for xx, g in issues if xx == x]
            r.mesures.append(
                mesure(D_CLUTCH_VICTOIRE, _pct(sum(lot), len(lot)), adversaires=x, n=len(lot))
            )
    return r


# --- CS-STR-01 : stratégie d'équipe -------------------------------------------------------


def strategie(d: DonneesMatch, rounds: list[Round]) -> ResultatAnalyse:
    r = ResultatAnalyse()
    miens, adverses = [], []  # (numero, site, gagné par l'équipe T)
    for rnd in rounds:
        site = site_depuis_lieu(_lieu_poseur(d, rnd)) if rnd.pose is not None else "aucune pose"
        if rnd.mon_equipe == 2:
            miens.append((rnd.numero, site, rnd.gagne))
        else:
            adverses.append((rnd.numero, site, None if rnd.gagne is None else not rnd.gagne))
    if miens:
        n = len(miens)
        for site in sorted({s for _, s, _ in miens}):
            lot = [g for _, s, g in miens if s == site]
            r.mesures.append(mesure(D_STR_POSES, _pct(len(lot), n), site=site, n=n))
            connus = [g for g in lot if g is not None]
            if connus:
                r.mesures.append(
                    mesure(D_STR_VICTOIRE, _pct(sum(connus), len(connus)), site=site, n=len(connus))
                )
        serie, plus_longue = 1, 1
        for (_, a, _), (_, b, _) in zip(miens, miens[1:], strict=False):
            serie = serie + 1 if a == b else 1
            plus_longue = max(plus_longue, serie)
        r.mesures.append(mesure(D_STR_REPETITION, plus_longue, n=n))
        resume = ", ".join(f"{num}:{site}" for num, site, _ in miens)
        r.preuves.append(
            Preuve(
                D_STR_POSES.nom,
                rounds[0].debut,
                f"Rounds T de l'équipe (round:site) : {resume}",
                None,
            )
        )
    if adverses:
        n = len(adverses)
        for site in sorted({s for _, s, _ in adverses}):
            lot = [s for _, s, _ in adverses if s == site]
            r.mesures.append(mesure(D_STR_ADVERSE, _pct(len(lot), n), site=site, n=n))
        resume = ", ".join(f"{num}:{site}" for num, site, _ in adverses)
        r.preuves.append(
            Preuve(
                D_STR_ADVERSE.nom,
                rounds[0].debut,
                f"Rounds T des adversaires (round:site) : {resume}",
                None,
            )
        )
    moities = (
        ("1", [x for x in rounds if x.numero <= ROUNDS_PAR_MOITIE]),
        ("2", [x for x in rounds if ROUNDS_PAR_MOITIE < x.numero <= 2 * ROUNDS_PAR_MOITIE]),
        ("prolongation", [x for x in rounds if x.numero > 2 * ROUNDS_PAR_MOITIE]),
    )
    for nom, lot in moities:
        connus = [x.gagne for x in lot if x.gagne is not None]
        if connus:
            r.mesures.append(
                mesure(D_STR_MOITIE, _pct(sum(connus), len(connus)), moitie=nom, n=len(connus))
            )
    return r


def analyser_decisions(d: DonneesMatch, pos: Positions | None = None) -> ResultatAnalyse:
    r = ResultatAnalyse()
    if d.est_deathmatch():
        return r
    pos = pos or Positions(d.ticks)
    rounds = decouper_rounds(d, pos)
    if not rounds:
        return r
    r.etendre(ouvertures(d, rounds))
    r.etendre(rotations(d, rounds, pos))
    r.etendre(saves(d, rounds))
    r.etendre(apres_pose_et_retakes(d, rounds))
    r.etendre(clutchs(d, rounds))
    r.etendre(strategie(d, rounds))
    return r
