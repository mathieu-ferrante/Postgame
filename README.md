# Postgame

Coach personnel multi-jeux (Counter-Strike 2, Geometry Dash, League of Legends, TFT) :
analyse chiffrée après chaque session, replays, second écran. Tout tourne en local sur le
PC de jeu. Spécification complète : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md).

## État

| Lot | Contenu | État |
|---|---|---|
| L0 | Socle : service, stockage, import des démos, API, config d'enregistrement DM | Fiche testée sur **2 vraies démos pros** (compétitif 13-8 correct) ; **à valider sur tes démos (Premier, DM, FACEIT) et sur le PC de jeu** |
| L1 | Mécanique CS2 : contre-strafe, première balle, spray, réaction, placement du viseur, armes | Exécuté sur 2 vraies parties (bugs corrigés, valeurs plausibles) ; **aucune mesure encore vérifiée à la main sur 5 cas** |
| L2 | Utilitaires et positionnement CS2 : flashs, HE, molotovs, gaspillage, chaleur, morts isolées, trades | Exécuté sur 2 vraies parties (flashs et armes corrigés, trades vérifiés) ; **vérification à la main à faire** |
| L3 | Références pros : vrais lineups (timing, raison, technique, trajectoire), positions, cibles par arme | **72 lineups et 124 cibles tirés de 2 vraies démos** (Mirage, Anubis) ; autres cartes en attente de démos |
| L4 | Décisions et économie CS2 : ouvertures, rotations, saves, après pose, clutchs, achats, stratégie | Exécuté sur 2 vraies parties ; **vérification à la main à faire** |
| L5 | Débrief : 3 priorités chiffrées, preuves, cibles des pros, rédaction Gemini / locale contrôlée | Débrief structuré produit sur vraies parties ; **aucun appel Gemini réel (clé à fournir)** |
| L6 | Interface web et PWA : parties, débrief, progression, chaleur, replay radar 2D, stuffs | Vérifiée dans le navigateur sur vraies données ; **radars officiels à exporter du jeu, pas encore installée sur le téléphone** |
| L7 | Second écran : CS2 (GSI), LoL (API locale du client), Geometry Dash (journal du mod) | Testé sur flux simulés ; **jamais branché sur une vraie partie** |
| L8 | Geometry Dash : mod Geode de journalisation, régularité, passages instables, morts, essais superposés, second écran | Analyses testées sur séances synthétiques ; **mod jamais compilé (outils présents, Geode SDK à télécharger) ni lancé** |
| L9 | LoL et TFT : API Riot, analyses par champion / rôle / patch, set TFT, noms officiels, haut classement | Noms TFT vérifiés sur le Data Dragon réel (set 18 compris) ; **clé API Riot pas encore fournie, aucune vraie partie** |
| L10 | Revoir les vrais moments dans CS2 (mes parties et démos pros, n'importe quel joueur), capture de la vue d'un lineup | Fichiers préparés et testés ; **jamais lancé dans CS2** |

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
- League of Legends et TFT : parties récupérées par l'API Riot, mesures jugées par
  champion, rôle et patch (LoL) ou par set et patch (TFT), face au haut classement du même
  patch ([docs/MESURES_LOL_TFT.md](docs/MESURES_LOL_TFT.md)).
- Stuffs CS2 : catalogue par carte appris sur démos pros, commandes `setpos` / `setang` pour
  s'entraîner hors ligne, tes notes, révisions espacées, maîtrise mesurée en match, rappel
  sur le second écran au chargement de la carte.
- Récupération automatique : démos du dossier du jeu, parties FACEIT, LoL et TFT ; codes de
  partage Steam ; rien n'est analysé pendant que tu joues.
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
| `riot synchroniser` / `riot meta` | Récupère les parties LoL/TFT ; construit les références de haut classement du patch |
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
    lol/, tft/     League of Legends et TFT
    riot/          client API Riot, collecte, Data Dragon, références méta
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
