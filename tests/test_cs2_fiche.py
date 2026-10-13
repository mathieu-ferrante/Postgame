"""Construction de la fiche CS2 à partir de données brutes.

DONNÉES DE SUBSTITUTION : les DataFrames ci-dessous sont fabriquées à la main pour imiter
ce que demoparser2 renvoie. Les colonnes et valeurs réelles restent à confirmer sur les
démos de Mathieu (voir A_VALIDER.md, L0) ; le test `test_cs2_demo_reelle.py` le fera.
"""

from datetime import UTC, datetime

import pandas as pd

from postgame.games.cs2.demo import DonneesDemo, construire_fiche, deduire_mode, trouver_joueur

MOI = "76561198000000001"


def _etat(score_t: int, score_ct: int, moi_equipe: int = 2, n_par_equipe: int = 5):
    lignes = []
    for i in range(n_par_equipe * 2):
        equipe = 2 if i < n_par_equipe else 3
        steamid = (
            MOI
            if (i == 0 and moi_equipe == 2) or (i == n_par_equipe and moi_equipe == 3)
            else str(76561198000000100 + i)
        )
        lignes.append(
            {
                "steamid": steamid,
                "name": "Mathieu" if steamid == MOI else f"j{i}",
                "tick": 100000,
                "team_num": equipe,
                "team_rounds_total": score_t if equipe == 2 else score_ct,
                "kills_total": 20 if steamid == MOI else 10,
                "deaths_total": 15,
                "assists_total": 4,
                "is_matchmaking": True,
                "match_making_mode": 1,
                "is_valve_dedicated_server": True,
            }
        )
    # Un spectateur (équipe 1) ne doit pas compter.
    lignes.append(
        {"steamid": "1", "name": "GOTV", "tick": 100000, "team_num": 1, "team_rounds_total": 0}
    )
    return pd.DataFrame(lignes)


def _donnees(etat, nb_rounds: int, nb_morts: int, entete=None, debut: int = 6400):
    rounds = pd.DataFrame(
        {"tick": [debut + 3000 * (i + 1) for i in range(nb_rounds)], "winner": [2] * nb_rounds}
    )
    morts = pd.DataFrame({"tick": [debut + 100 * (i + 1) for i in range(nb_morts)]})
    evenements = {
        "round_announce_match_start": pd.DataFrame({"tick": [debut]}),
        "round_end": rounds,
        "player_death": morts,
        # Des morts pendant l'échauffement ne doivent pas compter.
        "begin_new_match": pd.DataFrame({"tick": [debut]}),
    }
    evenements["player_death"] = pd.concat([pd.DataFrame({"tick": [10, 20, 30]}), morts])
    return DonneesDemo(
        entete=entete
        or {
            "map_name": "de_mirage",
            "server_name": "Valve CS2 EU West",
            "client_name": "",
            "demo_version_name": "valve_demo_2",
        },
        evenements=evenements,
        etat_final=etat,
        date_fichier=datetime(2026, 10, 1, 22, 0, tzinfo=UTC),
    )


def test_victoire_competitif():
    fiche = construire_fiche(_donnees(_etat(13, 7), nb_rounds=20, nb_morts=140), MOI)
    assert (fiche.mode, fiche.carte, fiche.resultat) == ("competitif", "de_mirage", "victoire")
    assert (fiche.score_joueur, fiche.score_adverse) == (13, 7)
    assert fiche.details["kills"] == 20
    assert fiche.details["nb_joueurs"] == 10
    assert fiche.details["nb_morts"] == 140  # échauffement exclu
    assert fiche.date_partie == "2026-10-01T22:00:00+00:00"
    # 20 rounds de 3000 ticks après le début → 60000 ticks / 64.
    assert fiche.duree_s == round(60000 / 64, 1)


def test_defaite_cote_ct():
    fiche = construire_fiche(_donnees(_etat(13, 10, moi_equipe=3), 23, 160), MOI)
    assert fiche.resultat == "defaite"
    assert (fiche.score_joueur, fiche.score_adverse) == (10, 13)


def test_match_nul():
    fiche = construire_fiche(_donnees(_etat(12, 12), 24, 170), MOI)
    assert fiche.resultat == "nul"
    assert fiche.mode == "autre"  # 12-12 : aucune équipe à 13, mode non tranché


def test_joueur_absent_resultat_inconnu():
    fiche = construire_fiche(_donnees(_etat(13, 5), 18, 120), "76561190000000000")
    assert fiche.resultat == "inconnu"
    assert fiche.details["joueur_trouve"] is False


def test_joueur_trouve_par_nom_client():
    donnees = _donnees(
        _etat(13, 5), 18, 120, entete={"map_name": "de_inferno", "client_name": "Mathieu"}
    )
    assert trouver_joueur(donnees, "")["steamid"] == MOI
    assert construire_fiche(donnees, "").resultat == "victoire"


def test_deathmatch():
    etat = _etat(0, 0)
    fiche = construire_fiche(_donnees(etat, nb_rounds=1, nb_morts=300), MOI)
    assert fiche.mode == "deathmatch"
    assert fiche.resultat == "sans_objet"
    assert fiche.score_joueur is None


def test_demo_sans_evenement():
    donnees = DonneesDemo(
        entete={"map_name": "de_dust2"},
        evenements={},
        etat_final=pd.DataFrame(),
        date_fichier=datetime(2026, 1, 1, tzinfo=UTC),
    )
    fiche = construire_fiche(donnees, MOI)
    assert (fiche.carte, fiche.resultat, fiche.duree_s) == ("de_dust2", "inconnu", None)


def test_deduire_mode_par_type_de_classement_et_serveur():
    assert deduire_mode(10, 21, 150, 13, type_classement=11) == "premier"
    assert deduire_mode(10, 21, 150, 13, type_classement=6) == "competitif"
    assert deduire_mode(4, 14, 60, 9, type_classement=7) == "wingman"
    assert deduire_mode(10, 21, 150, 13, serveur="FACEIT.com | EU Server 12") == "faceit"


def test_premier_et_classement():
    etat = _etat(13, 9)
    etat["comp_rank_type"] = 11
    etat["rank"] = 15230
    fiche = construire_fiche(_donnees(etat, 22, 160), MOI)
    assert fiche.mode == "premier" and fiche.details["classement"] == 15230


def test_deduire_mode():
    assert deduire_mode(16, 1, 400, 0) == "deathmatch"
    assert deduire_mode(4, 14, 60, 9) == "wingman"
    assert deduire_mode(10, 21, 150, 13) == "competitif"
    assert deduire_mode(10, 5, 40, 5) == "autre"


def test_joueur_trouve_par_pseudo_configure():
    donnees = _donnees(_etat(13, 5), 18, 120, entete={"map_name": "de_nuke", "client_name": ""})
    donnees.etat_final.loc[donnees.etat_final["steamid"] == MOI, "name"] = "JEANMARKKARROK SKIN"
    assert trouver_joueur(donnees, "", ["jeanmarkkarrok skin"])["steamid"] == MOI
    assert trouver_joueur(donnees, "", ["autre"]) is None


def test_demo_gotv_de_tournoi_sans_round_end():
    # Cas réel (ESL Pro League S24, Falcons vs Spirit) : pas d'évènement round_end, 146 morts.
    donnees = _donnees(_etat(8, 13, moi_equipe=3), nb_rounds=0, nb_morts=146)
    fiche = construire_fiche(donnees, MOI)
    assert fiche.mode == "competitif" and fiche.details["nb_rounds"] == 21
    assert (fiche.resultat, fiche.score_joueur, fiche.score_adverse) == ("victoire", 13, 8)
