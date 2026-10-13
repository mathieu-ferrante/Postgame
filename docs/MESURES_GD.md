# Mesures Geometry Dash — méthode (L8)

Source : journaux du mod Geode « Postgame — journal » (`mods/gd-journal`), une séance par
passage dans un niveau. Toutes les mesures sont **non vérifiées sur une vraie séance**.

## Alignement des essais (GD-02)

Tous les essais sont alignés sur la position X dans le niveau. Les appuis de tous les
essais sont triés par position et regroupés quand deux voisins sont à moins de 12 u ;
un groupe présent dans au moins 3 essais est un **input attendu** (centre = médiane).
Chaque essai y rattache au plus un appui, le plus proche du centre.

**Décalage** d'un appui = instant de l'appui − instant où l'essai atteint le centre de
l'input (interpolé sur les positions journalisées toutes les 4 frames). Négatif = trop tôt.

| Mesure | Calcul |
|---|---|
| `gd.regularite.ecart_type_median` | Médiane, sur les inputs attendus, de l'écart-type des décalages (ms). |
| `gd.regularite.decalage_moyen` | Moyenne de tous les décalages : tendance trop tôt / trop tard. |
| `gd.regularite.part_inputs_stables` | Part des inputs dont l'écart-type est sous 15 ms. |
| `gd.instables.part_morts_apres_instables` (GD-03) | Part des morts survenues juste après l'un des 5 inputs les plus irréguliers ; les preuves listent ces 5 inputs (position en %, écart-type, tendance, morts juste après / passages). |
| `gd.mort` (preuves, GD-04) | Chaque mort : %, X, mode, objet touché — carte des morts. |
| `gd.survie.par_segment` (GD-04) | Par tranche de 10 % : part des essais normaux arrivés dans la tranche qui en sortent vivants. |
| `gd.spam.cps_moyen`, `gd.spam.irregularite` (GD-05) | Passages de 4 appuis ou plus espacés de moins de 150 ms : cadence (clics/s) et écart-type / moyenne des intervalles. |
| `gd.progression.*` (GD-06) | Meilleur %, % moyen, écart-type du % (mode normal), nombre d'essais normaux et d'entraînement. |
| `gd.practice.gain` (GD-06) | % moyen des essais normaux après le premier essai d'entraînement de la séance, moins celui d'avant (3 essais minimum de chaque côté). |
| `gd.technique.resolution_ms` | Plus grand pas de temps dont tous les instants de clic (temps du niveau) sont des multiples : précision réelle de l'horodatage (risque du cahier des charges). |

La longueur du niveau (100 %) est déduite des morts (`x / pct`), ou d'un essai terminé.
Les niveaux plateforme n'ont pas d'analyse de régularité (pas d'« input attendu » à
position fixe).

## Replay (GD-07)

`GET /api/gd/replay/{partie}` et la page « essais superposés » : tous les essais sur le
profil du niveau, appuis, morts, inputs attendus colorés selon leur écart-type.

## Second écran (GD-08)

Le mod vide son journal à chaque ligne : le service lit seulement les lignes ajoutées
(toutes les 0,5 s, quelques octets) et la page « En direct » affiche la séance en cours :
position de l'essai en %, meilleur %, moyenne des 10 derniers essais normaux, zones de mort
de la séance. Depuis les séances déjà analysées du même niveau : les passages les plus
irréguliers (avec trop tôt / trop tard) et les zones où Mathieu meurt le plus. Aucun calcul
lourd pendant le jeu : l'analyse complète reste faite après la séance.
