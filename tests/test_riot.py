"""LoL, TFT et API Riot (L9) sur parties synthétiques calculées à la main.

DONNÉES DE SUBSTITUTION : aucune vraie partie de Mathieu n'a été récupérée (clé API Riot
pas encore fournie). L'API Riot est simulée (httpx.MockTransport).
"""

import json

import httpx
import pytest
from fabrique_riot import MOI, partie_lol, partie_tft
from fastapi.testclient import TestClient

from postgame.api import creer_app
from postgame.db import Mesure, Partie
from postgame.debrief.constats import cible_contextuelle
from postgame.games.lol import construire_fiche as fiche_lol
from postgame.games.lol import donnees_replay
from postgame.games.lol.analyse import analyser_lol, patch_de
from postgame.games.riot import meta
from postgame.games.riot.client import ClientRiot, ErreurRiot, Limiteur
from postgame.games.riot.collecte import CollecteurRiot
from postgame.games.tft import analyser_tft, nom_court, patch_tft
from postgame.games.tft import construire_fiche as fiche_tft
from postgame.games.tft.stats import comparer, observations, statistiques, traduire


def _valeur(resultat, nom, **contexte):
    for m in resultat.mesures:
        if m.nom == nom and all(m.contexte.get(k) == v for k, v in contexte.items()):
            return m.valeur
    raise AssertionError(f"mesure absente : {nom} {contexte}")


# --- League of Legends ----------------------------------------------------------------------


def test_patch():
    assert patch_de("15.20.712.3456") == "15.20"
    assert patch_tft("Version 15.20.712.3456 (Oct 10 2025/12:00) [PUBLIC]") == "15.20"
    assert nom_court("TFT15_Ahri") == "Ahri"
    # Format du set 18 (Unreal Engine), vu dans le Data Dragon officiel 16.20.1.
    assert nom_court("DA_CrimsonRaptor18") == "Crimson Raptor"
    assert nom_court("DA_18_ZyraUniqueTrait") == "Zyra"
    assert nom_court("TFT_Item_InfinityEdge") == "Infinity Edge"


def test_analyse_lol():
    d = partie_lol()
    r = analyser_lol(d["match"], d["timeline"], MOI, {"Ahri": ["mage", "assassin"]})
    assert _valeur(r, "lol.farm.cs", minute=10) == 80
    assert _valeur(r, "lol.farm.ecart_cs", minute=10) == -10
    assert _valeur(r, "lol.or.ecart", minute=10) == -300
    assert _valeur(r, "lol.xp.ecart", minute=10) == -500
    assert _valeur(r, "lol.farm.cs_par_minute") == pytest.approx(160 / 25)
    assert _valeur(r, "lol.morts.part_isolees") == 50.0
    assert _valeur(r, "lol.morts.part_avant_objectif") == 50.0
    assert _valeur(r, "lol.morts.part_sans_balise_recente") == 50.0
    assert _valeur(r, "lol.vision.score_par_minute") == pytest.approx(1.2)
    assert _valeur(r, "lol.vision.ecart_score") == 12
    assert _valeur(r, "lol.objectifs.participation_monstres") == 100.0
    assert _valeur(r, "lol.objectifs.participation_tours") == 0.0
    assert _valeur(r, "lol.combat.participation_kills") == 50.0
    assert _valeur(r, "lol.combat.degats_par_minute") == 600
    # Contexte : champion, rôle, classe, patch, adversaire.
    m = next(x for x in r.mesures if x.nom == "lol.farm.cs_par_minute")
    assert m.contexte == {
        "champion": "Ahri",
        "role": "MIDDLE",
        "patch": "15.20",
        "classe": "mage/assassin",
        "adversaire": "Zed",
    }
    textes = [p.texte for p in r.preuves]
    assert any(
        t.startswith("12:00 — tué par Zed : isolée") and "40 s avant le dragon" in t for t in textes
    )
    assert "À 10:00 : 80 sbires avec Ahri contre 90 pour Zed (-10)" in textes


def test_support_pas_juge_sur_le_farm():
    d = partie_lol(poste_moi="UTILITY")
    r = analyser_lol(d["match"], d["timeline"], MOI)
    noms = {m.nom for m in r.mesures}
    assert "lol.farm.cs" not in noms and "lol.farm.cs_par_minute" not in noms
    assert "lol.or.ecart" in noms  # l'or reste comparé


def test_fiche_et_replay_lol():
    d = partie_lol()
    f = fiche_lol(d)
    assert (f.carte, f.mode, f.resultat, f.duree_s) == (
        "Ahri — milieu",
        "classée solo",
        "victoire",
        1500,
    )
    assert f.details["kda"] == "4/2/6" and f.details["adversaire"] == "Zed"
    replay = donnees_replay(d)
    assert len(replay["minutes"]) == 26 and replay["joueurs"][2]["moi"]
    assert {e["type"] for e in replay["evenements"]} == {
        "CHAMPION_KILL",
        "ELITE_MONSTER_KILL",
        "BUILDING_KILL",
    }


# --- Références méta et débrief -------------------------------------------------------------


def test_meta_echantillons_et_cible(base):
    d = partie_lol()
    ech = meta.echantillons_lol(d["match"], d["timeline"])
    # Chacun des 10 joueurs est analysé ; repli « même rôle » ajouté.
    cles = {json.dumps(c, sort_keys=True) for n, c, p, v in ech if n == "lol.farm.cs_par_minute"}
    assert '{"champion": "Ahri", "role": "MIDDLE"}' in cles and '{"role": "MIDDLE"}' in cles
    lignes = meta.agreger(ech * 25, "haut classement EUW1", minimum=20)
    base.enregistrer_references(lignes)
    contexte = {"champion": "Ahri", "role": "MIDDLE", "patch": "15.20", "classe": "mage"}
    cible, source = cible_contextuelle(base, "lol.farm.cs_par_minute", contexte)
    assert cible == pytest.approx(6.4)
    assert source == "haut classement EUW1, 25 échantillons, patch 15.20"
    # Champion jamais vu en haut classement : repli sur le rôle, signalé.
    contexte["champion"] = "Aurelion"
    cible, source = cible_contextuelle(base, "lol.farm.cs_par_minute", contexte)
    assert cible == pytest.approx(6.4) and "même rôle, tous champions" in source
    # Nouveau patch sans référence : on garde l'ancienne en le disant.
    contexte.update(champion="Ahri", patch="15.21")
    _, source = cible_contextuelle(base, "lol.farm.cs_par_minute", contexte)
    assert "pas encore de référence pour le patch 15.21" in source


def test_debrief_utilise_la_cible_meta(base, cfg, tmp_path):
    from postgame.debrief.constats import construire_constats

    pid = base.ajouter_partie(
        Partie(
            jeu="lol",
            date_partie="2026-10-12T20:00:00+00:00",
            mode="classée solo",
            carte="Ahri — milieu",
            resultat="defaite",
            source="x",
            fichier="x",
            empreinte="l",
        )
    )
    contexte = {"champion": "Ahri", "role": "MIDDLE", "patch": "15.20", "n": 30}
    base.remplacer_mesures(
        pid, [Mesure("lol.vision.score_par_minute", 1, 0.8, "pts/min", contexte)]
    )
    base.enregistrer_references(
        [
            {
                "jeu": "lol",
                "nom": "lol.vision.score_par_minute",
                "contexte": {"champion": "Ahri", "role": "MIDDLE"},
                "patch": "15.20",
                "valeur": 1.1,
                "n": 40,
                "source": "haut classement EUW1",
            }
        ]
    )
    constats, _ = construire_constats(base, base.partie(pid), experimentales=True)
    c = constats[0]
    assert c.cible == 1.1 and c.source_cible.startswith("haut classement EUW1, 40 échantillons")
    assert c.contexte["patch"] == "15.20"


# --- TFT ------------------------------------------------------------------------------------


def test_tft_fiche_et_analyse():
    d = partie_tft(placement=3)
    f = fiche_tft(d)
    assert (f.carte, f.resultat, f.score_joueur, f.mode) == (
        "Set 15 — Bastion",
        "victoire",
        3,
        "classée",
    )
    r = analyser_tft(d)
    assert _valeur(r, "tft.placement", set=15, patch="15.20") == 3
    assert _valeur(r, "tft.top4") == 100.0
    assert r.preuves[0].texte == "3e avec Bastion 4 (niveau 8, 4 or restant)"


def test_tft_stats_par_patch():
    obs = []
    for place in (1, 2, 3):  # Bastion + Ahri : 1re, 2e, 3e au patch 15.20
        obs += observations(partie_tft(place)["match"], {MOI})
    obs += observations(partie_tft(8, version="Version 15.19.1")["match"], {MOI})
    stats = statistiques(obs)
    # 15.19 : une seule partie → listée, mais aucun élément ne passe le minimum de 3.
    assert set(stats) == {"15|15.20", "15|15.19"} and stats["15|15.19"]["elements"] == []
    s = stats["15|15.20"]
    assert s["place_moyenne"] == 2.0
    # Clés = identifiants bruts de Riot (stables) ; le nom affiché vient de traduire().
    ahri = next(e for e in s["elements"] if e["nom"] == "TFT15_Ahri")
    assert (ahri["parties"], ahri["place_moyenne"], ahri["ecart"]) == (3, 2.0, 0.0)
    reference = {
        "15|15.20": {
            "parties": 50,
            "elements": [
                {
                    "type": "unite",
                    "nom": "TFT15_Ahri",
                    "parties": 30,
                    "place_moyenne": 3.9,
                    "ecart": -0.6,
                },
                {
                    "type": "unite",
                    "nom": "TFT15_Jinx",
                    "parties": 20,
                    "place_moyenne": 3.2,
                    "ecart": -1.3,
                },
            ],
        }
    }
    comp = comparer(stats, reference)["15|15.20"]
    assert next(e for e in comp["elements"] if e["nom"] == "TFT15_Ahri")["ref_place_moyenne"] == 3.9
    assert [e["nom"] for e in comp["a_essayer"]] == ["TFT15_Jinx"]
    traduit = traduire({"15|15.20": comp}, {"TFT15_Jinx": "Jinx (officiel)"})["15|15.20"]
    assert traduit["a_essayer"][0]["libelle"] == "Jinx (officiel)"
    assert next(e for e in traduit["elements"] if e["nom"] == "TFT15_Ahri")["libelle"] == "Ahri"


# --- Client Riot ----------------------------------------------------------------------------


def test_limiteur_respecte_les_fenetres():
    temps = [0.0]
    attentes = []

    def dormir(s):
        attentes.append(s)
        temps[0] += s

    lim = Limiteur([(2, 1.0), (3, 10.0)], horloge=lambda: temps[0], dormir=dormir)
    for _ in range(4):
        lim.attendre()
    # 2 requêtes, attente ~1 s, 3e requête, puis attente jusqu'à 10 s pour la 4e.
    assert attentes[0] == pytest.approx(1.01, abs=0.02)
    assert temps[0] == pytest.approx(10.01, abs=0.05)


def test_client_429_cache_et_erreurs(tmp_path):
    appels = []

    def repondre(req: httpx.Request) -> httpx.Response:
        appels.append(str(req.url))
        assert req.headers["X-Riot-Token"] == "cle"
        if "matches/EUW1_1" in str(req.url) and len(appels) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        if "inconnu" in str(req.url):
            return httpx.Response(404)
        return httpx.Response(200, json={"ok": True})

    client = ClientRiot(
        "cle",
        dossier_cache=tmp_path,
        client=httpx.Client(transport=httpx.MockTransport(repondre)),
        limiteur=Limiteur([(100, 1.0)]),
        dormir=lambda s: None,
    )
    assert client.partie_lol("EUW1_1") == {"ok": True}
    assert client.partie_lol("EUW1_1") == {"ok": True}  # cache : pas de 3e appel
    assert len(appels) == 2 and appels[0].startswith("https://europe.api.riotgames.com/")
    with pytest.raises(ErreurRiot, match="introuvable"):
        client.partie_lol("inconnu")
    with pytest.raises(ErreurRiot, match="Pseudo#TAG"):
        client.compte("sans-tag")
    with pytest.raises(ErreurRiot, match="clé API Riot absente"):
        ClientRiot("")


class FauxClient:
    plateforme = "euw1"

    def __init__(self):
        self.lol, self.tft = ["EUW1_123"], ["EUW1_T1"]

    def compte(self, riot_id):
        assert riot_id == "iamheremyfriend#hiii"
        return {"puuid": MOI}

    def rangs_lol(self, puuid):
        return [{"queueType": "RANKED_SOLO_5x5", "tier": "GOLD", "rank": "II"}]

    def parties_lol(self, puuid, nombre=20, debut=0, file=None):
        return self.lol

    def parties_tft(self, puuid, nombre=20):
        return self.tft

    def partie_lol(self, match_id):
        return partie_lol()["match"]

    def chronologie_lol(self, match_id):
        return partie_lol()["timeline"]

    def partie_tft(self, match_id):
        return partie_tft()["match"]


def test_collecte(base, cfg):
    cfg.riot_id = "iamheremyfriend#hiii"
    collecteur = CollecteurRiot(base, cfg, FauxClient())
    bilan = collecteur.synchroniser()
    assert (bilan["lol"], bilan["tft"], bilan["erreurs"]) == (1, 1, [])
    assert collecteur.synchroniser()["lol"] == 0  # déjà vue
    lol = base.lister_parties(jeu="lol")[0]
    assert lol.details["rang"][0]["tier"] == "GOLD"
    assert base.mesures_partie(lol.id)
    with TestClient(creer_app(cfg, base=base, surveiller=False)) as c:
        assert c.get("/api/riot/etat").json()["riot_id"] == "iamheremyfriend#hiii"
        assert len(c.get(f"/api/lol/replay/{lol.id}").json()["minutes"]) == 26
        stats = c.get("/api/tft/stats").json()
        # Une seule partie TFT : place moyenne connue, détail par élément pas encore.
        assert stats["15|15.20"]["parties"] == 1 and stats["15|15.20"]["elements"] == []


def test_noms_tft_officiels(tmp_path):
    import httpx

    from postgame.games.riot.ddragon import DataDragon

    # Forme réelle des fichiers Data Dragon TFT (relevée sur la version 16.20.1).
    fichiers = {
        "/api/versions.json": ["16.20.1", "16.19.1"],
        "/cdn/16.20.1/data/fr_FR/tft-champion.json": {
            "type": "tft-champion",
            "data": {
                "Maps/Shipping/Map22/Sets/TFTSet18/Shop/DA_CrimsonRaptor18": {
                    "id": "DA_CrimsonRaptor18",
                    "name": "Maman Raptor",
                    "cost": 3,
                }
            },
        },
        "/cdn/16.20.1/data/fr_FR/tft-trait.json": {
            "data": {
                "DA_18_ZyraUniqueTrait": {"id": "DA_18_ZyraUniqueTrait", "name": "Dame des ronces"}
            }
        },
        "/cdn/16.20.1/data/fr_FR/tft-item.json": {"data": {}},
        "/cdn/16.20.1/data/fr_FR/tft-augments.json": {
            "augment-container": {},
            "data": {"DA_DoubleTrouble": {"id": "DA_DoubleTrouble", "name": "Doublure"}},
        },
    }
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=fichiers[r.url.path]))
    )
    noms = DataDragon(tmp_path, client).noms_tft("16.20")
    assert noms == {
        "DA_CrimsonRaptor18": "Maman Raptor",
        "DA_18_ZyraUniqueTrait": "Dame des ronces",
        "DA_DoubleTrouble": "Doublure",
    }
