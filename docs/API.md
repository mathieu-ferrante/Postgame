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

Valeurs de `mode` pour CS2 : `competitif`, `deathmatch`, `wingman`, `autre`.

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

## Pour Jarvis

Questions typiques et appels correspondants :

- « Comment s'est passée ma dernière partie de CS ? » → `GET /api/parties?jeu=cs2&limite=1`
  puis `GET /api/parties/{id}`.
- « Est-ce que mon contre-strafe progresse ? » → `GET /api/progression/<nom>?periode=30j`.
