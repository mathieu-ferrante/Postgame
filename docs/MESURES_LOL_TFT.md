# Mesures League of Legends et TFT — méthode (L9)

Source : API Riot avec la clé personnelle de Mathieu (match-v5 + chronologie, league-v4,
tft-match-v1, tft-league-v1, account-v1) et l'API locale du client LoL pendant une partie.
Toutes les mesures sont **non vérifiées sur de vraies parties** (clé pas encore fournie).

## Contexte de chaque mesure (CTX-01)

Chaque mesure LoL porte : champion, rôle, classe du champion (Data Dragon, par version),
patch, adversaire direct. Chaque mesure TFT porte : set et patch.

- L'**historique** de comparaison est celui du même contexte « discriminant » (même champion
  et même rôle ; même arme en CS2), tous patchs confondus.
- La **cible** vient des références de haut classement du **même patch** quand elles
  existent (`python -m postgame riot meta`), avec repli signalé sur « même rôle, tous
  champions », puis sur la cible provisoire. Le débrief affiche toujours l'origine de la cible.
- Le farm n'est pas jugé pour un support.

## LoL

| Mesure | Calcul | Limites |
|---|---|---|
| `lol.farm.cs` (10, 15, 20 min), `.cs_par_minute` | Sbires + monstres (chronologie), farm total / durée | — |
| `lol.farm.ecart_cs`, `lol.or.ecart`, `lol.xp.ecart` | Écart avec l'adversaire direct (même poste) à 10, 15, 20 min : benchmark du même rang (matchmaking) et du même rôle | Pas d'adversaire direct si les postes sont mal détectés par Riot |
| `lol.morts.part_isolees` | Aucun allié à moins de 2500 u (positions de la minute la plus proche) | Positions connues seulement à la minute |
| `lol.morts.part_avant_objectif` | Objectif adverse (dragon, nashor, héraut, structure) dans la minute qui suit la mort | — |
| `lol.morts.part_sans_balise_recente` | Aucune balise posée par Mathieu dans les 2 minutes avant la mort | Approximation de la vision : la chronologie ne donne pas la position des balises |
| `lol.vision.*` | Score de vision / min, écart avec l'adversaire direct, balises posées, détruites, de contrôle | — |
| `lol.combat.participation_kills`, `.degats_par_minute` | (kills + assistances) / kills de l'équipe ; dégâts aux champions / min | — |
| `lol.objectifs.participation_*` | Objectifs de l'équipe où Mathieu est tueur, assistant, ou à moins de 3000 u | Position à la minute |

Références méta : parties classées récentes de joueurs Challenger ; chacun des 10 joueurs
est analysé comme Mathieu ; médiane par (mesure, champion, rôle, minute) et par patch.

## TFT

| Mesure / vue | Calcul |
|---|---|
| `tft.placement`, `.top4`, `.degats_joueurs`, `.niveau_final`, `.or_restant`, `.dernier_round` | État final de Mathieu, par set et patch |
| Ce qui fait gagner des places (TFT-02) | Pour chaque trait actif (avec son nombre d'unités), unité, objet, augment : place moyenne quand il est joué, écart à la place moyenne du patch (≥ 3 parties) |
| Haut classement (TFT-03) | Mêmes statistiques sur les 8 joueurs de parties Challenger du même patch ; éléments forts en haut classement que Mathieu ne joue pas |
| Déroulé (TFT-04) | L'API ne fournit que l'état final : pas de déroulé étape par étape |

## Second écran LoL (LOL-07)

API locale du client (`https://127.0.0.1:2999/liveclientdata/allgamedata`), interrogée
2 fois par seconde pendant une partie : niveau, or, K/M/A, farm et farm par minute comparés
à la moyenne de Mathieu sur ce champion et à la référence méta, adversaire direct.
