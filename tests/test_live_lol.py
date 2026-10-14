"""Second écran LoL (LOL-07) sur un exemple de réponse de la Live Client Data API.

DONNÉES DE SUBSTITUTION : réponse construite d'après la documentation de Riot ; à vérifier
pendant une vraie partie (A_VALIDER.md).
"""

import httpx

from postgame.db import Mesure, Partie
from postgame.live.lol import ScruteurLoL, resumer


def donnees(temps=600.0):
    return {
        "activePlayer": {"riotId": "iamheremyfriend#hiii", "level": 9, "currentGold": 812.4},
        "allPlayers": [
            {
                "riotId": "iamheremyfriend#hiii",
                "championName": "Ahri",
                "team": "ORDER",
                "position": "MIDDLE",
                "level": 9,
                "scores": {
                    "kills": 2,
                    "deaths": 1,
                    "assists": 3,
                    "creepScore": 70,
                    "wardScore": 7.5,
                },
                "items": [{"displayName": "Malédiction de Luden"}],
            },
            {
                "riotId": "adv#euw",
                "championName": "Zed",
                "team": "CHAOS",
                "position": "MIDDLE",
                "level": 10,
                "scores": {"creepScore": 84},
            },
        ],
        "gameData": {"gameTime": temps},
    }


def test_resumer():
    r = resumer(donnees(), {"cs_par_minute_moyen": 6.9})
    assert (r["champion"], r["cs"], r["cs_par_minute"], r["or"]) == ("Ahri", 70, 7.0, 812)
    assert r["adversaire"] == {"champion": "Zed", "cs": 84, "niveau": 10}
    assert r["objets"] == ["Malédiction de Luden"] and r["reperes"]["cs_par_minute_moyen"] == 6.9
    assert resumer(donnees(temps=30))["cs_par_minute"] is None  # avant 1 min : pas de taux


def test_scruteur(base):
    pid = base.ajouter_partie(
        Partie(
            jeu="lol",
            date_partie="2026-10-01T20:00:00+00:00",
            mode="classée solo",
            carte="Ahri — milieu",
            resultat="victoire",
            source="x",
            fichier="x",
            empreinte="z",
        )
    )
    base.remplacer_mesures(
        pid,
        [
            Mesure(
                "lol.farm.cs_par_minute",
                1,
                6.5,
                "sbires/min",
                {"champion": "Ahri", "role": "MIDDLE"},
            )
        ],
    )
    en_partie = {"oui": True}

    def repondre(requete):
        assert str(requete.url) == "https://127.0.0.1:2999/liveclientdata/allgamedata"
        return httpx.Response(200, json=donnees()) if en_partie["oui"] else httpx.Response(404)

    s = ScruteurLoL(base, client=httpx.Client(transport=httpx.MockTransport(repondre)))
    s.passe()
    assert s.resume["actif"] and s.resume["reperes"]["cs_par_minute_moyen"] == 6.5
    en_partie["oui"] = False
    s.passe()
    assert s.resume == {"actif": False}


def test_trouver_le_joueur_actif_quel_que_soit_le_format_du_nom():
    from postgame.live.lol import trouver_moi

    joueurs = [
        {"riotId": "Autre#EUW", "championName": "Ahri"},
        {"riotIdGameName": "iamheremyfriend", "riotIdTagLine": "hiii", "championName": "Jinx"},
    ]
    # Format actuel (Riot ID complet), nom de jeu seul, ancien summonerName : même joueur.
    for actif in (
        {"riotId": "iamheremyfriend#hiii"},
        {"riotIdGameName": "iamheremyfriend"},
        {"summonerName": "IAMHEREMYFRIEND#hiii"},
    ):
        assert trouver_moi(actif, joueurs)["championName"] == "Jinx"
    assert trouver_moi({}, joueurs) is None


def test_reference_haut_classement_par_champion_et_role(base):
    from postgame.live.lol import reperes

    base.enregistrer_references(
        [
            {
                "jeu": "lol",
                "nom": "lol.farm.cs_par_minute",
                "contexte": {"champion": "Ahri", "role": "MIDDLE"},
                "patch": "16.20",
                "valeur": 8.4,
                "n": 40,
                "source": "Challenger",
            },
            {
                "jeu": "lol",
                "nom": "lol.farm.cs_par_minute",
                "contexte": {"role": "MIDDLE"},
                "patch": "16.20",
                "valeur": 7.9,
                "n": 300,
                "source": "Challenger",
            },
        ]
    )
    assert reperes(base, "Ahri", "MIDDLE")["cs_par_minute_meta"] == 8.4
    assert reperes(base, "Syndra", "MIDDLE")["cs_par_minute_meta"] == 7.9  # repli : le rôle
    assert reperes(base, "Ahri", None)["cs_par_minute_meta"] is None


def test_second_ecran_lol_ne_meurt_pas(base):
    import httpx

    from postgame.live.lol import ScruteurLoL

    # Réponse inattendue du client LoL (une liste au lieu d'un objet).
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[1, 2])))
    s = ScruteurLoL(base, client=client)
    tours = []

    def attendre(_duree):
        tours.append(1)
        if len(tours) == 2:
            s._arret.set()
        return s._arret.is_set()

    s._arret.wait = attendre
    s._boucle()  # deux passes en erreur : la boucle continue, sans lever
    assert len(tours) == 2 and s.resume == {"actif": False}
