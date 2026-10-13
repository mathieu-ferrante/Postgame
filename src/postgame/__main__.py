"""Ligne de commande : `python -m postgame <commande>`.

- serve       : lance le service (API + surveillance des dossiers)
- importer    : importe un ou plusieurs fichiers à la main
- parties     : liste les parties en base
- reanalyser  : recalcule fiches et mesures de tout l'historique (COM-08)
- verifier    : fiche de vérification manuelle des mesures d'une partie (5 cas par mesure)
- diagnostic  : décrit une démo CS2 (en-tête, évènements, fiche) dans un fichier JSON
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from postgame.config import charger_config
from postgame.db import Base


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="postgame", description="Coach personnel multi-jeux")
    parser.add_argument("--config", type=Path, help="fichier de configuration (postgame.toml)")
    sous = parser.add_subparsers(dest="commande", required=True)

    p_serve = sous.add_parser("serve", help="lance le service")
    p_serve.add_argument(
        "--sans-surveillance", action="store_true", help="ne pas surveiller les dossiers de démos"
    )

    p_imp = sous.add_parser("importer", help="importe des fichiers")
    p_imp.add_argument("fichiers", nargs="+", type=Path)

    p_list = sous.add_parser("parties", help="liste les parties")
    p_list.add_argument("--jeu")
    p_list.add_argument("--limite", type=int, default=20)

    p_re = sous.add_parser("reanalyser", help="recalcule tout l'historique")
    p_re.add_argument("--jeu")

    p_verif = sous.add_parser("verifier", help="fiche de vérification manuelle d'une partie")
    p_verif.add_argument("partie_id", type=int)
    p_verif.add_argument("--sortie", type=Path)

    p_diag = sous.add_parser("diagnostic", help="décrit une démo CS2 dans un fichier JSON")
    p_diag.add_argument("demo", type=Path)
    p_diag.add_argument("--sortie", type=Path)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s"
    )
    cfg = charger_config(args.config)

    if args.commande == "serve":
        import uvicorn

        from postgame.api import creer_app

        app = creer_app(cfg, surveiller=not args.sans_surveillance)
        uvicorn.run(app, host=cfg.hote, port=cfg.port)
        return 0

    if args.commande == "diagnostic":
        from postgame.games.cs2.diagnostic import diagnostiquer

        rapport = diagnostiquer(args.demo, cfg.steamid)
        sortie = args.sortie or args.demo.with_suffix(".diagnostic.json")
        sortie.write_text(
            json.dumps(rapport, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(f"Diagnostic écrit dans {sortie}")
        print(json.dumps(rapport.get("fiche"), ensure_ascii=False, indent=2, default=str))
        return 0

    base = Base(cfg.chemin_base)
    if args.commande == "importer":
        from postgame.importation import importer

        code = 0
        for chemin in args.fichiers:
            res = importer(chemin, base, cfg)
            print(f"{chemin.name} : {res.statut} — {res.message} (partie {res.partie_id})")
            code |= res.statut == "erreur"
        return code

    if args.commande == "parties":
        for p in base.lister_parties(jeu=args.jeu, limite=args.limite):
            score = f"{p.score_joueur}-{p.score_adverse}" if p.score_joueur is not None else ""
            print(
                f"#{p.id:<5} {p.date_partie[:16]}  {p.jeu:<4} {p.mode:<11} {p.carte:<14} "
                f"{p.resultat:<10} {score}"
            )
        return 0

    if args.commande == "verifier":
        from postgame.games.cs2 import mecanique  # noqa: F401  (définitions des mesures)
        from postgame.verification import fiche_verification

        texte = fiche_verification(base, args.partie_id)
        sortie = (
            args.sortie or cfg.dossier_donnees / "verifications" / f"partie_{args.partie_id}.md"
        )
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_text(texte, encoding="utf-8")
        print(f"Fiche de vérification écrite dans {sortie}")
        return 0

    if args.commande == "reanalyser":
        from postgame.importation import reanalyser

        print(reanalyser(base, cfg, args.jeu))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
