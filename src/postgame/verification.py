"""Fiche de vérification manuelle des mesures d'une partie (NF-06).

Pour chaque mesure qui a des preuves, liste jusqu'à 5 moments avec la commande CS2 pour
s'y rendre dans le lecteur de démos du jeu. Mathieu coche ce qu'il constate ; une mesure
dont les 5 cas sont confirmés peut passer `fiable=True`.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from postgame.db import Base
from postgame.mesures import DEFINITIONS

NB_CAS = 5


def fiche_verification(base: Base, partie_id: int) -> str:
    partie = base.partie(partie_id)
    if partie is None:
        raise ValueError(f"partie {partie_id} inconnue")
    par_mesure: dict[str, list[dict]] = defaultdict(list)
    for preuve in base.preuves_partie(partie_id):
        par_mesure[preuve["mesure"]].append(preuve)
    valeurs = defaultdict(list)
    for m in base.mesures_partie(partie_id):
        valeurs[m["nom"]].append(m)

    demo = Path(partie.fichier)
    lignes = [
        f"# Vérification des mesures — partie {partie_id}",
        "",
        f"- Jeu : {partie.jeu} · carte : {partie.carte} · mode : {partie.mode} · "
        f"date : {partie.date_partie}",
        f"- Démo archivée : `{demo}`",
        "",
        'Dans CS2 (console) : `playdemo "<chemin de la démo>"`, puis pour chaque cas '
        "`demo_gototick <tick>` et regarder depuis les yeux de Mathieu. Cocher si le constat "
        "est juste ; sinon noter ce qui est vu à la place.",
        "",
        "> Si le moment affiché est décalé de quelques secondes partout, le noter : les ticks "
        "de demoparser2 et ceux du lecteur du jeu peuvent avoir un décalage constant.",
        "",
    ]
    for nom in sorted(par_mesure):
        definition = DEFINITIONS.get(nom)
        lignes.append(f"## {nom}")
        if definition:
            lignes.append(f"_{definition.description}_ (v{definition.version})")
        globales = [
            m
            for m in valeurs.get(nom, [])
            if not m["contexte"].get("arme") and not m["contexte"].get("tranche")
        ]
        if globales:
            g = globales[0]
            lignes.append(
                f"Valeur sur la partie : **{g['valeur']} {g['unite']}** "
                f"(échantillon : {g['contexte'].get('n', '?')})"
            )
        lignes.append("")
        for p in par_mesure[nom][:NB_CAS]:
            rnd = f"round {p['round']}, " if p["round"] is not None else ""
            lignes.append(
                f"- [ ] {rnd}tick {p['tick']} — {p['texte']} (`demo_gototick {p['tick']}`)"
            )
        lignes.append("")
    if not par_mesure:
        lignes.append("Aucune preuve enregistrée pour cette partie.")
    return "\n".join(lignes)
