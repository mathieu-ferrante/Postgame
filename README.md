# Postgame

Coach personnel multi-jeux (Counter-Strike 2, Geometry Dash, League of Legends, TFT) :
analyse chiffrée après chaque session, replays, second écran. Tout tourne en local sur le
PC de jeu. Spécification complète : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md).

## État

| Lot | Contenu | État |
|---|---|---|
| L0 | Socle : service, stockage, import des démos, API, config d'enregistrement DM | Codé et testé sur données de substitution ; **à valider sur vraies démos et sur le PC de jeu** |
| L1 | Mécanique CS2 : contre-strafe, première balle, spray, réaction, placement du viseur, armes | Codé et testé sur scénarios synthétiques ; **jamais exécuté sur une vraie démo, aucune mesure vérifiée à la main** |
| L2 | Utilitaires et positionnement CS2 : flashs, HE, molotovs, gaspillage, chaleur, morts isolées, trades | Codé et testé sur scénarios synthétiques ; **jamais exécuté sur une vraie démo** |
| L3–L10 | Références pro, décisions, débrief, interface, second écran, GD, LoL/TFT, 3D | À faire |

Détail et décisions : [PLAN.md](PLAN.md). Ce qui attend un test ou une donnée de Mathieu :
[A_VALIDER.md](A_VALIDER.md).

## Ce qui marche aujourd'hui

- Le service surveille les dossiers de démos CS2 (`replays` pour Premier, `game\csgo` pour
  les démos enregistrées avec F8) et importe chaque nouvelle démo une fois son écriture
  terminée. Import manuel possible par l'API.
- Chaque démo est archivée dans `data/archives/` et produit une fiche : carte, mode,
  résultat, score, durée (**lecture CS2 pas encore vérifiée sur une vraie démo**).
- Chaque démo est analysée : mécanique, utilitaires, positionnement (méthode : [docs/MESURES_CS2.md](docs/MESURES_CS2.md))
  et preuves (moments précis du replay). `verifier <partie>` produit la fiche de
  vérification manuelle des mesures.
- Une API locale JSON (parties, fiches, mesures, progression) sert l'interface à venir et
  Jarvis : [docs/API.md](docs/API.md).

## Installation (PC de jeu, Windows)

Prérequis : Python 3.13.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\installer.ps1
```

Puis éditer `postgame.toml` (créé à partir de `postgame.exemple.toml`, jamais commité) :
SteamID64 et dossiers CS2.

Pour enregistrer les parties de deathmatch : [config/cs2/LISEZMOI.md](config/cs2/LISEZMOI.md).

## Utilisation

```powershell
powershell -ExecutionPolicy Bypass -File scripts\lancer.ps1   # service sur le port 8765
```

Ligne de commande (`.venv\Scripts\python -m postgame …`) :

| Commande | Rôle |
|---|---|
| `serve [--sans-surveillance]` | Lance l'API et la surveillance des dossiers |
| `importer <fichiers…>` | Importe des fichiers à la main |
| `parties [--jeu cs2]` | Liste les parties en base |
| `reanalyser [--jeu cs2]` | Recalcule fiches et mesures de tout l'historique |
| `verifier <partie>` | Fiche de vérification manuelle : 5 moments par mesure, avec la commande CS2 pour y aller |
| `diagnostic <demo.dem>` | Décrit une démo (en-tête, évènements, fiche) dans un JSON |

Documentation interactive de l'API : `http://localhost:8765/docs`.

## Développement

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest          # tests (les tests sur vraies démos sont ignorés
                                        # tant que tests/donnees/ est vide)
.venv\Scripts\ruff check src tests
.venv\Scripts\ruff format src tests
```

Organisation :

```
src/postgame/
  config.py        configuration locale (postgame.toml)
  db.py            stockage SQLite versionné : parties, mesures, fichiers vus
  importation.py   import d'un fichier : déduplication, archive, fiche, mesures, re-analyse
  mesures.py       registre des mesures (nom, version, unité, fiabilité) et preuves
  verification.py  fiche de vérification manuelle d'une partie
  surveillance.py  scrutation des dossiers surveillés
  api.py           API HTTP (FastAPI)
  games/           un module par jeu derrière une interface commune (base.py)
    cs2/           lecture des démos (demoparser2), diagnostic, armes, géométrie,
                   analyses (mecanique.py, utilitaires.py, positionnement.py)
config/cs2/        config d'enregistrement des démos DM
scripts/           installation et lancement sur le PC de jeu
tests/             tests ; tests/donnees/ (ignoré par git) pour les vraies démos
```

## Principes

- Uniquement des sources autorisées : démos, Game State Integration, API Riot, API locale
  de Riot, mod Geode qui journalise sans rien modifier. Rien ne touche à la mémoire d'un jeu.
- Aucun secret dans le dépôt : clé Riot, SteamID et chemins restent dans `postgame.toml`.
- Chaque mesure est versionnée et testée sur des cas vérifiés à la main ; une mesure non
  fiable n'apparaît pas dans le débrief.
