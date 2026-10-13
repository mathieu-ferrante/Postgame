"""Ligne de commande : `python -m postgame <commande>`.

- serve       : lance le service (API + surveillance des dossiers)
- importer    : importe un ou plusieurs fichiers à la main
- parties     : liste les parties en base
- reanalyser  : recalcule fiches et mesures de tout l'historique (COM-08)
- references  : ajoute des démos pros au catalogue CS2 (lancers et positions de référence)
- debrief     : (re)génère le débrief d'une partie
- fiabilite   : marque une mesure vérifiée à la main (elle entre alors dans le débrief)
- couts       : coût cumulé des débriefs rédigés
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

    p_ref = sous.add_parser("references", help="catalogue CS2 appris sur démos pros")
    sous_ref = p_ref.add_subparsers(dest="action", required=True)
    p_ref_aj = sous_ref.add_parser("ajouter", help="ajoute des démos pros (fichiers ou dossiers)")
    p_ref_aj.add_argument("chemins", nargs="+", type=Path)
    sous_ref.add_parser("reconstruire", help="recalcule le catalogue à partir des observations")
    sous_ref.add_parser("lister", help="résumé du catalogue par carte")

    p_deb = sous.add_parser("debrief", help="(re)génère le débrief d'une partie")
    p_deb.add_argument("partie_id", type=int)
    p_deb.add_argument("--sans-modele", action="store_true", help="débrief structuré seul")

    p_fiab = sous.add_parser("fiabilite", help="marque une mesure vérifiée à la main")
    p_fiab.add_argument("nom")
    p_fiab.add_argument("--non", action="store_true", help="la marquer non fiable")
    p_fiab.add_argument("--note", default="")

    sous.add_parser("couts", help="coût cumulé des débriefs rédigés")

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
        tls = {}
        if cfg.certificat and cfg.cle_privee:
            tls = {"ssl_certfile": str(cfg.certificat), "ssl_keyfile": str(cfg.cle_privee)}
        uvicorn.run(app, host=cfg.hote, port=cfg.port, **tls)
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

    if args.commande == "references":
        from postgame.games.cs2 import references

        if args.action == "ajouter":
            demos = []
            for chemin in args.chemins:
                demos += sorted(chemin.glob("*.dem")) if chemin.is_dir() else [chemin]
            for demo in demos:
                try:
                    print(f"{demo.name} : {references.ajouter_demo_pro(base, demo)}")
                except Exception as exc:  # une démo pro illisible ne bloque pas les autres
                    print(f"{demo.name} : erreur — {exc}")
            print(references.reconstruire_catalogue(base))
        elif args.action == "reconstruire":
            print(references.reconstruire_catalogue(base))
        for ligne in references.resume_catalogue(base):
            print(
                f"{ligne['carte']:<14} {ligne['demos']} démo(s), {ligne['lancers']} lancers, "
                f"{ligne['positions']} positions"
            )
        return 0

    if args.commande == "debrief":
        from postgame.debrief import generer_debrief

        d = generer_debrief(base, cfg, args.partie_id, None if args.sans_modele else "config")
        print(d["texte"])
        print(
            f"\n[{d['statut']}] {d['fournisseur']} {d['modele']} — "
            f"{d['jetons_entree']} + {d['jetons_sortie']} jetons, {d['cout']:.5f} $"
            + (f" — {d['message']}" if d["message"] else "")
        )
        return 0

    if args.commande == "fiabilite":
        from postgame.debrief.constats import charger_definitions
        from postgame.mesures import DEFINITIONS

        charger_definitions()
        definition = DEFINITIONS.get(args.nom)
        if definition is None:
            print(f"mesure inconnue : {args.nom}")
            return 1
        base.noter_fiabilite(definition.nom, definition.version, not args.non, args.note)
        print(f"{definition.nom} v{definition.version} : {'non ' if args.non else ''}fiable")
        return 0

    if args.commande == "couts":
        c = base.couts_debriefs()
        print(
            f"{c['nb']} débrief(s), {c['entree']} + {c['sortie']} jetons, "
            f"{c['total']:.4f} $ au total, {c['moyen']:.5f} $ par débrief rédigé"
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
