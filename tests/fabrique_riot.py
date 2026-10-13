"""Parties LoL et TFT synthétiques au format de l'API Riot (match-v5, timeline, tft-match-v1).

DONNÉES DE SUBSTITUTION : construites à la main pour que chaque résultat se calcule sur
papier. Elles suivent la structure documentée par Riot, pas de vraies parties de Mathieu.
"""

from __future__ import annotations

MOI = "puuid-mathieu"
POSTES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
CHAMPIONS = ["Garen", "LeeSin", "Ahri", "Jinx", "Thresh", "Darius", "Vi", "Zed", "Caitlyn", "Lulu"]


def participants(poste_moi="MIDDLE"):
    """10 joueurs ; Mathieu (participant 3) joue Ahri au milieu, contre Zed (participant 8)."""
    liste = []
    for i in range(10):
        poste = POSTES[i % 5]
        liste.append(
            {
                "participantId": i + 1,
                "puuid": MOI if i == 2 else f"puuid-{i + 1}",
                "championName": CHAMPIONS[i],
                "teamId": 100 if i < 5 else 200,
                "teamPosition": poste,
                "win": i < 5,
                "kills": 4 if i < 5 else 2,
                "deaths": 2,
                "assists": 6,
                "totalMinionsKilled": 150,
                "neutralMinionsKilled": 10,
                "visionScore": 30 if i != 7 else 18,
                "wardsPlaced": 9,
                "wardsKilled": 3,
                "visionWardsBoughtInGame": 2,
                "totalDamageDealtToChampions": 15000,
            }
        )
    if poste_moi != "MIDDLE":
        liste[2]["teamPosition"] = liste[7]["teamPosition"] = poste_moi
    return liste


def frame(minute, cs_moi, cs_adv, or_moi, or_adv, positions=None):
    pf = {}
    for pid in range(1, 11):
        x, y = (positions or {}).get(pid, (7000 + 100 * pid, 7000))
        pf[str(pid)] = {
            "participantId": pid,
            "position": {"x": x, "y": y},
            "minionsKilled": 0,
            "jungleMinionsKilled": 0,
            "totalGold": 500,
            "xp": 0,
        }
    pf["3"].update(minionsKilled=cs_moi, totalGold=or_moi, xp=4000)
    pf["8"].update(minionsKilled=cs_adv, totalGold=or_adv, xp=4500)
    return {"timestamp": minute * 60000, "participantFrames": pf, "events": []}


def partie_lol(poste_moi="MIDDLE"):
    """Partie de 25 min. À 10 min : 80 sbires contre 90 (−10), 3 500 or contre 3 800.
    Morts de Mathieu :
      - 12:00 en (2000, 2000), alliés tous vers (7000, 7000) → isolée ; le dragon adverse
        tombe à 12:40 (40 s après) ; aucune balise posée avant ;
      - 18:00 en (7300, 7000), allié à 0 u → pas isolée ; balise posée à 17:00.
    Objectifs de l'équipe de Mathieu : un dragon à 20:00 (Mathieu assiste) et une tour
    adverse à 22:00 loin de lui → participation monstres 100 %, tours 0 %."""
    frames = [frame(m, 8 * m, 9 * m, 350 * m, 380 * m) for m in range(26)]
    frames[12]["events"] = [
        {
            "type": "CHAMPION_KILL",
            "timestamp": 12 * 60000,
            "killerId": 8,
            "victimId": 3,
            "position": {"x": 2000, "y": 2000},
        },
        {
            "type": "ELITE_MONSTER_KILL",
            "timestamp": 12 * 60000 + 40000,
            "killerId": 7,
            "killerTeamId": 200,
            "monsterType": "DRAGON",
            "position": {"x": 9800, "y": 4400},
        },
    ]
    frames[17]["events"] = [{"type": "WARD_PLACED", "timestamp": 17 * 60000, "creatorId": 3}]
    frames[18]["events"] = [
        {
            "type": "CHAMPION_KILL",
            "timestamp": 18 * 60000,
            "killerId": 8,
            "victimId": 3,
            "position": {"x": 7300, "y": 7000},
        }
    ]
    frames[20]["events"] = [
        {
            "type": "ELITE_MONSTER_KILL",
            "timestamp": 20 * 60000,
            "killerId": 2,
            "killerTeamId": 100,
            "monsterType": "DRAGON",
            "assistingParticipantIds": [3],
            "position": {"x": 9800, "y": 4400},
        }
    ]
    frames[22]["events"] = [
        {
            "type": "BUILDING_KILL",
            "timestamp": 22 * 60000,
            "killerId": 1,
            "teamId": 200,
            "buildingType": "TOWER_BUILDING",
            "position": {"x": 13000, "y": 13000},
        }
    ]
    match = {
        "metadata": {"matchId": "EUW1_123"},
        "info": {
            "gameDuration": 1500,
            "gameStartTimestamp": 1_760_000_000_000,
            "gameVersion": "15.20.712.3456",
            "queueId": 420,
            "participants": participants(poste_moi),
        },
    }
    return {"format": 1, "puuid": MOI, "match": match, "timeline": {"info": {"frames": frames}}}


def partie_tft(
    placement=3,
    set_=15,
    version="Version 15.20.712.3456 (Oct 10 2025) [PUBLIC]",
    match_id="EUW1_T1",
):
    joueurs = []
    for i in range(8):
        joueurs.append(
            {
                "puuid": MOI if i == 0 else f"puuid-{i}",
                "placement": placement if i == 0 else (i if i < placement else i + 1),
                "level": 8,
                "gold_left": 4,
                "last_round": 33,
                "total_damage_to_players": 90,
                "traits": [
                    {"name": "TFT15_Bastion", "num_units": 4, "style": 2, "tier_current": 2},
                    {"name": "TFT15_Duelist", "num_units": 1, "style": 0, "tier_current": 0},
                ],
                "units": [
                    {
                        "character_id": "TFT15_Ahri",
                        "tier": 2,
                        "itemNames": ["TFT_Item_JeweledGauntlet"],
                    },
                    {"character_id": "TFT15_Garen", "tier": 1, "itemNames": []},
                ],
                "augments": ["TFT9_Augment_Something"],
            }
        )
    return {
        "format": 1,
        "puuid": MOI,
        "match": {
            "metadata": {"match_id": match_id},
            "info": {
                "game_datetime": 1_760_000_000_000,
                "game_length": 2100.5,
                "game_version": version,
                "queue_id": 1100,
                "tft_set_number": set_,
                "participants": joueurs,
            },
        },
    }
