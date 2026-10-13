"""Remplit une base de DÉMONSTRATION pour essayer l'interface sans vraie démo.

DONNÉES DE SUBSTITUTION : parties et matchs entièrement simulés. Rien ici ne décrit le jeu
de Mathieu. Toutes les parties portent la source « DEMONSTRATION ».

Usage : .venv\\Scripts\\python scripts\\donnees_demo.py data_demo
puis   : .venv\\Scripts\\python -m postgame --config data_demo\\postgame.toml serve
"""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from postgame.config import Config
from postgame.db import Base, Mesure, Partie
from postgame.debrief import generer_debrief
from postgame.games.cs2.analyse import analyser_match
from postgame.games.cs2.donnees import COLONNES_TICKS, DonneesMatch, construire_rounds
from postgame.games.cs2.replay import chemin_cache, construire_replay, ecrire_cache
from postgame.importation import enregistrer_analyse, importer

SOURCE = "DEMONSTRATION"
MOI = "76561190000000000"
NOMS = [
    "Mathieu",
    "Alpha",
    "Bravo",
    "Charlie",
    "Delta",
    "Echo",
    "Foxtrot",
    "Golf",
    "Hotel",
    "India",
]


def simuler_match(graine: int, nb_rounds: int = 6) -> DonneesMatch:
    """Match 5v5 grossièrement plausible sur l'emprise de de_mirage."""
    rng = random.Random(graine)
    joueurs = [MOI] + [f"7656119000000{i:04d}" for i in range(1, 10)]
    duree, pause = 64 * 45, 64 * 8
    lignes, tirs, degats, morts, debuts, fins, gagnants = [], [], [], [], [], [], {}
    t0 = 0
    for _ in range(nb_rounds):
        debut, fin = t0 + pause, t0 + pause + duree
        debuts.append(debut)
        fins.append(fin)
        etats = {}
        for i, sid in enumerate(joueurs):
            equipe = 2 if i < 5 else 3
            depart = (1200.0, 0.0) if equipe == 2 else (-1800.0, -1800.0)
            etats[sid] = {
                "x": depart[0] + rng.uniform(-150, 150),
                "y": depart[1] + rng.uniform(-150, 150),
                "cap": rng.uniform(0, 360),
                "vivant": True,
                "equipe": equipe,
            }
        cible = {2: (-1200.0, -1300.0), 3: (-300.0, -600.0)}
        for t in range(t0, fin + 1):
            for i, sid in enumerate(joueurs):
                e = etats[sid]
                if e["vivant"] and t >= debut:
                    cx, cy = cible[e["equipe"]]
                    angle = math.atan2(cy - e["y"], cx - e["x"]) + rng.uniform(-0.6, 0.6)
                    vitesse = rng.choice([0, 120, 230]) / 64
                    e["x"] += math.cos(angle) * vitesse
                    e["y"] += math.sin(angle) * vitesse
                    e["cap"] = math.degrees(angle) + rng.uniform(-20, 20)
                if t % 2 == 0 or sid == MOI:
                    lignes.append(
                        {
                            "tick": t,
                            "steamid": sid,
                            "nom": NOMS[i],
                            "equipe": e["equipe"],
                            "x": e["x"],
                            "y": e["y"],
                            "z": 0.0,
                            "vx": rng.uniform(-60, 60)
                            if rng.random() < 0.6
                            else rng.uniform(-230, 230),
                            "vy": rng.uniform(-60, 60),
                            "pitch": rng.uniform(-3, 8),
                            "yaw": e["cap"],
                            "vivant": e["vivant"],
                            "accroupi": False,
                            "arme": "ak47" if e["equipe"] == 2 else "m4a1",
                            "vu_par_moi": e["equipe"] == 3 and e["vivant"] and rng.random() < 0.15,
                            "punch_pitch": 0.0,
                            "punch_yaw": 0.0,
                            "lunette": False,
                            "en_l_air": False,
                        }
                    )
            if t > debut + 64 * 10 and rng.random() < 0.004:
                vivants = [s for s in joueurs if etats[s]["vivant"]]
                tireur = rng.choice(vivants)
                adverses = [s for s in vivants if etats[s]["equipe"] != etats[tireur]["equipe"]]
                if adverses:
                    victime = rng.choice(adverses)
                    arme = "ak47" if etats[tireur]["equipe"] == 2 else "m4a1"
                    for k in range(rng.randint(1, 6)):
                        tirs.append({"tick": t + 6 * k, "steamid": tireur, "arme": arme})
                    degats.append(
                        {
                            "tick": t,
                            "attaquant": tireur,
                            "victime": victime,
                            "arme": arme,
                            "degats": 100.0,
                            "zone": "tete" if rng.random() < 0.4 else "torse",
                        }
                    )
                    morts.append(
                        {
                            "tick": t,
                            "attaquant": tireur,
                            "victime": victime,
                            "arme": arme,
                            "headshot": rng.random() < 0.4,
                        }
                    )
                    etats[victime]["vivant"] = False
        gagnants[fin] = rng.choice([2, 3])
        t0 = fin + 1
    ticks = pd.DataFrame(lignes)
    # Les joueurs autres que Mathieu ne sont échantillonnés qu'un tick sur deux : on complète.
    ticks = (
        ticks.set_index(["steamid", "tick"])
        .groupby(level=0, group_keys=False)
        .apply(
            lambda g: (
                g.reset_index(level=0, drop=True)
                .reindex(
                    range(g.index.get_level_values(1).min(), g.index.get_level_values(1).max() + 1)
                )
                .ffill()
                .assign(steamid=g.index.get_level_values(0)[0])
            )
        )
        .reset_index()
        .rename(columns={"index": "tick"})
    )
    ticks = ticks[COLONNES_TICKS].sort_values(["tick", "steamid"]).reset_index(drop=True)
    ticks["vivant"] = ticks["vivant"].astype(bool)
    ticks["vu_par_moi"] = ticks["vu_par_moi"].astype(bool)
    ticks["accroupi"] = ticks["accroupi"].astype(bool)
    ticks["lunette"] = ticks["lunette"].astype(bool)
    ticks["en_l_air"] = ticks["en_l_air"].astype(bool)
    return DonneesMatch(
        moi=MOI,
        ticks=ticks,
        tirs=pd.DataFrame(tirs, columns=["tick", "steamid", "arme"]),
        degats=pd.DataFrame(
            degats, columns=["tick", "attaquant", "victime", "arme", "degats", "zone"]
        ),
        morts=pd.DataFrame(morts, columns=["tick", "attaquant", "victime", "arme", "headshot"]),
        rounds=construire_rounds(debuts, fins, gagnants),
        carte="de_mirage",
    )


def simuler_seance_gd(graine: int) -> list[str]:
    """Séance Geometry Dash simulée : 45 essais normaux puis entraînement puis 15 normaux."""
    rng = random.Random(graine)
    vitesse, longueur = 0.311, 6000.0
    inputs = []
    x = 250.0
    while x < longueur - 200:
        inputs.append((x, rng.choice([6, 9, 14, 22, 35])))  # (position, écart-type en ms)
        x += rng.uniform(90, 420)
    lignes = [
        {
            "type": "session",
            "format": 1,
            "debut": datetime.now().replace(microsecond=0).isoformat(),
            "niveau": {"id": 123456, "nom": "Niveau simulé (DÉMO)", "createur": "demo"},
            "plateforme": False,
            "mod": "v1.0.0",
        }
    ]
    t = 0.0
    plan = ["normal"] * 45 + ["practice"] * 12 + ["normal"] * 15
    for n, mode in enumerate(plan, start=1):
        x0 = 0.0 if mode == "normal" else rng.choice([0.0, 2000.0, 3500.0])
        lignes.append({"type": "essai", "n": n, "mode": mode, "t": t, "x": x0})
        mort_x = longueur
        evenements = []
        for xi, ecart in inputs:
            if xi < x0:
                continue
            decalage = rng.gauss(rng.choice([-3, 0, 4]), ecart)
            tp = t + (xi - x0) / vitesse + decalage
            evenements.append(
                {
                    "type": "input",
                    "t": round(tp, 2),
                    "x": round(x0 + vitesse * (tp - t), 1),
                    "appui": True,
                    "j": 1,
                }
            )
            if abs(decalage) > 28 and rng.random() < 0.6:
                mort_x = xi + rng.uniform(10, 60)
                break
        duree = (mort_x - x0) / vitesse
        for k in range(0, int(duree), 30):
            evenements.append(
                {"type": "pos", "t": round(t + k, 2), "x": round(x0 + vitesse * k, 1)}
            )
        lignes += sorted(evenements, key=lambda e: e["t"])
        if mort_x < longueur:
            lignes.append(
                {
                    "type": "mort",
                    "t": round(t + duree, 2),
                    "x": round(mort_x, 1),
                    "pct": round(100 * mort_x / longueur, 2),
                    "objet": 8,
                }
            )
        else:
            lignes.append({"type": "fin", "t": round(t + duree, 2), "pct": 100, "complete": True})
        t += duree + 1500
    lignes.append({"type": "fin_session", "t": t})
    return [json.dumps(ligne, ensure_ascii=False) for ligne in lignes]


def main(dossier: Path) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "postgame.toml").write_text(
        '# Base de DÉMONSTRATION (données simulées)\n[service]\nhote = "127.0.0.1"\n'
        'port = 8765\ndossier_donnees = "."\n[cs2]\ndossiers_demos = []\n'
        '[debrief]\nfournisseur = "aucun"\nmesures_experimentales = true\n',
        encoding="utf-8",
    )
    cfg = Config(dossier_donnees=dossier, dossiers_cs2=[])
    cfg.debrief.fournisseur = "aucun"
    cfg.debrief.mesures_experimentales = True
    base = Base(cfg.chemin_base)
    maintenant = datetime.now(UTC)
    rng = random.Random(1)
    # Historique : 7 parties avec quelques mesures qui progressent doucement.
    for i in range(7):
        date = (maintenant - timedelta(days=20 - 3 * i)).isoformat(timespec="seconds")
        pid = base.ajouter_partie(
            Partie(
                jeu="cs2",
                date_partie=date,
                mode="competitif",
                carte=rng.choice(["de_mirage", "de_inferno", "de_ancient"]),
                resultat=rng.choice(["victoire", "defaite"]),
                score_joueur=13,
                score_adverse=rng.randint(5, 12),
                duree_s=2300,
                source=SOURCE,
                fichier=SOURCE,
                empreinte=f"demo{i:060d}",
            )
        )
        base.remplacer_mesures(
            pid,
            [
                Mesure(
                    "cs2.contre_strafe.part_premieres_balles_precises",
                    1,
                    55 + 2.5 * i + rng.uniform(-4, 4),
                    "%",
                    {"n": 60},
                ),
                Mesure(
                    "cs2.viseur.ecart_median", 1, 11 - 0.6 * i + rng.uniform(-1, 1), "°", {"n": 80}
                ),
                Mesure(
                    "cs2.trades.part_tradables_non_tradees",
                    1,
                    50 - 2 * i + rng.uniform(-8, 8),
                    "%",
                    {"n": 10},
                ),
            ],
        )
    # Partie récente : match simulé passé dans le vrai pipeline d'analyse et de replay.
    d = simuler_match(42)
    pid = base.ajouter_partie(
        Partie(
            jeu="cs2",
            date_partie=maintenant.isoformat(timespec="seconds"),
            mode="competitif",
            carte="de_mirage",
            resultat="defaite",
            score_joueur=3,
            score_adverse=3,
            duree_s=330,
            source=SOURCE,
            fichier=SOURCE,
            empreinte="demo" + "f" * 60,
            details={"avertissement": "match simulé (données de démonstration)"},
        )
    )
    enregistrer_analyse(base, pid, analyser_match(d))
    ecrire_cache(chemin_cache(cfg.dossier_donnees, pid), construire_replay(d))
    generer_debrief(base, cfg, pid, None)
    # Stuffs simulés sur de_mirage (catalogue normalement appris sur démos pros).
    with base.transaction() as cx:
        for i, (tp, x, y, lx, ly, arrivee, depart) in enumerate(
            [
                ("smoke", -400, -1250, -1150, 100, "Window (DÉMO)", "TSpawn"),
                ("smoke", -980, -900, -1150, 100, "Jungle (DÉMO)", "TSpawn"),
                ("smoke", -300, -2000, -1600, -700, "CT (DÉMO)", "Palace"),
                ("flash", -900, -1500, -1000, -400, "Ramp (DÉMO)", "Tetris"),
                ("molotov", -1700, -1800, -1300, -500, "Bench (DÉMO)", "Ramp"),
            ]
        ):
            cx.execute(
                "INSERT INTO cs2_ref_lancers (carte, type, x, y, z, lx, ly, lz, lieu_arrivee, "
                "lieu_lancer, nb, nb_demos, lpitch, lyaw, part_saut, part_accroupi, cle, "
                "construit_le) VALUES ('de_mirage', ?, ?, ?, 0, ?, ?, -160, ?, ?, ?, 3, -12.5, "
                "-48.2, ?, 0, ?, 'demo')",
                (tp, x, y, lx, ly, arrivee, depart, 20 - i, 1.0 if i == 0 else 0.0, f"demo{i}"),
            )
    # Démo pro SIMULÉE (faux fichier, illisible par CS2) : sert à montrer les listes
    # « Les pros au même endroit » et « Le voir lancé par un pro ».
    faux_pro = dossier / "pros" / "SIMULEE-pas-une-vraie-demo.dem"
    faux_pro.parent.mkdir(parents=True, exist_ok=True)
    faux_pro.write_bytes(b"DEMO SIMULEE")
    pros = ["ZywOo (DÉMO)", "donk (DÉMO)", "m0NESY (DÉMO)", "ropz (DÉMO)"]
    echantillon = d.ticks[d.ticks["vivant"]].sample(800, random_state=3)
    with base.transaction() as cx:
        cx.execute(
            "INSERT INTO cs2_ref_demos (empreinte, fichier, carte, ajoute_le, chemin) "
            "VALUES ('simulee0000', ?, 'de_mirage', 'demo', ?)",
            (faux_pro.name, str(faux_pro.resolve())),
        )
        for k, (_, e) in enumerate(echantillon.iterrows()):
            cx.execute(
                "INSERT INTO cs2_ref_observations (empreinte, carte, genre, camp, lieu, x, y, z, "
                "tick, joueur, round) VALUES ('simulee0000', 'de_mirage', 'lieu', ?, 'DÉMO', ?, "
                "?, 0, ?, ?, ?)",
                (
                    "T" if int(e["equipe"]) == 2 else "CT",
                    float(e["x"]),
                    float(e["y"]),
                    int(e["tick"]),
                    pros[k % 4],
                    1 + k % 6,
                ),
            )
        for k in range(3):
            cx.execute(
                "INSERT INTO cs2_ref_observations (empreinte, carte, genre, type, camp, lieu, x, "
                "y, z, lx, ly, tick, joueur, round) VALUES ('simulee0000', 'de_mirage', 'lancer', "
                "'smoke', 'T', 'TSpawn', -400, -1250, 0, -1150, 100, ?, ?, ?)",
                (2000 + 9000 * k, pros[k], 2 + 4 * k),
            )
    # Séance Geometry Dash simulée, importée par le chemin normal (lecture + analyses).
    journal = dossier / "gd" / "demo.gdsession"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text("\n".join(simuler_seance_gd(7)), encoding="utf-8")
    importer(journal, base, cfg)
    print(f"Base de démonstration prête dans {dossier} ({base.compter_parties()} parties).")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "data_demo"))
