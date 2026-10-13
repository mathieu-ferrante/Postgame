# API locale de Postgame (COM-07)

Service HTTP + JSON sur `http://<PC de jeu>:8765`. Documentation interactive générée
automatiquement (OpenAPI) : `http://<PC de jeu>:8765/docs`. Aucune authentification :
l'API n'est faite que pour le réseau local (interface web, téléphone, Mac, Jarvis).

Conventions : dates en ISO 8601 UTC ; noms de champs en français ; erreurs au format
FastAPI `{"detail": "message"}`.

## Service

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/sante` | `{"statut": "ok", "version", "schema", "parties"}` |
| GET | `/api/jeux` | Jeux pris en charge, extensions, dossiers surveillés (et s'ils existent), nombre de parties |

## Import

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/api/import` | Import manuel, formulaire multipart, champ `fichier`. Réponse `{"statut": "importe" \| "deja_connu", "message", "partie_id"}`. 415 si l'extension n'est pas prise en charge, 422 si le fichier est illisible. |
| GET | `/api/import/etat` | Dernière passe de surveillance, fichiers en attente de stabilité, 20 derniers fichiers traités (statut, message d'erreur éventuel) |

## Parties

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/parties?jeu=cs2&limite=50&decalage=0` | `{"total", "parties": [résumé]}` ; résumé = `id, jeu, date_partie, mode, carte, resultat, score_joueur, score_adverse, duree_s` |
| GET | `/api/parties/{id}` | Fiche complète (dont `details`, propre au jeu), ses `mesures` et ses `preuves` |

Valeurs de `resultat` : `victoire`, `defaite`, `nul`, `sans_objet` (deathmatch,
entraînement), `inconnu` (joueur non trouvé dans la démo : vérifier le SteamID dans
`postgame.toml`).

Valeurs de `mode` pour CS2 : `premier`, `competitif`, `faceit`, `wingman`, `deathmatch`, `autre` (type de classement du match, nom du serveur pour FACEIT).

## Mesures

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/mesures` | Noms des mesures présentes en base |
| GET | `/api/mesures/definitions` | Toutes les mesures connues : `nom, version, unite, description, sens, fiable` |
| GET | `/api/parties/{id}/preuves?mesure=…` | Moments du replay qui illustrent les mesures : `mesure, tick, round, texte, donnees` |
| GET | `/api/parties/{id}/mesures` | Mesures d'une partie : `nom, version, valeur, unite, contexte, calcule_le` |
| GET | `/api/progression/{nom}?periode=7j\|30j\|tout` | Série chronologique d'une mesure, un point par partie (COM-03) |

Une mesure a un nom à points (`cs2.contre_strafe.part_tirs_precis`), une version entière
(incrémentée quand son calcul change ; `python -m postgame reanalyser` recalcule alors tout
l'historique, COM-08), une unité et un contexte JSON (arme, camp, taille d'échantillon…).

## Débrief

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/parties/{id}/debrief?regenerer=false` | Dernier débrief (généré s'il n'existe pas) : `texte` (Markdown), `statut` (`redige`, `structure`, `rejete`), `contenu.priorites / points_forts / details` (constats avec `valeur, reference, cible, impact, preuves[{tick, round, texte, lien}]`), `jetons_entree`, `jetons_sortie`, `cout` |
| GET | `/api/debriefs/couts` | `{nb, total, entree, sortie, moyen}` (dollars, jetons) |
| POST | `/api/mesures/fiabilite` | Corps `{"nom", "fiable", "note"}` : marque la version courante d'une mesure comme vérifiée à la main |

## CS2

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/cs2/chaleur?carte=de_mirage&type=mort\|kill&camp=T\|CT&periode=7j\|30j\|tout` | Positions des morts ou kills de Mathieu sur une carte, toutes parties confondues : `points: [{x, y, z, camp, arme, partie_id, tick, round}]` |

| GET | `/api/cs2/references` | Résumé du catalogue appris sur démos pros : `cartes: [{carte, demos, lancers, positions}]` |
| GET | `/api/cs2/references?carte=de_mirage` | Lancers de référence (`type, x, y, z, lx, ly, lz, lieu_arrivee, lieu_lancer, nb, nb_demos`) et positions de référence (`camp, lieu, x, y, nb, part`) |

| GET | `/api/cs2/replay/{id}` | Replay 2D : `carte, tickrate, joueurs [{id, steamid, nom, moi}], rounds [{numero, debut, fin, gagnant}], fond` (silhouette) et `radar {parametres, image}` |
| POST | `/api/cs2/revoir` | Corps `{partie_id | empreinte, tick, joueur?}` : prépare la vraie démo dans CS2 → `demo, installe, commandes ["exec postgame", "pg"], lien_steam, tick, joueur, vues [{commande, joueur}]` (410 si la démo a disparu) ; options `avance_s`, `pause` |
| GET | `/api/cs2/pros` | Démos pros lues : `empreinte, fichier, carte, chemin, disponible` |
| GET | `/api/cs2/pros/proches?carte=&x=&y=&camp=` | Vrais rounds pros au même endroit : `empreinte, demo, joueur, round, tick, lieu, distance` |
| GET | `/api/cs2/stuffs/{cle}/pros` | Vrais lancers pros de ce stuff (même format) |
| POST | `/api/cs2/stuffs/{cle}/capture` | Corps `{empreinte, tick, joueur}` : démo pro figée au lâcher ; la prochaine capture Steam (F12) sera jointe → `commandes, vues, dossiers` |
| GET | `/api/cs2/stuffs/{cle}/capture` | `attente` (capture demandée, pas encore arrivée), `image` (jointe) |
| POST | `/api/cs2/radars/exporter` | Exporte les radars du pool depuis les fichiers du jeu (409 si Source2Viewer-CLI ou CS2 absents) |
| GET | `/api/cs2/replay/{id}/round/{n}` | Round à 16 images/s : `ticks, joueurs {id: {equipe, x[], y[], yaw[], vivant[], arme[]}}, tirs, morts, grenades, bombe` |
| GET | `/api/cs2/radar/{carte}.png` | Image du radar officiel si Mathieu l'a exportée dans `data/radars/` |

| POST | `/api/cs2/gsi` | Point d'arrivée du flux Game State Integration (appelé par CS2, jeton obligatoire) |
| GET | `/api/cs2/live` | État en direct : `carte, round, phase_round, camp, score, joueur {argent, argent_si_defaite, vie, armure, armes, kills…}, recommandation {type, titre, raison}, coequipiers (si fournis), rappel (priorités du dernier débrief)` |
| WS | `/api/cs2/live/ws` | Même contenu, poussé à chaque message GSI |

Toute autre adresse hors `/api/` sert l'interface web (`web/dist`).

## Geometry Dash

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/gd/replay/{id}` | Essais superposés : `niveau, longueur, essais [{numero, mode, x_debut, x_fin, pct_fin, mort, complete, appuis[]}], inputs [{x, pct, ecart_type, decalage, n}]` |

## League of Legends et TFT

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/riot/etat` | Riot ID, plateforme, clé présente, dernière synchronisation, erreur |
| POST | `/api/riot/synchroniser` | Récupère tout de suite les nouvelles parties |
| GET | `/api/lol/replay/{id}` | Carte minute par minute : `joueurs, minutes [{t, positions}], evenements` |
| GET | `/api/lol/live` · WS `/api/lol/live/ws` | Partie LoL en cours (API locale du client) |
| GET | `/api/tft/stats` | Par set et patch : place moyenne, éléments (place moyenne, écart, haut classement), éléments à essayer |

## Stuffs et notes (STUFF-01)

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/cs2/cartes` | Pool actif de CS2 (d'après les notes officielles) et cartes jouées |
| GET | `/api/cs2/stuffs?carte=de_mirage` | Stuffs : nom, technique, commandes, maîtrise, révision, notes ; notes de la carte ; config d'entraînement |
| GET | `/api/cs2/stuffs/a_reviser?carte=…&nombre=5` | Stuffs à réviser aujourd'hui |
| POST | `/api/cs2/stuffs/{cle}/revision` | `{"reussi": true}` : révision espacée |
| POST / PUT / DELETE | `/api/notes`, `/api/notes/{id}` | Notes de Mathieu (`carte`, `texte`, `stuff` facultatif) |

## Récupération automatique

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/sources/etat` | FACEIT, codes de partage Steam : dernière synchronisation, parties sans démo |
| POST | `/api/sources/synchroniser` | Lance la synchronisation tout de suite |

## Pour Jarvis

Questions typiques et appels correspondants :

- « Comment s'est passée ma dernière partie de CS ? » → `GET /api/parties?jeu=cs2&limite=1`
  puis `GET /api/parties/{id}`.
- « Est-ce que mon contre-strafe progresse ? » → `GET /api/progression/<nom>?periode=30j`.
