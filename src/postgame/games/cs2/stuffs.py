"""Apprendre les stuffs (lancers de grenades) de chaque carte (STUFF-01).

- Catalogue : les lancers de référence appris sur les démos pros (references.py), avec le
  point et l'angle de lancer, la part de lancers en sautant ou accroupi.
- Entraînement hors ligne : commandes `setpos` / `setang` pour se placer exactement au
  point de lancer dans une partie privée (sv_cheats 1, serveur local : rien d'autorisé en
  ligne n'est contourné).
- Maîtrise : chaque smoke de Mathieu en match est rattachée à un stuff ; on compte les
  tentatives (à moins de 400 u) et les réussites (à moins de 150 u).
- Notes de Mathieu, par carte ou par stuff.
- Révisions espacées (boîtes de Leitner : 1, 2, 4, 8, 16 jours) ; une smoke réussie en
  match vaut une révision réussie.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from postgame.db import Base, maintenant
from postgame.games.cs2.references import DISTANCE_RATEE, DISTANCE_RECONNUE

INTERVALLES_JOURS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
TYPES = {"smoke": "Smoke", "flash": "Flash", "molotov": "Molotov"}

CONFIG_ENTRAINEMENT = (
    "sv_cheats 1; mp_warmup_end; mp_freezetime 0; mp_roundtime_defuse 60; "
    "mp_buy_anywhere 1; mp_maxmoney 60000; mp_startmoney 60000; sv_infinite_ammo 1; "
    "ammo_grenade_limit_total 5; sv_grenade_trajectory_prac_pipreview 1; "
    "sv_showimpacts 1; bot_kick; mp_restartgame 1"
)


def commandes(stuff: dict[str, Any]) -> str | None:
    """Commande console qui place exactement au point de lancer, regard compris."""
    if stuff.get("lx") is None or stuff.get("lpitch") is None:
        return None
    return (
        f"setpos {stuff['lx']:.2f} {stuff['ly']:.2f} {stuff['lz']:.2f}; "
        f"setang {stuff['lpitch']:.2f} {stuff['lyaw']:.2f} 0"
    )


def technique(stuff: dict[str, Any]) -> str:
    if stuff.get("technique"):
        part = stuff.get("part_technique")
        return stuff["technique"] + (f" ({round(100 * part)} % des pros)" if part else "")
    morceaux = []
    if (stuff.get("part_saut") or 0) >= 0.5:
        morceaux.append("en sautant (jumpthrow)")
    if (stuff.get("part_accroupi") or 0) >= 0.5:
        morceaux.append("accroupi")
    return ", ".join(morceaux) or "debout, sans sauter"


def nom(stuff: dict[str, Any]) -> str:
    depuis = f" depuis {stuff['lieu_lancer']}" if stuff.get("lieu_lancer") else ""
    return f"{TYPES.get(stuff['type'], stuff['type'])} {stuff.get('lieu_arrivee') or '?'}{depuis}"


# --- Captures d'écran jointes par Mathieu -------------------------------------------------

FORMATS_IMAGE = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def dossier_images(dossier_donnees: Path) -> Path:
    return dossier_donnees / "stuffs_images"


def chemin_image(dossier_donnees: Path, cle: str) -> Path | None:
    for ext in FORMATS_IMAGE:
        f = dossier_images(dossier_donnees) / f"{cle}{ext}"
        if f.exists():
            return f
    return None


def enregistrer_image(dossier_donnees: Path, cle: str, nom_fichier: str, contenu: bytes) -> Path:
    ext = Path(nom_fichier).suffix.lower()
    if ext not in FORMATS_IMAGE or not cle.isalnum():
        raise ValueError("image attendue : png, jpg ou webp")
    ancienne = chemin_image(dossier_donnees, cle)
    if ancienne:
        ancienne.unlink()
    dossier_images(dossier_donnees).mkdir(parents=True, exist_ok=True)
    cible = dossier_images(dossier_donnees) / f"{cle}{ext}"
    cible.write_bytes(contenu)
    return cible


# --- Maîtrise en match -------------------------------------------------------------------


def maitrise(base: Base, carte: str) -> dict[str, dict[str, Any]]:
    """Par stuff : tentatives, réussites, dernier écart, date de la dernière réussite."""
    resultat: dict[str, dict[str, Any]] = {}
    for p in base.preuves_toutes_parties("cs2.smoke.part_reconnues", "cs2"):
        cle = p["donnees"].get("stuff")
        ecart = p["donnees"].get("ecart")
        if p["carte"] != carte or not cle or ecart is None or ecart > DISTANCE_RATEE:
            continue
        m = resultat.setdefault(
            cle, {"tentatives": 0, "reussites": 0, "dernier_ecart": None, "derniere_reussite": None}
        )
        m["tentatives"] += 1
        m["dernier_ecart"] = ecart
        if ecart <= DISTANCE_RECONNUE:
            m["reussites"] += 1
            m["derniere_reussite"] = p["date_partie"][:10]
    return resultat


# --- Notes --------------------------------------------------------------------------------


def notes(base: Base, carte: str, jeu: str = "cs2") -> list[dict[str, Any]]:
    with base.transaction() as cx:
        lignes = cx.execute(
            "SELECT * FROM notes WHERE jeu = ? AND carte = ? ORDER BY maj_le DESC", (jeu, carte)
        ).fetchall()
    return [dict(lg) for lg in lignes]


def ajouter_note(
    base: Base, carte: str, texte: str, stuff: str | None = None, jeu: str = "cs2"
) -> int:
    horodatage = maintenant()
    with base.transaction() as cx:
        cur = cx.execute(
            "INSERT INTO notes (jeu, carte, stuff, texte, cree_le, maj_le) VALUES "
            "(?, ?, ?, ?, ?, ?)",
            (jeu, carte, stuff, texte, horodatage, horodatage),
        )
        return cur.lastrowid


def modifier_note(base: Base, note_id: int, texte: str) -> bool:
    with base.transaction() as cx:
        return (
            cx.execute(
                "UPDATE notes SET texte = ?, maj_le = ? WHERE id = ?",
                (texte, maintenant(), note_id),
            ).rowcount
            > 0
        )


def supprimer_note(base: Base, note_id: int) -> bool:
    with base.transaction() as cx:
        return cx.execute("DELETE FROM notes WHERE id = ?", (note_id,)).rowcount > 0


# --- Révisions espacées --------------------------------------------------------------------


def noter_revision(
    base: Base, stuff: str, reussi: bool, jour: date | None = None
) -> dict[str, Any]:
    jour = jour or date.today()
    with base.transaction() as cx:
        ligne = cx.execute("SELECT * FROM revisions WHERE stuff = ?", (stuff,)).fetchone()
        boite = int(ligne["boite"]) if ligne else 1
        boite = min(5, boite + 1) if reussi and ligne else (1 if not reussi else 2)
        prochaine = (jour + timedelta(days=INTERVALLES_JOURS[boite])).isoformat()
        cx.execute(
            "INSERT INTO revisions (stuff, boite, prochaine, derniere, reussites, echecs) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (stuff) DO UPDATE SET boite = excluded.boite, "
            "prochaine = excluded.prochaine, derniere = excluded.derniere, "
            "reussites = revisions.reussites + excluded.reussites, "
            "echecs = revisions.echecs + excluded.echecs",
            (stuff, boite, prochaine, jour.isoformat(), int(reussi), int(not reussi)),
        )
    return {"stuff": stuff, "boite": boite, "prochaine": prochaine}


def revisions(base: Base) -> dict[str, dict[str, Any]]:
    with base.transaction() as cx:
        return {r["stuff"]: dict(r) for r in cx.execute("SELECT * FROM revisions").fetchall()}


# --- Vue complète d'une carte -------------------------------------------------------------


def stuffs_carte(base: Base, carte: str) -> list[dict[str, Any]]:
    with base.transaction() as cx:
        refs = pd.read_sql_query(
            "SELECT * FROM cs2_ref_lancers WHERE carte = ? ORDER BY nb DESC", cx, params=(carte,)
        )
    m = maitrise(base, carte)
    vols = trajectoires_exemples(base, carte)
    rev = revisions(base)
    toutes_notes = notes(base, carte)
    sortie = []
    for _, r in refs.iterrows():
        s = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
        cle = s.get("cle")
        image = chemin_image(base.chemin.parent, cle) if cle else None
        s.update(
            trajectoire=vols.get((s.get("exemple_empreinte"), s.get("exemple_tick"))),
            image=f"/api/cs2/stuffs/{cle}/image" if image else None,
            nom=nom(s),
            commandes=commandes(s),
            technique=technique(s),
            maitrise=m.get(
                cle,
                {"tentatives": 0, "reussites": 0, "dernier_ecart": None, "derniere_reussite": None},
            ),
            revision=rev.get(cle),
            notes=[n for n in toutes_notes if n["stuff"] == cle],
        )
        sortie.append(s)
    return sortie


def a_reviser(
    base: Base, carte: str, nombre: int = 5, jour: date | None = None
) -> list[dict[str, Any]]:
    """Stuffs à revoir aujourd'hui : en retard d'abord, puis jamais vus (les plus joués par
    les pros en premier). Un stuff réussi en match depuis la dernière révision est sauté."""
    jour = (jour or date.today()).isoformat()
    candidats = []
    for s in stuffs_carte(base, carte):
        rev, m = s["revision"], s["maitrise"]
        if rev and rev["prochaine"] > jour:
            continue
        if rev and m["derniere_reussite"] and m["derniere_reussite"] >= (rev["derniere"] or ""):
            continue
        priorite = (0, rev["prochaine"]) if rev else (1, -(s.get("nb") or 0))
        candidats.append((priorite, s))
    candidats.sort(key=lambda c: c[0])
    return [s for _, s in candidats[:nombre]]


def trajectoires_exemples(base: Base, carte: str) -> dict[tuple[str, int], list]:
    """Trajectoire réelle (relevée dans la démo) du lancer pro qui sert d'exemple à chaque
    stuff : [[tick, x, y, z], …]."""
    with base.transaction() as cx:
        lignes = cx.execute(
            "SELECT o.empreinte, o.tick, o.trajectoire FROM cs2_ref_observations o "
            "JOIN cs2_ref_lancers l ON l.exemple_empreinte = o.empreinte "
            "AND l.exemple_tick = o.tick WHERE l.carte = ? AND o.genre = 'lancer' "
            "AND o.trajectoire IS NOT NULL",
            (carte,),
        ).fetchall()
    return {(e, int(t)): json.loads(v) for e, t, v in lignes}
