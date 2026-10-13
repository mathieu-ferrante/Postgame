# Mesures CS2 — méthode

Chaque mesure est versionnée (nom, version, unité) ; la liste à jour est servie par
`GET /api/mesures/definitions`. Statut « fiable » : seulement après vérification à la main
de 5 cas sur une vraie démo (`python -m postgame verifier <partie>`). **À ce jour, aucune
mesure n'est fiable** : toutes sont testées sur scénarios synthétiques uniquement.

## L1 — Mécanique (CS-AIM-01 à 06)

Données : position, vitesse, angles de vue, aim punch, arme, indicateur « repéré » de
chaque joueur à chaque tick ; évènements `weapon_fire`, `player_hurt`, `player_death`.

**Engagement** : un tir ouvre un engagement si le précédent date de plus de 0,5 s ou était
fait avec une autre arme. **Rafale** : tirs consécutifs espacés de moins de 1,6 × la
cadence de l'arme. **Touche** : un `player_hurt` du joueur dans les 2 ticks suivant le tir.

| Mesure | Calcul | Limites connues |
|---|---|---|
| `cs2.contre_strafe.part_tirs_precis` | Part des tirs (hors pompes) faits à une vitesse ≤ 34 % de la vitesse max de l'arme. Aussi par arme. | Vitesse calculée par demoparser2 (écart de position entre ticks) ; vitesses max d'après les fiches d'armes, à revérifier après les mises à jour. |
| `cs2.contre_strafe.part_premieres_balles_precises`, `…vitesse_mediane_premiere_balle` | Idem sur la première balle de chaque engagement. Preuves : les 5 premières balles les plus rapides. | |
| `cs2.premiere_balle.precision`, `.headshot` | Part des premières balles qui touchent / touchent la tête. Aussi par arme. | Un tir à travers un mur qui touche compte comme touché. |
| `cs2.spray.touche_par_tranche` | Part des balles qui touchent, par rang dans la rafale : 1, 2-5, 6-10, 11+ (rafales de 5 balles et plus, armes automatiques). | |
| `cs2.spray.erreur_mediane_par_tranche` | Angle entre la direction du tir (vue + 2 × aim punch) et la tête de la cible, médiane par tranche. Cible = joueur le plus touché par la rafale, sinon l'adversaire le plus proche du viseur (< 10°). | Ignore la dispersion aléatoire (inaccuracy) : mesure la compensation du recul, pas le hasard. |
| `cs2.spray.balle_decrochage` | Premier rang ≥ 4 où l'erreur médiane dépasse 1,5° et le double de celle des 3 premières balles, deux rangs de suite (3 rafales minimum par rang). | |
| `cs2.viseur.ecart_median`, `.part_ecart_sous_5deg` | À chaque apparition d'un adversaire (passage à « repéré par moi » après 0,5 s sans l'être), angle entre le regard et sa tête (yeux à +64 u, +46 accroupi). | L'indicateur « repéré » est une approximation de la visibilité (cahier des charges : affiner plus tard par lancer de rayons). |
| `cs2.viseur.ecart_vertical_moyen`, `.ecart_horizontal_moyen` | Moyennes signées : vertical > 0 = viseur trop bas, horizontal > 0 = trop à gauche. | |
| `cs2.viseur.pitch_median_deplacement` | Inclinaison médiane du regard en déplacement (> 150 u/s) sans adversaire repéré. 0 = horizon. | Dépend des cartes et des dénivelés. |
| `cs2.reaction.delai_median` | De l'apparition au premier tir dirigé vers l'adversaire (< 8° de sa tête, recul compris), dans les 2 s. | Hérite de l'approximation « repéré ». |
| `cs2.ttk.median` | Du premier tir sur un adversaire apparu à sa mort par le joueur (< 5 s). | |
| `cs2.armes.kills`, `.headshot`, `.precision`, `.degats` | Par arme, plus globaux pour headshot et précision. | |

En deathmatch (un seul round), tous les autres joueurs sont traités comme adversaires.

## L2 — Utilitaires et positionnement (CS-UTL-02/03/04, CS-POS-01/02/03)

Données supplémentaires : `player_blind`, éclatements de grenades (`flashbang_detonate`,
`hegrenade_detonate`, `smokegrenade_detonate/expired`, `molotov_detonate`,
`inferno_startburn/expire`), `grenade_thrown`, inventaire (propriété `inventory`) en début et
fin de round et juste avant chaque mort. Un feu est rattaché au `molotov_detonate` le plus
proche (± 2 ticks, < 300 u) quand l'évènement ne porte pas le lanceur.

| Mesure | Calcul | Limites connues |
|---|---|---|
| `cs2.flash.nombre`, `.adversaires_aveugles_par_flash`, `.duree_aveuglement_adversaires` | Aveuglements ≥ 1 s rattachés à la flash (même tick à 2 près, lanceur = Mathieu). | Seuil de 1 s arbitraire (un aveuglement plus court gêne peu). |
| `cs2.flash.coequipiers_aveugles` | Coéquipiers (et Mathieu) aveuglés ≥ 1 s. | |
| `cs2.flash.part_convertie` | Flash suivie dans les 2 s d'un kill de l'équipe sur un adversaire aveuglé. | |
| `cs2.flash.part_inutile` | Flash sans adversaire aveuglé ≥ 1 s. | Une flash « de sortie » qui empêche un peek sans aveugler compte comme inutile. |
| `cs2.he.degats_moyens`, `.degats_coequipiers` | `player_hurt` avec l'arme `hegrenade` dans les 2 ticks de l'éclatement. | |
| `cs2.molotov.duree_moyenne`, `.degats_moyens` | Du début à la fin du feu ; dégâts `inferno` sur cette durée. | |
| `cs2.molotov.adversaires_deloges` | Adversaires vivants à moins de 250 u du feu à l'allumage, hors zone 3 s plus tard (et vivants). | Rayon fixe : la forme réelle du feu dépend du sol. |
| `cs2.utilitaires.valeur_perdue_par_mort` | Prix des grenades en poche 1 tick avant la mort (flash 200, smoke 300, HE 300, molotov 400, leurre 50). | Le prix de l'incendiaire (500 $ côté CT) est compté comme un molotov. |
| `cs2.utilitaires.part_rounds_sans_lancer` | Rounds commencés avec au moins une grenade sans aucun lancer. | |
| `cs2.position.kill`, `.mort` (preuves) | Position, camp, arme de chaque kill / mort : cartes de chaleur (`GET /api/cs2/chaleur`). | |
| `cs2.position.distance_coequipier_a_la_mort`, `.part_morts_isolees` | Distance 2D au coéquipier vivant le plus proche 1 tick avant la mort ; isolée au-delà de 1000 u. | Distance à vol d'oiseau : un mur entre les deux n'est pas pris en compte. |
| `cs2.trades.part_morts_tradees` | Le tueur de Mathieu meurt sous les balles de son équipe dans les 5 s. | |
| `cs2.trades.part_tradables_non_tradees` | Parmi les morts avec un coéquipier à moins de 800 u, part non vengée ; les preuves nomment les coéquipiers proches. | |
| `cs2.trades.reussis`, `.delai_median`, `.occasions_manquees` | Coéquipier tué : Mathieu tue le tueur dans les 5 s (réussi), ou était vivant à moins de 800 u et personne ne l'a vengé (manqué). | |

Mesures d'équipe (gaspillage, isolement, trades) non calculées en deathmatch.
