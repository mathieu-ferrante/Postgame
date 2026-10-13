# Débrief — fonctionnement (COM-04, COM-05, COM-06, NF-04, NF-05, NF-06)

## 1. Constats chiffrés

Pour chaque mesure de la partie (hors mesures « neutres » comme un simple nombre de flashs)
on calcule :

- la **référence personnelle** : moyenne de la même mesure (même contexte : arme, tranche…)
  sur les 10 parties précédentes du même jeu et du même mode ;
- la **cible** quand elle existe (`src/postgame/debrief/objectifs.py`, **cibles
  provisoires** en attendant des cibles calculées sur les démos pros) ;
- l'**impact estimé** = poids × confiance × (écart à la cible + ½ × dégradation par rapport
  à l'habitude), les écarts étant exprimés en « échelles » (10 points de %, 50 ms, 2°…) ;
  confiance = min(1, échantillon / 20). Un écart dans le bon sens ne compte pas.

Les mesures dont l'échantillon est inférieur à 5 sont ignorées. Les **3 constats d'impact
le plus fort** (mesures distinctes) sont les priorités, suivis de 2 points forts au plus et
du détail. Chaque constat porte jusqu'à 5 preuves avec un lien `/replay/<partie>?tick=<t>`.

## 2. Fiabilité (NF-06)

Une mesure n'entre dans le débrief que si elle est **fiable** : vérifiée à la main sur 5
cas réels (`python -m postgame verifier <partie>`), puis marquée :

```
python -m postgame fiabilite cs2.contre_strafe.part_tirs_precis --note "5 cas vérifiés le …"
```

La fiabilité est liée à la **version** de la mesure : si son calcul change (nouvelle
version), elle redevient non fiable jusqu'à une nouvelle vérification. Pendant la phase de
validation, `mesures_experimentales = true` dans `[debrief]` les affiche quand même, marquées
« mesure en cours de validation ».

## 3. Rédaction (COM-05)

Fournisseur au choix (`[debrief] fournisseur`) : `gemini` (défaut), `local` (Ollama) ou
`aucun`. Sans modèle, ou si le modèle échoue, le débrief structuré est affiché tel quel.

Ce qui part vers le modèle : libellé de la mesure, valeur, unité, sens, référence
personnelle, cible, taille d'échantillon, contexte (arme, site…), nombre de moments de
replay. **Jamais** : noms de joueurs, SteamID, chemins, démos, textes des preuves (NF-05).

Le modèle doit citer `[C1]`, `[C2]`… Tout chiffre de sa réponse qui n'est pas dans les
données envoyées (aux arrondis près) fait **rejeter** le texte : le débrief structuré est
gardé, le texte rejeté est conservé pour analyse (`contenu.texte_rejete`).

## 4. Coût (NF-04)

Le coût de chaque débrief est calculé à partir des jetons réellement comptés par
l'API (`usageMetadata.promptTokenCount`, `candidatesTokenCount` + `thoughtsTokenCount`) et
des prix configurés (défaut `gemini-3.1-flash-lite` : 0,25 $ / 1,50 $ par million de jetons,
tarifs relevés en octobre 2026). Cumul : `python -m postgame couts` ou
`GET /api/debriefs/couts`.

Ordre de grandeur attendu (à confirmer sur un vrai débrief) : ~3 000 jetons envoyés et
~1 000 reçus, soit environ 0,002 $ par débrief ; 15 € couvrent alors plusieurs milliers de
débriefs.
