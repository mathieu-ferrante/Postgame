"""Revoir un vrai moment dans CS2 : la démo jouée par le moteur du jeu, pas une animation.

Postgame ne pilote pas le jeu et ne touche à rien d'autre que les dossiers prévus pour
l'utilisateur. Pour revoir un moment (une de mes parties ou une démo pro), il prépare :

- une copie de la démo dans game/csgo/postgame/ (nom court, sans espace) ;
- game/csgo/cfg/postgame.cfg : définit l'alias « pg » puis lance `playdemo` ;
- game/csgo/cfg/postgame_aller.cfg : `demo_gototick` quelques secondes avant le moment,
  puis `spec_player` sur le joueur à suivre (moi, ou le pro qui lance le stuff) ;
- game/csgo/cfg/postgame_vue_<n>.cfg : `spec_player` sur chacun des joueurs, appelés par
  les alias v1, v2… pour voir le même moment par les yeux de n'importe qui.

En jeu : console → `exec postgame`, puis `pg` une fois la démo chargée. Hors du jeu, le
lien steam://run/730//+exec postgame/ démarre CS2 directement sur la démo.
Les commandes utilisées sont les commandes de démo standard du jeu.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from postgame.games.cs2.demo import TICKS_PAR_SECONDE

AVANCE_S = 5  # on arrive 5 s avant le moment pour voir ce qui l'amène
COPIES_GARDEES = 4  # copies de démos laissées dans game/csgo/postgame/
SOUS_DOSSIER = "postgame"


@dataclass
class Revoir:
    demo: Path  # copie jouée par CS2
    installe: bool  # True si écrit dans le vrai dossier du jeu
    commandes: list[str]  # à taper dans la console, dans l'ordre
    lien_steam: str
    tick: int
    joueur: str | None
    vues: list[tuple[str, str]] = field(default_factory=list)  # (alias, joueur)

    def en_dict(self) -> dict:
        return {
            "demo": str(self.demo),
            "installe": self.installe,
            "commandes": self.commandes,
            "lien_steam": self.lien_steam,
            "tick": self.tick,
            "joueur": self.joueur,
            "vues": [{"commande": c, "joueur": j} for c, j in self.vues],
        }


def dossier_csgo(dossiers_cs2: list[Path]) -> Path | None:
    """game/csgo du PC de jeu, retrouvé depuis les dossiers de démos configurés."""
    for d in dossiers_cs2:
        candidat = d.parent if d.name == "replays" else d
        if (candidat / "cfg").is_dir():
            return candidat
    return None


def _nettoyer(dossier: Path, garder: Path) -> None:
    copies = sorted(dossier.glob("*.dem"), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in [c for c in copies if c != garder][COPIES_GARDEES - 1 :]:
        f.unlink(missing_ok=True)


def _copier(demo: Path, dossier: Path, nom: str) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / f"{nom}.dem"
    if not (cible.exists() and cible.stat().st_size == demo.stat().st_size):
        try:
            # Lien physique si même disque : instantané et sans place en plus.
            cible.unlink(missing_ok=True)
            os.link(demo, cible)
        except OSError:
            shutil.copy2(demo, cible)
    os.utime(cible)
    _nettoyer(dossier, cible)
    return cible


def _texte_console(valeur: str) -> str:
    """Les guillemets ne s'échappent pas dans la console : on les retire."""
    return valeur.replace('"', "").replace(";", "").strip()


def preparer(
    demo: Path,
    tick: int,
    joueur: str | None,
    csgo: Path | None,
    repli: Path,
    nom: str,
    avance_s: float = AVANCE_S,
    joueurs: list[str] | None = None,
    pause: bool = False,
) -> Revoir:
    """Prépare la démo et les fichiers de commandes. `nom` : identifiant court (lettres et
    chiffres) de la copie. `repli` : dossier utilisé hors du PC de jeu. `joueurs` : tous
    ceux dont on veut pouvoir prendre la vue. `pause` : figer l'image (capture d'écran)."""
    if not demo.is_file():
        raise FileNotFoundError(f"démo introuvable : {demo}")
    if not nom.isalnum():
        raise ValueError("nom de copie : lettres et chiffres uniquement")
    racine = csgo if csgo is not None else repli
    copie = _copier(demo, racine / SOUS_DOSSIER, nom)
    cible = max(0, int(tick) - round(avance_s * TICKS_PAR_SECONDE))
    cfg = racine / "cfg"
    cfg.mkdir(parents=True, exist_ok=True)
    for ancien in cfg.glob("postgame_vue_*.cfg"):
        ancien.unlink()
    noms = list(dict.fromkeys(_texte_console(j) for j in (joueurs or []) if j and j.strip()))
    vues = []
    for i, j in enumerate(noms, start=1):
        (cfg / f"postgame_vue_{i}.cfg").write_text(f'spec_player "{j}"\n', encoding="utf-8")
        vues.append((f"v{i}", j))
    (cfg / "postgame.cfg").write_text(
        "// Écrit par Postgame. Ouvre la démo ; une fois chargée, tape « pg ».\n"
        'alias pg "exec postgame_aller"\n'
        + "".join(f'alias {c} "exec postgame_vue_{i}"\n' for i, (c, _) in enumerate(vues, 1))
        + f"playdemo {SOUS_DOSSIER}/{nom}\n",
        encoding="utf-8",
    )
    aller = [f"demo_gototick {cible}"]
    if joueur:
        aller.append(f'spec_player "{_texte_console(joueur)}"')
    if pause:
        aller.append("demo_pause")
    (cfg / "postgame_aller.cfg").write_text(
        "// Écrit par Postgame : va au moment choisi.\n" + "\n".join(aller) + "\n",
        encoding="utf-8",
    )
    return Revoir(
        demo=copie,
        installe=csgo is not None,
        commandes=["exec postgame", "pg"],
        lien_steam="steam://run/730//+exec postgame/",
        tick=cible,
        joueur=joueur,
        vues=vues,
    )


# --- Vrais moments pros -------------------------------------------------------------------

RAYON_PROCHE = 350.0  # unités : « même endroit » pour une situation pro équivalente
RAYON_LANCER = 150.0  # le pro lance depuis le même point que le stuff


def demos_pros(base) -> list[dict]:
    """Démos pros lues, avec leur emplacement : seules celles encore présentes se revoient."""
    with base.transaction() as cx:
        lignes = cx.execute(
            "SELECT empreinte, fichier, carte, chemin, ajoute_le FROM cs2_ref_demos "
            "ORDER BY carte, ajoute_le DESC"
        ).fetchall()
    return [
        {
            "empreinte": e,
            "fichier": f,
            "carte": c,
            "chemin": ch,
            "ajoute_le": a,
            "disponible": bool(ch) and Path(ch).is_file(),
        }
        for e, f, c, ch, a in lignes
    ]


def chemin_demo_pro(base, empreinte: str) -> Path | None:
    with base.transaction() as cx:
        ligne = cx.execute(
            "SELECT chemin FROM cs2_ref_demos WHERE empreinte = ?", (empreinte,)
        ).fetchone()
    return Path(ligne[0]) if ligne and ligne[0] else None


def _moments(lignes: list[tuple], disponibles: dict[str, dict], limite: int) -> list[dict]:
    """Un moment par (démo, round, joueur), le plus proche ; triés par distance."""
    vus: set[tuple] = set()
    sortie = []
    for empreinte, joueur, rnd, tick, lieu, distance in sorted(lignes, key=lambda r: r[5]):
        cle = (empreinte, rnd, joueur)
        if cle in vus or empreinte not in disponibles:
            continue
        vus.add(cle)
        demo = disponibles[empreinte]
        sortie.append(
            {
                "empreinte": empreinte,
                "demo": demo["fichier"],
                "joueur": joueur,
                "round": rnd,
                "tick": tick,
                "lieu": lieu,
                "distance": round(distance),
            }
        )
        if len(sortie) >= limite:
            break
    return sortie


def moments_proches(
    base,
    carte: str,
    camp: str | None,
    x: float,
    y: float,
    limite: int = 10,
    rayon: float = RAYON_PROCHE,
) -> list[dict]:
    """Vrais rounds pros où un joueur du même camp se tenait au même endroit."""
    disponibles = {d["empreinte"]: d for d in demos_pros(base) if d["disponible"]}
    if not disponibles:
        return []
    requete = (
        "SELECT empreinte, joueur, round, tick, lieu, x, y FROM cs2_ref_observations "
        "WHERE carte = ? AND genre IN ('lieu', 'position') AND tick IS NOT NULL "
        "AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?"
    )
    params: list = [carte, x - rayon, x + rayon, y - rayon, y + rayon]
    if camp:
        requete += " AND camp = ?"
        params.append(camp)
    with base.transaction() as cx:
        brutes = cx.execute(requete, params).fetchall()
    lignes = []
    for e, j, r, t, lieu, ox, oy in brutes:
        d = ((ox - x) ** 2 + (oy - y) ** 2) ** 0.5
        if d <= rayon:
            lignes.append((e, j, r, t, lieu, d))
    return _moments(lignes, disponibles, limite)


def exemples_stuff(base, cle: str, limite: int = 10) -> list[dict]:
    """Vrais lancers pros de ce stuff : même type, même arrivée, même point de lancer."""
    with base.transaction() as cx:
        stuff = cx.execute(
            "SELECT carte, type, x, y, lx, ly FROM cs2_ref_lancers WHERE cle = ?", (cle,)
        ).fetchone()
        if stuff is None:
            raise KeyError(cle)
        carte, type_, x, y, lx, ly = stuff
        brutes = cx.execute(
            "SELECT empreinte, joueur, round, tick, lieu, x, y, lx, ly FROM cs2_ref_observations "
            "WHERE carte = ? AND genre = 'lancer' AND type = ? AND tick IS NOT NULL",
            (carte, type_),
        ).fetchall()
    from postgame.games.cs2.references import RAYON_GROUPE

    disponibles = {d["empreinte"]: d for d in demos_pros(base) if d["disponible"]}
    lignes = []
    for e, j, r, t, lieu, ox, oy, olx, oly in brutes:
        arrivee = ((ox - x) ** 2 + (oy - y) ** 2) ** 0.5
        if arrivee > RAYON_GROUPE:
            continue
        if None not in (lx, ly, olx, oly):
            depart = ((olx - lx) ** 2 + (oly - ly) ** 2) ** 0.5
            if depart > RAYON_LANCER:
                continue
        else:
            depart = 0.0
        lignes.append((e, j, r, t, lieu, arrivee + depart))
    return _moments(lignes, disponibles, limite)


def joueurs_demo_pro(base, empreinte: str) -> list[str]:
    """Joueurs vus dans une démo pro (pour pouvoir prendre la vue de chacun)."""
    with base.transaction() as cx:
        lignes = cx.execute(
            "SELECT joueur FROM cs2_ref_observations WHERE empreinte = ? AND joueur IS NOT NULL "
            "GROUP BY joueur ORDER BY MIN(camp), joueur",
            (empreinte,),
        ).fetchall()
    return [j for (j,) in lignes]
