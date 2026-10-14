"""Débrief (L5) : constats, priorités, rédaction contrôlée, coût, fournisseurs simulés.

Aucun appel réseau réel : Gemini et Ollama sont simulés (httpx.MockTransport). La qualité
du débrief sur un vrai match reste à juger par Mathieu (critère de fin de L5).
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from postgame.api import creer_app
from postgame.db import Mesure, Partie
from postgame.debrief import generer_debrief
from postgame.debrief.constats import (
    charger_definitions,
    construire_constats,
    estimer_impact,
    selectionner,
)
from postgame.debrief.redaction import (
    GeminiRedacteur,
    LocalRedacteur,
    Reponse,
    chiffres_inventes,
    donnees_modele,
)
from postgame.mesures import DEFINITIONS, Preuve

CS = "cs2.contre_strafe.part_premieres_balles_precises"
VISEUR = "cs2.viseur.ecart_median"
FLASH = "cs2.flash.part_inutile"


def test_impact_calcule_a_la_main():
    # 60 % contre une cible de 80 et une habitude de 70, échelle 10, poids 2, n = 20 :
    # 2 × 1 × (2 + 0,5 × 1) = 5
    assert estimer_impact(60, "haut", 70, 80, 10, 2.0, 20) == (5.0, "a_corriger")
    assert estimer_impact(85, "haut", 70, 80, 10, 2.0, 20) == (0.0, "point_fort")
    # Sens « bas » : 400 ms pour 300 attendus, échelle 50, n = 10 (confiance 0,5) :
    # 1 × 0,5 × (2 + 0,5 × 2) = 1,5
    assert estimer_impact(400, "bas", 300, 300, 50, 1.0, 10) == (1.5, "a_corriger")
    assert estimer_impact(70, "haut", None, None, 10, 1.0, 20) == (0.0, "neutre")


def _partie(base, n, date, mode="competitif"):
    return base.ajouter_partie(
        Partie(
            jeu="cs2",
            date_partie=date,
            mode=mode,
            carte="de_mirage",
            resultat="defaite",
            source=f"{n}.dem",
            fichier=f"{n}.dem",
            empreinte=str(n) * 64,
        )
    )


@pytest.fixture
def historique(base):
    """Deux parties précédentes (70 et 72 %) puis la partie analysée (60 %)."""
    p1 = _partie(base, 1, "2026-10-01T20:00:00+00:00")
    p2 = _partie(base, 2, "2026-10-02T20:00:00+00:00")
    p3 = _partie(base, 3, "2026-10-03T20:00:00+00:00")
    _partie(base, 4, "2026-10-04T20:00:00+00:00", mode="deathmatch")
    base.remplacer_mesures(p1, [Mesure(CS, 1, 70.0, "%", {"n": 30})])
    base.remplacer_mesures(p2, [Mesure(CS, 1, 72.0, "%", {"n": 30})])
    base.remplacer_mesures(
        p3,
        [
            Mesure(CS, 1, 60.0, "%", {"n": 25}),
            Mesure(CS, 1, 40.0, "%", {"arme": "ak47", "n": 3}),  # échantillon trop petit
            Mesure(VISEUR, 1, 9.0, "°", {"n": 40}),
            Mesure(FLASH, 1, 10.0, "%", {"n": 10}),
            Mesure("cs2.flash.nombre", 1, 10.0, "flashs"),  # sens neutre : jamais un constat
        ],
    )
    base.remplacer_preuves(
        p3,
        [
            Preuve(CS, 1200, "Première balle à 180 u/s avec AK-47", 3, {"arme": "ak47"}),
            Preuve(VISEUR, 900, "Adv1 apparaît à 20° du viseur", 2),
        ],
    )
    for nom in (CS, VISEUR):
        charger_definitions()
        base.noter_fiabilite(nom, DEFINITIONS[nom].version, True, "vérifié à la main (test)")
    return base.partie(p3)


def test_constats_et_priorites(base, historique):
    constats, masquees = construire_constats(base, historique)
    assert masquees == 1  # cs2.flash.part_inutile n'est pas vérifiée
    noms = [c.mesure for c in constats]
    # Contre-strafe : (80 − 60) / 10 + 0,5 × (71 − 60) / 10 = 2,55, × poids 2 = 5,1.
    # Viseur : 9° pour une cible de 5°, échelle 2 : (9 − 5) / 2 × poids 2 = 4.
    assert noms == [CS, VISEUR]
    assert constats[1].impact == pytest.approx(4.0)
    cs = constats[0]
    assert cs.reference == 71.0 and cs.nb_reference == 2
    assert cs.impact == pytest.approx(5.1)
    assert cs.preuves[0]["lien"] == f"/replay/{historique.id}?tick=1200"
    sel = selectionner(constats)
    assert [c.id for c in sel["priorites"]] == ["C1", "C2"]


def test_mesures_experimentales_signalees(base, historique):
    constats, masquees = construire_constats(base, historique, experimentales=True)
    assert masquees == 0
    flash = next(c for c in constats if c.mesure == FLASH)
    assert flash.experimental and flash.statut == "point_fort"


def test_rien_ne_part_avec_des_noms(base, historique):
    constats, _ = construire_constats(base, historique)
    donnees = donnees_modele(selectionner(constats), "cs2", "competitif", "de_mirage")
    texte = json.dumps(donnees, ensure_ascii=False)
    assert "Adv1" not in texte and "76561" not in texte and ".dem" not in texte
    assert donnees["priorites"][0]["source"] == "C1"


def test_chiffres_inventes():
    donnees = {"priorites": [{"source": "C1", "valeur": 61.5, "cible": 80, "echantillon": 25}]}
    assert chiffres_inventes("Tu es à 61,5 % [C1] pour 80 visés, sur 25 balles.", donnees) == []
    assert chiffres_inventes("Environ 62 % [C1].", donnees) == []  # arrondi autorisé
    assert chiffres_inventes("Tu perds 18,5 points [C1], soit 3 duels de plus.", donnees) == [
        "18,5"
    ]
    assert chiffres_inventes("Avec la M4A1 [C1], 1v3.", donnees) == []


class FauxRedacteur:
    nom, modele = "faux", "faux-1"

    def __init__(self, texte):
        self.texte = texte
        self.recu = None

    def rediger(self, consignes, donnees):
        self.recu = donnees
        return Reponse(self.texte, 1000, 500)


def test_generer_debrief_redige_et_cout(base, cfg, historique):
    faux = FauxRedacteur("## Priorités\n1. Viseur à 9 ° [C1], cible 5.\n2. 60 % [C2].")
    d = generer_debrief(base, cfg, historique.id, faux)
    assert d["statut"] == "redige" and d["texte"].startswith("## Priorités")
    # 1000 × 0,25 $ + 500 × 1,50 $ par million de jetons
    assert d["cout"] == pytest.approx(0.001)
    assert d["contenu"]["priorites"][0]["preuves"][0]["tick"] == 1200
    assert base.couts_debriefs()["total"] == pytest.approx(0.001)


def test_generer_debrief_rejete_un_chiffre_invente(base, cfg, historique):
    d = generer_debrief(base, cfg, historique.id, FauxRedacteur("Tu as raté 45 % [C1]."))
    assert d["statut"] == "rejete" and "45" in d["message"]
    assert d["texte"].startswith("## Priorités\n1. Part des premières balles")
    assert d["contenu"]["texte_rejete"] == "Tu as raté 45 % [C1]."


def test_generer_debrief_sans_modele(base, cfg, historique):
    d = generer_debrief(base, cfg, historique.id, None)
    assert d["statut"] == "structure" and d["fournisseur"] == "aucun"
    assert "1 mesure(s) pas encore vérifiée(s)" in d["texte"]
    assert "ta moyenne : 71 % sur 2 partie(s)" in d["texte"]


def test_gemini_sans_cle(base, cfg, historique):
    cfg.debrief.fournisseur = "gemini"
    d = generer_debrief(base, cfg, historique.id)
    assert d["statut"] == "structure" and "clé Gemini absente" in d["message"]


def test_gemini_simule():
    vu = {}

    def repondre(requete: httpx.Request) -> httpx.Response:
        vu["url"], vu["cle"] = str(requete.url), requete.headers["x-goog-api-key"]
        vu["corps"] = json.loads(requete.content)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "Bonjour [C1]"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 812,
                    "candidatesTokenCount": 230,
                    "thoughtsTokenCount": 20,
                    "totalTokenCount": 1062,
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(repondre))
    r = GeminiRedacteur("cle-test", "gemini-3.1-flash-lite", client).rediger("consignes", "{}")
    assert vu["url"].endswith("/models/gemini-3.1-flash-lite:generateContent")
    assert vu["cle"] == "cle-test" and "cle-test" not in vu["url"]
    assert vu["corps"]["systemInstruction"]["parts"][0]["text"] == "consignes"
    assert (r.texte, r.jetons_entree, r.jetons_sortie) == ("Bonjour [C1]", 812, 250)


def test_local_simule():
    def repondre(requete: httpx.Request) -> httpx.Response:
        assert str(requete.url) == "http://localhost:11434/api/chat"
        corps = json.loads(requete.content)
        assert corps["messages"][0]["role"] == "system" and corps["stream"] is False
        return httpx.Response(
            200, json={"message": {"content": "Salut"}, "prompt_eval_count": 100, "eval_count": 40}
        )

    client = httpx.Client(transport=httpx.MockTransport(repondre))
    r = LocalRedacteur("http://localhost:11434/", "qwen3", client).rediger("c", "d")
    assert (r.texte, r.jetons_entree, r.jetons_sortie) == ("Salut", 100, 40)


def test_api_debrief(base, cfg, historique):
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as client:
        d = client.get(f"/api/parties/{historique.id}/debrief").json()
        assert d["statut"] == "structure"
        assert len(d["contenu"]["priorites"]) == 2
        assert client.get("/api/parties/999/debrief").status_code == 404
        r = client.post("/api/mesures/fiabilite", json={"nom": FLASH, "fiable": True})
        assert r.json() == {"nom": FLASH, "version": 1, "fiable": True}
        d2 = client.get(f"/api/parties/{historique.id}/debrief?regenerer=true").json()
        assert d2["id"] != d["id"] and d2["contenu"]["mesures_masquees"] == 0
        assert client.get("/api/debriefs/couts").json()["nb"] == 2
        defs = {x["nom"]: x for x in client.get("/api/mesures/definitions").json()}
        assert defs[FLASH]["fiable"] is True


def test_chiffres_negatifs_et_milliers_acceptes():
    from postgame.debrief.redaction import chiffres_inventes

    donnees = {"ecart_cs": -12, "or": 1250}
    # « 12 sbires de retard » pour un écart de −12, et les milliers à la française.
    assert chiffres_inventes("Tu as 12 sbires de retard (-12) et 1 250 or.", donnees) == []
    assert chiffres_inventes("Tu as 1 250 or.", donnees) == []
    assert chiffres_inventes("Tu as 13 sbires de retard.", donnees) == ["13"]


def test_patch_le_plus_recent_d_abord(base):
    for patch, valeur in (("15.9", 1.0), ("15.20", 2.0), ("", 3.0)):
        base.enregistrer_references(
            [
                {
                    "jeu": "lol",
                    "nom": "lol.farm.cs_par_minute",
                    "contexte": {"role": "MIDDLE"},
                    "patch": patch,
                    "valeur": valeur,
                    "n": 50,
                    "source": "test",
                }
            ]
        )
    refs = base.references("lol.farm.cs_par_minute", {"role": "MIDDLE"})
    assert [r["patch"] for r in refs] == ["15.20", "15.9", ""]
