"""Stockage local SQLite : parties (fiches), mesures, fichiers vus par la surveillance.

Le schéma est versionné : chaque migration est une liste d'instructions SQL appliquée une
seule fois, dans l'ordre. Ne jamais modifier une migration déjà publiée : en ajouter une.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MIGRATIONS: list[list[str]] = [
    # 1 — socle (L0)
    [
        """
        CREATE TABLE parties (
            id            INTEGER PRIMARY KEY,
            jeu           TEXT NOT NULL,          -- cs2, gd, lol, tft
            date_partie   TEXT NOT NULL,          -- ISO 8601
            mode          TEXT NOT NULL,          -- ex. competitif, deathmatch
            carte         TEXT NOT NULL,          -- carte ou niveau
            resultat      TEXT NOT NULL,          -- victoire, defaite, nul, sans_objet, inconnu
            score_joueur  INTEGER,
            score_adverse INTEGER,
            duree_s       REAL,
            source        TEXT NOT NULL,          -- chemin d'origine du fichier
            fichier       TEXT NOT NULL,          -- copie archivée analysée
            empreinte     TEXT NOT NULL UNIQUE,   -- SHA-256 du fichier : évite les doublons
            importe_le    TEXT NOT NULL,
            details       TEXT NOT NULL DEFAULT '{}'  -- JSON propre au jeu
        )
        """,
        "CREATE INDEX parties_jeu_date ON parties (jeu, date_partie)",
        """
        CREATE TABLE mesures (
            id          INTEGER PRIMARY KEY,
            partie_id   INTEGER NOT NULL REFERENCES parties (id) ON DELETE CASCADE,
            nom         TEXT NOT NULL,            -- ex. cs2.contre_strafe.part_tirs_precis
            version     INTEGER NOT NULL,
            valeur      REAL,
            unite       TEXT NOT NULL DEFAULT '',
            contexte    TEXT NOT NULL DEFAULT '{}',  -- JSON : arme, camp, échantillon…
            calcule_le  TEXT NOT NULL
        )
        """,
        "CREATE INDEX mesures_nom ON mesures (nom, partie_id)",
        """
        CREATE TABLE fichiers_vus (
            chemin     TEXT PRIMARY KEY,
            taille     INTEGER NOT NULL,
            mtime      REAL NOT NULL,
            statut     TEXT NOT NULL,             -- importe, deja_connu, erreur, ignore
            message    TEXT NOT NULL DEFAULT '',
            partie_id  INTEGER,
            vu_le      TEXT NOT NULL
        )
        """,
    ],
    # 2 — preuves des mesures (L1, COM-04)
    [
        """
        CREATE TABLE preuves (
            id         INTEGER PRIMARY KEY,
            partie_id  INTEGER NOT NULL REFERENCES parties (id) ON DELETE CASCADE,
            mesure     TEXT NOT NULL,             -- nom de la mesure illustrée
            tick       INTEGER,                   -- ou position dans le niveau (GD)
            round      INTEGER,
            texte      TEXT NOT NULL,
            donnees    TEXT NOT NULL DEFAULT '{}'
        )
        """,
        "CREATE INDEX preuves_partie ON preuves (partie_id, mesure)",
    ],
    # 3 — références apprises sur démos pros (L3, CS-REF-01)
    [
        """
        CREATE TABLE cs2_ref_demos (
            empreinte  TEXT PRIMARY KEY,
            fichier    TEXT NOT NULL,
            carte      TEXT NOT NULL,
            ajoute_le  TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE cs2_ref_observations (
            id          INTEGER PRIMARY KEY,
            empreinte   TEXT NOT NULL REFERENCES cs2_ref_demos (empreinte) ON DELETE CASCADE,
            carte       TEXT NOT NULL,
            genre       TEXT NOT NULL,      -- lancer, position, lieu
            type        TEXT,               -- smoke, flash, molotov (lancers)
            camp        TEXT,               -- T, CT
            lieu        TEXT,               -- lieu du joueur (ou du lanceur)
            x REAL, y REAL, z REAL,         -- arrivée (lancer) ou position du joueur
            lx REAL, ly REAL, lz REAL       -- position de lancer
        )
        """,
        "CREATE INDEX cs2_ref_obs_carte ON cs2_ref_observations (carte, genre)",
        """
        CREATE TABLE cs2_ref_lancers (
            id INTEGER PRIMARY KEY, carte TEXT NOT NULL, type TEXT NOT NULL,
            x REAL, y REAL, z REAL, lx REAL, ly REAL, lz REAL,
            lieu_arrivee TEXT, lieu_lancer TEXT, nb INTEGER, nb_demos INTEGER, construit_le TEXT
        )
        """,
        """
        CREATE TABLE cs2_ref_positions (
            id INTEGER PRIMARY KEY, carte TEXT NOT NULL, camp TEXT NOT NULL, lieu TEXT NOT NULL,
            x REAL, y REAL, nb INTEGER, part REAL, construit_le TEXT
        )
        """,
    ],
    # 4 — débriefs et fiabilité des mesures validée à la main (L5)
    [
        """
        CREATE TABLE debriefs (
            id           INTEGER PRIMARY KEY,
            partie_id    INTEGER NOT NULL REFERENCES parties (id) ON DELETE CASCADE,
            cree_le      TEXT NOT NULL,
            fournisseur  TEXT NOT NULL,
            modele       TEXT NOT NULL DEFAULT '',
            contenu      TEXT NOT NULL,          -- JSON : priorités, détail, preuves
            texte        TEXT NOT NULL,          -- débrief rédigé (Markdown)
            statut       TEXT NOT NULL,          -- redige, structure, rejete, erreur
            message      TEXT NOT NULL DEFAULT '',
            jetons_entree INTEGER NOT NULL DEFAULT 0,
            jetons_sortie INTEGER NOT NULL DEFAULT 0,
            cout         REAL NOT NULL DEFAULT 0  -- dollars
        )
        """,
        "CREATE INDEX debriefs_partie ON debriefs (partie_id, cree_le)",
        """
        CREATE TABLE fiabilite_mesures (
            nom      TEXT NOT NULL,
            version  INTEGER NOT NULL,
            fiable   INTEGER NOT NULL,
            note     TEXT NOT NULL DEFAULT '',
            le       TEXT NOT NULL,
            PRIMARY KEY (nom, version)
        )
        """,
    ],
    # 5 — références par contexte : méta par patch (LoL, TFT), pros par arme (CS2)
    [
        """
        CREATE TABLE references_mesures (
            jeu       TEXT NOT NULL,
            nom       TEXT NOT NULL,              -- nom de la mesure
            contexte  TEXT NOT NULL,              -- JSON trié des clés discriminantes
            patch     TEXT NOT NULL DEFAULT '',   -- '' si la mesure ne dépend pas du patch
            valeur    REAL NOT NULL,
            n         INTEGER NOT NULL,           -- taille de l'échantillon
            source    TEXT NOT NULL,              -- ex. « haut classement EUW », « démos pros »
            maj_le    TEXT NOT NULL,
            PRIMARY KEY (jeu, nom, contexte, patch)
        )
        """,
    ],
    # 6 — mesures de mécanique des joueurs pros, par démo (cibles par arme, CTX-01)
    [
        """
        CREATE TABLE cs2_ref_mesures (
            id         INTEGER PRIMARY KEY,
            empreinte  TEXT NOT NULL REFERENCES cs2_ref_demos (empreinte) ON DELETE CASCADE,
            joueur     TEXT NOT NULL,
            nom        TEXT NOT NULL,
            contexte   TEXT NOT NULL,      -- JSON trié des clés discriminantes
            valeur     REAL NOT NULL,
            n          INTEGER
        )
        """,
        "CREATE INDEX cs2_ref_mesures_nom ON cs2_ref_mesures (nom, contexte)",
    ],
    # 7 — apprentissage des stuffs (STUFF-01) : angle de lancer, identifiants stables,
    # notes et révisions
    [
        "ALTER TABLE cs2_ref_observations ADD COLUMN lpitch REAL",
        "ALTER TABLE cs2_ref_observations ADD COLUMN lyaw REAL",
        "ALTER TABLE cs2_ref_observations ADD COLUMN saut INTEGER",
        "ALTER TABLE cs2_ref_observations ADD COLUMN accroupi INTEGER",
        "ALTER TABLE cs2_ref_lancers ADD COLUMN cle TEXT",
        "ALTER TABLE cs2_ref_lancers ADD COLUMN lpitch REAL",
        "ALTER TABLE cs2_ref_lancers ADD COLUMN lyaw REAL",
        "ALTER TABLE cs2_ref_lancers ADD COLUMN part_saut REAL",
        "ALTER TABLE cs2_ref_lancers ADD COLUMN part_accroupi REAL",
        """
        CREATE TABLE notes (
            id        INTEGER PRIMARY KEY,
            jeu       TEXT NOT NULL,
            carte     TEXT NOT NULL,
            stuff     TEXT,                 -- clé du stuff, ou NULL pour une note de carte
            texte     TEXT NOT NULL,
            cree_le   TEXT NOT NULL,
            maj_le    TEXT NOT NULL
        )
        """,
        "CREATE INDEX notes_carte ON notes (jeu, carte)",
        """
        CREATE TABLE revisions (
            stuff     TEXT PRIMARY KEY,     -- clé du stuff
            boite     INTEGER NOT NULL,     -- boîte de Leitner (1 à 5)
            prochaine TEXT NOT NULL,        -- date de la prochaine révision
            derniere  TEXT,
            reussites INTEGER NOT NULL DEFAULT 0,
            echecs    INTEGER NOT NULL DEFAULT 0
        )
        """,
    ],
    # 8 — technique de lancer des stuffs (clic, saut, déplacement)
    [
        "ALTER TABLE cs2_ref_observations ADD COLUMN technique TEXT",
        "ALTER TABLE cs2_ref_lancers ADD COLUMN technique TEXT",
        "ALTER TABLE cs2_ref_lancers ADD COLUMN part_technique REAL",
    ],
    # 9 — revoir les vrais moments dans CS2 : chemin de la démo pro, tick, joueur, round
    [
        "ALTER TABLE cs2_ref_demos ADD COLUMN chemin TEXT",
        "ALTER TABLE cs2_ref_observations ADD COLUMN tick INTEGER",
        "ALTER TABLE cs2_ref_observations ADD COLUMN joueur TEXT",
        "ALTER TABLE cs2_ref_observations ADD COLUMN round INTEGER",
        "CREATE INDEX cs2_ref_obs_lieu ON cs2_ref_observations (carte, camp, lieu)",
    ],
]


def maintenant() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Partie:
    jeu: str
    date_partie: str
    mode: str
    carte: str
    resultat: str
    source: str
    fichier: str
    empreinte: str
    score_joueur: int | None = None
    score_adverse: int | None = None
    duree_s: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    importe_le: str = ""

    def en_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Mesure:
    nom: str
    version: int
    valeur: float | None
    unite: str = ""
    contexte: dict[str, Any] = field(default_factory=dict)


class Base:
    """Accès à la base. Une seule connexion protégée par un verrou : le service est
    mono-utilisateur, le débit d'écriture est faible."""

    def __init__(self, chemin: Path | str):
        self.chemin = Path(chemin)
        en_memoire = str(chemin) == ":memory:"
        if not en_memoire:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self._verrou = threading.RLock()
        self._cx = sqlite3.connect(str(chemin), check_same_thread=False)
        self._cx.row_factory = sqlite3.Row
        self._cx.execute("PRAGMA foreign_keys = ON")
        if not en_memoire:
            self._cx.execute("PRAGMA journal_mode = WAL")
        self._migrer()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._verrou:
            try:
                yield self._cx
                self._cx.commit()
            except Exception:
                self._cx.rollback()
                raise

    def _migrer(self) -> None:
        with self.transaction() as cx:
            version = cx.execute("PRAGMA user_version").fetchone()[0]
            for numero, instructions in enumerate(MIGRATIONS, start=1):
                if numero <= version:
                    continue
                for sql in instructions:
                    cx.execute(sql)
                cx.execute(f"PRAGMA user_version = {numero}")

    @property
    def version_schema(self) -> int:
        with self._verrou:
            return self._cx.execute("PRAGMA user_version").fetchone()[0]

    def fermer(self) -> None:
        with self._verrou:
            self._cx.close()

    # --- Parties -------------------------------------------------------------------

    def ajouter_partie(self, p: Partie) -> int:
        p.importe_le = p.importe_le or maintenant()
        with self.transaction() as cx:
            cur = cx.execute(
                """INSERT INTO parties (jeu, date_partie, mode, carte, resultat, score_joueur,
                   score_adverse, duree_s, source, fichier, empreinte, importe_le, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    p.jeu,
                    p.date_partie,
                    p.mode,
                    p.carte,
                    p.resultat,
                    p.score_joueur,
                    p.score_adverse,
                    p.duree_s,
                    p.source,
                    p.fichier,
                    p.empreinte,
                    p.importe_le,
                    json.dumps(p.details, ensure_ascii=False),
                ),
            )
            p.id = cur.lastrowid
        return p.id

    def mettre_a_jour_fiche(self, p: Partie) -> None:
        """Réécrit les champs de la fiche (re-analyse) ; l'empreinte et la source restent."""
        with self.transaction() as cx:
            cx.execute(
                """UPDATE parties SET date_partie = ?, mode = ?, carte = ?, resultat = ?,
                   score_joueur = ?, score_adverse = ?, duree_s = ?, details = ? WHERE id = ?""",
                (
                    p.date_partie,
                    p.mode,
                    p.carte,
                    p.resultat,
                    p.score_joueur,
                    p.score_adverse,
                    p.duree_s,
                    json.dumps(p.details, ensure_ascii=False),
                    p.id,
                ),
            )

    def partie_par_empreinte(self, empreinte: str) -> Partie | None:
        with self._verrou:
            ligne = self._cx.execute(
                "SELECT * FROM parties WHERE empreinte = ?", (empreinte,)
            ).fetchone()
        return _ligne_vers_partie(ligne) if ligne else None

    def partie(self, partie_id: int) -> Partie | None:
        with self._verrou:
            ligne = self._cx.execute("SELECT * FROM parties WHERE id = ?", (partie_id,)).fetchone()
        return _ligne_vers_partie(ligne) if ligne else None

    def lister_parties(
        self, jeu: str | None = None, limite: int = 50, decalage: int = 0
    ) -> list[Partie]:
        sql = "SELECT * FROM parties"
        params: list[Any] = []
        if jeu:
            sql += " WHERE jeu = ?"
            params.append(jeu)
        sql += " ORDER BY date_partie DESC, id DESC LIMIT ? OFFSET ?"
        params += [limite, decalage]
        with self._verrou:
            lignes = self._cx.execute(sql, params).fetchall()
        return [_ligne_vers_partie(lg) for lg in lignes]

    def compter_parties(self, jeu: str | None = None) -> int:
        with self._verrou:
            if jeu:
                return self._cx.execute(
                    "SELECT COUNT(*) FROM parties WHERE jeu = ?", (jeu,)
                ).fetchone()[0]
            return self._cx.execute("SELECT COUNT(*) FROM parties").fetchone()[0]

    # --- Mesures -------------------------------------------------------------------

    def remplacer_mesures(self, partie_id: int, mesures: list[Mesure], prefixe: str = "") -> None:
        """Remplace les mesures d'une partie (toutes, ou celles dont le nom commence par
        `prefixe`). Utilisé à l'analyse comme à la re-analyse (COM-08)."""
        horodatage = maintenant()
        with self.transaction() as cx:
            cx.execute(
                "DELETE FROM mesures WHERE partie_id = ? AND nom LIKE ?",
                (partie_id, prefixe + "%"),
            )
            cx.executemany(
                """INSERT INTO mesures (partie_id, nom, version, valeur, unite, contexte,
                   calcule_le) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        partie_id,
                        m.nom,
                        m.version,
                        m.valeur,
                        m.unite,
                        json.dumps(m.contexte, ensure_ascii=False),
                        horodatage,
                    )
                    for m in mesures
                ],
            )

    def remplacer_preuves(self, partie_id: int, preuves: list[Any]) -> None:
        """Remplace les preuves d'une partie (objets `postgame.mesures.Preuve`)."""
        with self.transaction() as cx:
            cx.execute("DELETE FROM preuves WHERE partie_id = ?", (partie_id,))
            cx.executemany(
                "INSERT INTO preuves (partie_id, mesure, tick, round, texte, donnees) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        partie_id,
                        p.mesure,
                        p.tick,
                        p.round,
                        p.texte,
                        json.dumps(p.donnees, ensure_ascii=False, default=float),
                    )
                    for p in preuves
                ],
            )

    def preuves_partie(self, partie_id: int, mesure: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT mesure, tick, round, texte, donnees FROM preuves WHERE partie_id = ?"
        params: list[Any] = [partie_id]
        if mesure:
            sql += " AND mesure = ?"
            params.append(mesure)
        sql += " ORDER BY mesure, tick"
        with self._verrou:
            lignes = self._cx.execute(sql, params).fetchall()
        return [{**dict(lg), "donnees": json.loads(lg["donnees"])} for lg in lignes]

    def preuves_toutes_parties(
        self, mesure: str, jeu: str | None = None, depuis: str | None = None
    ) -> list[dict[str, Any]]:
        """Preuves d'une mesure sur toutes les parties (cartes de chaleur, catalogues)."""
        sql = (
            "SELECT pr.partie_id, pr.tick, pr.round, pr.texte, pr.donnees, p.carte, "
            "p.date_partie FROM preuves pr JOIN parties p ON p.id = pr.partie_id "
            "WHERE pr.mesure = ?"
        )
        params: list[Any] = [mesure]
        if jeu:
            sql += " AND p.jeu = ?"
            params.append(jeu)
        if depuis:
            sql += " AND p.date_partie >= ?"
            params.append(depuis)
        sql += " ORDER BY p.date_partie, pr.tick"
        with self._verrou:
            lignes = self._cx.execute(sql, params).fetchall()
        return [{**dict(lg), "donnees": json.loads(lg["donnees"])} for lg in lignes]

    # --- Fiabilité et débriefs ------------------------------------------------------------

    def fiabilites(self) -> dict[tuple[str, int], bool]:
        with self._verrou:
            lignes = self._cx.execute("SELECT nom, version, fiable FROM fiabilite_mesures")
            return {(r["nom"], r["version"]): bool(r["fiable"]) for r in lignes.fetchall()}

    def noter_fiabilite(self, nom: str, version: int, fiable: bool, note: str = "") -> None:
        with self.transaction() as cx:
            cx.execute(
                "INSERT INTO fiabilite_mesures (nom, version, fiable, note, le) VALUES "
                "(?, ?, ?, ?, ?) ON CONFLICT (nom, version) DO UPDATE SET fiable = "
                "excluded.fiable, note = excluded.note, le = excluded.le",
                (nom, version, int(fiable), note, maintenant()),
            )

    def enregistrer_debrief(self, partie_id: int, d: dict[str, Any]) -> int:
        with self.transaction() as cx:
            cur = cx.execute(
                "INSERT INTO debriefs (partie_id, cree_le, fournisseur, modele, contenu, texte, "
                "statut, message, jetons_entree, jetons_sortie, cout) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    partie_id,
                    maintenant(),
                    d["fournisseur"],
                    d.get("modele", ""),
                    json.dumps(d["contenu"], ensure_ascii=False, default=float),
                    d["texte"],
                    d["statut"],
                    d.get("message", ""),
                    d.get("jetons_entree", 0),
                    d.get("jetons_sortie", 0),
                    d.get("cout", 0.0),
                ),
            )
            return cur.lastrowid

    def dernier_debrief(self, partie_id: int) -> dict[str, Any] | None:
        with self._verrou:
            ligne = self._cx.execute(
                "SELECT * FROM debriefs WHERE partie_id = ? ORDER BY id DESC LIMIT 1",
                (partie_id,),
            ).fetchone()
        if ligne is None:
            return None
        return {**dict(ligne), "contenu": json.loads(ligne["contenu"])}

    def couts_debriefs(self) -> dict[str, Any]:
        with self._verrou:
            ligne = self._cx.execute(
                "SELECT COUNT(*) AS nb, COALESCE(SUM(cout), 0) AS total, "
                "COALESCE(SUM(jetons_entree), 0) AS entree, COALESCE(SUM(jetons_sortie), 0) "
                "AS sortie, COALESCE(AVG(NULLIF(cout, 0)), 0) AS moyen FROM debriefs"
            ).fetchone()
        return dict(ligne)

    # --- Références par contexte ----------------------------------------------------------

    def enregistrer_references(self, lignes: list[dict[str, Any]]) -> None:
        """Lignes {jeu, nom, contexte (dict), patch, valeur, n, source} ; remplace l'existant."""
        horodatage = maintenant()
        with self.transaction() as cx:
            cx.executemany(
                "INSERT INTO references_mesures (jeu, nom, contexte, patch, valeur, n, source, "
                "maj_le) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (jeu, nom, contexte, patch) "
                "DO UPDATE SET valeur = excluded.valeur, n = excluded.n, "
                "source = excluded.source, maj_le = excluded.maj_le",
                [
                    (
                        r["jeu"],
                        r["nom"],
                        json.dumps(r["contexte"], sort_keys=True, ensure_ascii=False),
                        r.get("patch", ""),
                        float(r["valeur"]),
                        int(r["n"]),
                        r["source"],
                        horodatage,
                    )
                    for r in lignes
                ],
            )

    def references(self, nom: str, contexte: dict[str, Any]) -> list[dict[str, Any]]:
        """Références d'une mesure pour un contexte, du patch le plus récent au plus ancien."""
        with self._verrou:
            lignes = self._cx.execute(
                "SELECT * FROM references_mesures WHERE nom = ? AND contexte = ? "
                "ORDER BY patch DESC, maj_le DESC",
                (nom, json.dumps(contexte, sort_keys=True, ensure_ascii=False)),
            ).fetchall()
        return [{**dict(lg), "contexte": json.loads(lg["contexte"])} for lg in lignes]

    def mesures_partie(self, partie_id: int) -> list[dict[str, Any]]:
        with self._verrou:
            lignes = self._cx.execute(
                "SELECT nom, version, valeur, unite, contexte, calcule_le FROM mesures "
                "WHERE partie_id = ? ORDER BY nom, id",
                (partie_id,),
            ).fetchall()
        return [{**dict(lg), "contexte": json.loads(lg["contexte"])} for lg in lignes]

    def serie_mesure(
        self, nom: str, depuis: str | None = None, contexte: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Valeurs d'une mesure partie par partie, dans l'ordre chronologique (COM-03)."""
        sql = (
            "SELECT p.id AS partie_id, p.date_partie, p.carte, p.mode, m.valeur, m.unite, "
            "m.version, m.contexte FROM mesures m JOIN parties p ON p.id = m.partie_id "
            "WHERE m.nom = ?"
        )
        params: list[Any] = [nom]
        if depuis:
            sql += " AND p.date_partie >= ?"
            params.append(depuis)
        sql += " ORDER BY p.date_partie, p.id"
        with self._verrou:
            lignes = self._cx.execute(sql, params).fetchall()
        serie = [{**dict(lg), "contexte": json.loads(lg["contexte"])} for lg in lignes]
        if contexte:
            serie = [
                s for s in serie if all(s["contexte"].get(k) == v for k, v in contexte.items())
            ]
        return serie

    def noms_mesures(self) -> list[str]:
        with self._verrou:
            return [r[0] for r in self._cx.execute("SELECT DISTINCT nom FROM mesures ORDER BY nom")]

    # --- Fichiers vus par la surveillance ---------------------------------------------

    def fichier_vu(self, chemin: str) -> dict[str, Any] | None:
        with self._verrou:
            ligne = self._cx.execute(
                "SELECT * FROM fichiers_vus WHERE chemin = ?", (chemin,)
            ).fetchone()
        return dict(ligne) if ligne else None

    def noter_fichier(
        self,
        chemin: str,
        taille: int,
        mtime: float,
        statut: str,
        message: str = "",
        partie_id: int | None = None,
    ) -> None:
        with self.transaction() as cx:
            cx.execute(
                """INSERT INTO fichiers_vus (chemin, taille, mtime, statut, message, partie_id,
                   vu_le) VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (chemin) DO UPDATE SET taille = excluded.taille,
                   mtime = excluded.mtime, statut = excluded.statut, message = excluded.message,
                   partie_id = excluded.partie_id, vu_le = excluded.vu_le""",
                (chemin, taille, mtime, statut, message, partie_id, maintenant()),
            )

    def derniers_fichiers(self, limite: int = 20) -> list[dict[str, Any]]:
        with self._verrou:
            lignes = self._cx.execute(
                "SELECT * FROM fichiers_vus ORDER BY vu_le DESC, rowid DESC LIMIT ?", (limite,)
            ).fetchall()
        return [dict(lg) for lg in lignes]


def _ligne_vers_partie(ligne: sqlite3.Row) -> Partie:
    d = dict(ligne)
    d["details"] = json.loads(d["details"])
    return Partie(**d)
