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
| L3 | Références pros : catalogue de lancers et positions appris sur démos pros, rattachement des smokes | Codé et testé sur données synthétiques ; **aucune démo pro lue, catalogue vide** |
| L4 | Décisions et économie CS2 : ouvertures, rotations, saves, après pose, clutchs, achats, stratégie | Codé et testé sur scénarios synthétiques ; **jamais exécuté sur une vraie démo** |
| L5 | Débrief : 3 priorités chiffrées, preuves, rédaction Gemini / locale contrôlée, coût | Codé et testé avec réponses simulées ; **aucun appel Gemini réel, coût réel non mesuré** |
| L6 | Interface web et PWA : parties, débrief, progression, chaleur, replay radar 2D | Vérifiée dans le navigateur (PC et format téléphone) sur données de démonstration ; **pas encore installée sur le téléphone, radars officiels absents** |
| L7 | Second écran CS2 (Game State Integration) : état en direct, conseil d'achat, rappel des priorités | Vérifié avec un flux GSI simulé ; **jamais branché sur une vraie partie** |
| L8 | Geometry Dash : mod Geode de journalisation, régularité des clics, passages instables, carte des morts, essais superposés | Analyses testées sur séances synthétiques ; **mod jamais compilé ni lancé** |
| L9–L10 | LoL/TFT, 3D | À faire |

Détail et décisions : [PLAN.md](PLAN.md). Ce qui attend un test ou une donnée de Mathieu :
[A_VALIDER.md](A_VALIDER.md).

## Ce qui marche aujourd'hui

- Le service surveille les dossiers de démos CS2 (`replays` pour Premier, `game\csgo` pour
  les démos enregistrées avec F8) et importe chaque nouvelle démo une fois son écriture
  terminée. Import manuel possible par l'API.
- Chaque démo est archivée dans `data/archives/` et produit une fiche : carte, mode,
  résultat, score, durée (**lecture CS2 pas encore vérifiée sur une vraie démo**).
- Chaque démo est analysée : mécanique, utilitaires, positionnement, références pros,
  décisions, économie (méthode : [docs/MESURES_CS2.md](docs/MESURES_CS2.md))
  et preuves (moments précis du replay). `verifier <partie>` produit la fiche de
  vérification manuelle des mesures.
- Chaque partie reçoit un débrief : 3 priorités classées par impact, chiffres et moments
  du replay à l'appui, rédigé par Gemini (ou un modèle local) sans qu'il puisse inventer de
  chiffre : [docs/DEBRIEF.md](docs/DEBRIEF.md).
- Une interface web (`http://<PC>:8765/`, installable sur le téléphone en HTTPS) :
  parties, import par glisser-déposer, débrief avec moments cliquables, progression,
  cartes de chaleur, replay radar 2D.
- Un second écran CS2 (`/direct`) alimenté par Game State Integration : score, argent,
  conseil d'achat pendant le freeze, rappel des priorités du dernier débrief.
- Geometry Dash : un mod Geode journalise chaque essai et chaque clic sans rien modifier ;
  le service mesure la régularité de chaque input, les passages instables, la survie par
  tranche du niveau ([docs/MESURES_GD.md](docs/MESURES_GD.md)).
- Une API locale JSON (parties, fiches, mesures, progression) sert l'interface à venir et
  Jarvis : [docs/API.md](docs/API.md).

## Installation (PC de jeu, Windows)

Prérequis : Python 3.13.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\installer.ps1
```

Puis éditer `postgame.toml` (créé à partir de `postgame.exemple.toml`, jamais commité) :
SteamID64 et dossiers CS2. La clé Gemini va dans `secrets.toml` (modèle :
`secrets.exemple.toml`, jamais commité).

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
| `references ajouter <dossier>` | Ajoute des démos pros au catalogue CS2 (`reconstruire`, `lister` aussi) |
| `debrief <partie> [--sans-modele]` | (Re)génère le débrief d'une partie |
| `fiabilite <mesure> [--non]` | Marque une mesure vérifiée à la main : elle entre dans le débrief |
| `couts` | Coût cumulé des débriefs rédigés |
| `gsi-config [--hote IP]` | Écrit la config Game State Integration de CS2 (second écran) |
| `verifier <partie>` | Fiche de vérification manuelle : 5 moments par mesure, avec la commande CS2 pour y aller |
| `diagnostic <demo.dem>` | Décrit une démo (en-tête, évènements, fiche) dans un JSON |

Documentation interactive de l'API : `http://localhost:8765/docs`.

## Développement

Interface (Node.js 24) :

```powershell
cd web
npm ci
npm run dev      # http://localhost:5173, l'API est relayée vers le service (port 8765)
npm test         # tests des utilitaires (vitest)
npm run build    # construit web\dist, servi ensuite par le service
```

Essayer l'interface sans vraie démo : `.venv\Scripts\python scripts\donnees_demo.py data_demo`
puis `.venv\Scripts\python -m postgame --config data_demo\postgame.toml serve
--sans-surveillance` (**données simulées**, à ne pas confondre avec de vraies parties).

Service :

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
  debrief/         constats priorisés, cibles, rédaction par modèle de langage
  live/            second écran : réception GSI, conseil d'achat CS2
  surveillance.py  scrutation des dossiers surveillés
  api.py           API HTTP (FastAPI)
  games/           un module par jeu derrière une interface commune (base.py)
    gd/            Geometry Dash : lecture des journaux du mod, analyses
    cs2/           lecture des démos (demoparser2), diagnostic, armes, géométrie,
                   analyses (mecanique.py, utilitaires.py, positionnement.py,
                   references.py, decisions.py, economie.py)
web/               interface React + Vite + TypeScript (PWA)
mods/gd-journal/   mod Geode (C++) qui journalise les séances Geometry Dash
config/cs2/        config d'enregistrement des démos DM
scripts/           installation, lancement, base de démonstration
tests/             tests ; tests/donnees/ (ignoré par git) pour les vraies démos
```

## Principes

- Uniquement des sources autorisées : démos, Game State Integration, API Riot, API locale
  de Riot, mod Geode qui journalise sans rien modifier. Rien ne touche à la mémoire d'un jeu.
- Aucun secret dans le dépôt : clé Riot, SteamID et chemins restent dans `postgame.toml`.
- Chaque mesure est versionnée et testée sur des cas vérifiés à la main ; une mesure non
  fiable n'apparaît pas dans le débrief.
