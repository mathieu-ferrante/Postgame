"""Geometry Dash (L8) : lecture des journaux du mod et analyses, sur séances synthétiques.

DONNÉES DE SUBSTITUTION : journaux fabriqués au format du mod (mods/gd-journal), avec des
décalages de clic choisis à la main. Le mod n'a pas encore tourné sur le PC de jeu.
"""

import json
import statistics

import pytest
from fastapi.testclient import TestClient

from postgame.api import creer_app
from postgame.games.gd import construire_fiche, donnees_replay
from postgame.games.gd.analyse import analyser_session, inputs_attendus, longueur_niveau
from postgame.games.gd.session import analyser_lignes
from postgame.importation import importer

VITESSE = 0.311  # u/ms (vitesse normale ≈ 311 u/s)
TICK = 1000 / 240  # ms


def essai(n, t0, offsets, fin, mode="normal", x0=0.0, appuis_en_plus=()):
    """Lignes d'un essai : départ en x0 à t0, appui à chaque x de `offsets` avec le décalage
    donné (ms), puis `fin` = ("mort", x, pct) ou ("fin",)."""
    lignes = [{"type": "essai", "n": n, "mode": mode, "t": t0, "tn": 0.0, "f": 0, "x": x0}]
    x_max = fin[1] if fin[0] == "mort" else 3000.0
    t_max = t0 + (x_max - x0) / VITESSE
    evenements = []
    t = t0
    while t <= t_max:
        evenements.append({"type": "pos", "t": round(t, 3), "x": round(x0 + VITESSE * (t - t0), 2)})
        t += 20
    for x, decalage in offsets.items():
        if x > x_max:
            continue
        tp = t0 + (x - x0) / VITESSE + decalage
        tn = round(round((tp - t0) / TICK) * TICK / 1000, 5)
        evenements.append(
            {
                "type": "input",
                "t": round(tp, 3),
                "tn": tn,
                "x": round(x0 + VITESSE * (tp - t0), 2),
                "appui": True,
                "j": 1,
            }
        )
        evenements.append(
            {
                "type": "input",
                "t": round(tp + 60, 3),
                "x": round(x0 + VITESSE * (tp + 60 - t0), 2),
                "appui": False,
                "j": 1,
            }
        )
    for tp in appuis_en_plus:
        evenements.append(
            {
                "type": "input",
                "t": tp,
                "x": round(x0 + VITESSE * (tp - t0), 2),
                "appui": True,
                "j": 1,
            }
        )
    lignes += sorted(evenements, key=lambda e: e["t"])
    if fin[0] == "mort":
        lignes.append(
            {"type": "mort", "t": round(t_max, 3), "x": fin[1], "pct": fin[2], "objet": 8}
        )
    else:
        lignes.append({"type": "fin", "t": round(t_max, 3), "pct": 100, "complete": True})
    return lignes


def seance(*essais, plateforme=False):
    lignes = [
        {
            "type": "session",
            "format": 1,
            "debut": "2026-10-12T21:30:00",
            "niveau": {"id": 4284013, "nom": "Niveau test", "createur": "Quelqu'un"},
            "plateforme": plateforme,
            "mod": "v1.0.0",
        }
    ]
    for e in essais:
        lignes += e
    lignes.append({"type": "fin_session", "t": 99999})
    return [json.dumps(ligne) for ligne in lignes]


def seance_de_base():
    """3 essais normaux. Appui à 300 u : toujours à l'heure. À 600 u : −10, 0, +10 ms.
    Essai 1 meurt à 650 u (21,67 %), essai 2 à 1250 u (41,67 %), essai 3 termine.
    Le niveau fait donc 3000 u (650 / 21,67 %)."""
    appuis = {300: 0, 900: 0, 1200: 0, 1500: 0}
    return analyser_lignes(
        seance(
            essai(1, 0, {**appuis, 600: -10}, ("mort", 650.0, 650 / 30)),
            essai(2, 10000, {**appuis, 600: 0}, ("mort", 1250.0, 1250 / 30)),
            essai(3, 20000, {**appuis, 600: 10}, ("fin",)),
        )
    )


def _valeur(resultat, nom, **contexte):
    for m in resultat.mesures:
        if m.nom == nom and all(m.contexte.get(k) == v for k, v in contexte.items()):
            return m.valeur
    raise AssertionError(f"mesure absente : {nom} {contexte}")


def test_lecture():
    s = seance_de_base()
    assert (s.niveau, s.niveau_id, len(s.essais)) == ("Niveau test", 4284013, 3)
    assert s.essais[0].mort and s.essais[0].pct_fin == pytest.approx(21.6667, abs=1e-3)
    assert s.essais[2].complete and s.essais[2].x_fin == pytest.approx(3000, abs=10)
    assert len(s.essais[1].appuis) == 4  # 300, 600, 900, 1200 (mort à 1250)


def test_lignes_corrompues_et_sans_entete():
    lignes = seance(essai(1, 0, {300: 0}, ("mort", 400.0, 13.3)))
    lignes.insert(3, "{pas du json")
    assert analyser_lignes(lignes).avertissements == ["ligne 4 illisible"]
    with pytest.raises(Exception, match="sans en-tête"):
        analyser_lignes(lignes[1:])


def test_inputs_attendus_et_decalages():
    s = seance_de_base()
    attendus = inputs_attendus(s)
    # 900 u et au-delà : seulement 2 essais y arrivent → pas d'input attendu.
    assert [round(a.x) for a in attendus] == [300, 600]
    assert attendus[0].decalages == pytest.approx([0, 0, 0], abs=0.05)
    assert sorted(attendus[1].decalages) == pytest.approx([-10, 0, 10], abs=0.05)
    assert attendus[1].ecart_type == pytest.approx(statistics.pstdev([-10, 0, 10]), abs=0.05)
    assert longueur_niveau(s) == pytest.approx(3000)


def test_analyse():
    r = analyser_session(seance_de_base())
    ecart = statistics.pstdev([-10, 0, 10])  # 8,16 ms
    assert _valeur(r, "gd.regularite.ecart_type_median") == pytest.approx(ecart / 2, abs=0.05)
    assert _valeur(r, "gd.regularite.decalage_moyen") == pytest.approx(0, abs=0.05)
    assert _valeur(r, "gd.regularite.part_inputs_stables") == 100.0
    # Les deux morts suivent l'input de 600 u, le plus irrégulier.
    assert _valeur(r, "gd.instables.part_morts_apres_instables") == 100.0
    assert _valeur(r, "gd.survie.par_segment", segment="0-10") == 100.0
    assert _valeur(r, "gd.survie.par_segment", segment="20-30") == pytest.approx(200 / 3, abs=1e-3)
    assert _valeur(r, "gd.survie.par_segment", segment="40-50") == 50.0
    assert _valeur(r, "gd.progression.meilleur_pourcent") == 100.0
    assert _valeur(r, "gd.progression.pourcent_moyen") == pytest.approx(
        (65 / 3 + 125 / 3 + 100) / 3, abs=1e-3
    )
    assert _valeur(r, "gd.technique.resolution_ms") == pytest.approx(TICK, abs=0.01)
    textes = [p.texte for p in r.preuves]
    assert "Input à 20.0 % : écart-type 8 ms" in textes[0].replace(",", ".")
    assert "2 mort(s) juste après sur 3 passage(s)" in textes[0]
    assert any("Passage le plus meurtrier : 40-50 %" in t for t in textes)
    assert sum(p.mesure == "gd.mort" for p in r.preuves) == 2


def test_pas_commun():
    from postgame.games.gd.analyse import pas_commun

    tick = 1000 / 240
    assert pas_commun([0, 2 * tick, 5 * tick, 9 * tick]) == pytest.approx(tick, abs=0.01)
    assert pas_commun([0, 8.0, 16.0]) == pytest.approx(8.0)
    assert pas_commun([1.0]) is None


def test_spam():
    # 5 appuis toutes les 100 ms : 4 intervalles en 0,4 s = 10 clics/s, parfaitement réguliers.
    s = analyser_lignes(
        seance(essai(1, 0, {}, ("mort", 600.0, 20.0), appuis_en_plus=(500, 600, 700, 800, 900)))
    )
    r = analyser_session(s)
    assert _valeur(r, "gd.spam.cps_moyen") == pytest.approx(10.0)
    assert _valeur(r, "gd.spam.irregularite") == pytest.approx(0.0)


def test_effet_practice():
    normal = lambda n, t, pct: essai(n, t, {}, ("mort", 30 * pct, pct))  # noqa: E731
    s = analyser_lignes(
        seance(
            normal(1, 0, 10),
            normal(2, 5000, 12),
            normal(3, 10000, 14),
            essai(4, 15000, {}, ("mort", 900.0, 30.0), mode="practice", x0=600.0),
            normal(5, 20000, 20),
            normal(6, 25000, 22),
            normal(7, 30000, 24),
        )
    )
    r = analyser_session(s)
    assert _valeur(r, "gd.practice.gain") == pytest.approx(10.0)  # 22 − 12
    assert _valeur(r, "gd.progression.essais_practice") == 1
    fiche = construire_fiche(s)
    assert (fiche.mode, fiche.resultat, fiche.score_joueur) == ("mixte", "sans_objet", 24)


def test_fiche_et_replay():
    s = seance_de_base()
    fiche = construire_fiche(s)
    assert (fiche.carte, fiche.mode, fiche.resultat, fiche.score_joueur) == (
        "Niveau test",
        "normal",
        "victoire",
        100,
    )
    replay = donnees_replay(s)
    assert len(replay["essais"]) == 3 and replay["longueur"] == pytest.approx(3000)
    assert [i["pct"] for i in replay["inputs"]] == [10.0, 20.0]


def test_plateforme_sans_regularite():
    s = analyser_lignes(seance(essai(1, 0, {300: 0}, ("mort", 400.0, 13.3)), plateforme=True))
    noms = {m.nom for m in analyser_session(s).mesures}
    assert "gd.regularite.ecart_type_median" not in noms
    assert construire_fiche(s).mode == "plateforme normal"


def test_import_et_api(tmp_path, base, cfg):
    journal = tmp_path / "20261012-213000_Niveau_test.gdsession"
    journal.write_text("\n".join(seance_de_base_lignes()), encoding="utf-8")
    res = importer(journal, base, cfg)
    assert res.statut == "importe", res.message
    p = base.partie(res.partie_id)
    assert (p.jeu, p.carte, p.resultat) == ("gd", "Niveau test", "victoire")
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as client:
        r = client.get(f"/api/gd/replay/{res.partie_id}").json()
        assert r["niveau"] == "Niveau test" and len(r["inputs"]) == 2
        assert client.get("/api/gd/replay/999").status_code == 404


def seance_de_base_lignes():
    appuis = {300: 0, 900: 0, 1200: 0, 1500: 0}
    return seance(
        essai(1, 0, {**appuis, 600: -10}, ("mort", 650.0, 650 / 30)),
        essai(2, 10000, {**appuis, 600: 0}, ("mort", 1250.0, 1250 / 30)),
        essai(3, 20000, {**appuis, 600: 10}, ("fin",)),
    )


def test_second_ecran_gd(base, cfg, tmp_path):
    from postgame.live.gd import SuiviGD

    appuis = {300: 0, 900: 0, 1200: 0, 1500: 0}
    lignes = seance(
        essai(1, 0, {**appuis, 600: -10}, ("mort", 650.0, 650 / 30)),
        essai(2, 10000, {**appuis, 600: 0}, ("mort", 1250.0, 1250 / 30)),
        essai(3, 20000, {**appuis, 600: 10}, ("fin",)),
    )
    # Une séance passée du même niveau, déjà importée et analysée.
    passe = tmp_path / "passe.gdsession"
    passe.write_text("\n".join(lignes), encoding="utf-8")
    importer(passe, base, cfg)
    # Séance en cours : le journal grossit ligne par ligne, la dernière est incomplète.
    dossier = tmp_path / "sessions"
    dossier.mkdir()
    journal = dossier / "en_cours.gdsession"
    sans_fin = lignes[:-1]
    coupe = len(sans_fin) // 2
    journal.write_text("\n".join(sans_fin[:coupe]) + "\n" + sans_fin[coupe][:10], encoding="utf-8")
    suivi = SuiviGD(base, [dossier])
    suivi.passe()
    assert suivi.resume["actif"] and suivi.resume["niveau"] == "Niveau test"
    avant = suivi.resume["essais_normaux"]
    with journal.open("a", encoding="utf-8") as f:
        f.write(sans_fin[coupe][10:] + "\n" + "\n".join(sans_fin[coupe + 1 :]) + "\n")
    suivi.passe()
    r = suivi.resume
    assert r["essais_normaux"] == 3 > avant and r["complete"] and r["meilleur"] == 100.0
    assert r["zones_mort"][0]["de"] in (20, 40)
    h = r["historique"]
    assert h["morts_total"] == 2 and h["zones_mort"]
    # Fin de séance : plus rien à afficher.
    with journal.open("a", encoding="utf-8") as f:
        f.write(lignes[-1] + "\n")
    suivi.passe()
    assert not suivi.resume["actif"]
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        assert c.get("/api/gd/live").json() == {"actif": False}


def test_second_ecran_gd_robuste(base, tmp_path):
    from postgame.live.gd import SuiviGD

    dossier = tmp_path / "sessions"
    dossier.mkdir()
    journal = dossier / "s.gdsession"
    entete = json.dumps(
        {"type": "session", "niveau": {"id": 1, "nom": "Électrodynamix"}}, ensure_ascii=False
    ).encode("utf-8")
    coupe = entete.index("É".encode()) + 1  # au milieu du É (2 octets en UTF-8)
    journal.write_bytes(entete[:coupe])
    suivi = SuiviGD(base, [dossier])
    suivi.passe()
    with journal.open("ab") as f:
        f.write(
            entete[coupe:] + b"\n" + b'[1, 2]\n{"type": "mort", "x": null}\n{"type": "essai"}\n'
        )
    suivi.passe()
    # Nom accentué intact ; lignes inattendues ignorées sans arrêter le suivi.
    assert suivi.resume["niveau"] == "Électrodynamix" and suivi.resume["essai"] == 1


def test_lignes_inattendues_ignorees():
    lignes = seance(essai(1, 0, {300: 0}, ("mort", 400.0, 13.3)))
    lignes.insert(2, "[1, 2]")
    lignes.insert(3, json.dumps({"type": "mort", "t": 5, "x": None, "pct": None}))
    s = analyser_lignes(lignes)
    assert len(s.essais) == 1 and any("inattendue" in a for a in s.avertissements)
