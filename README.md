# Postgame

Coach personnel multi-jeux, en local sur le PC de jeu : **Counter-Strike 2**, **League of
Legends**, **Teamfight Tactics** et **Geometry Dash**.

Après chaque session, Postgame récupère la partie tout seul, la mesure chiffre par chiffre,
la compare à ton propre historique et aux joueurs de haut niveau **dans le même contexte**
(même arme, même champion et même rôle, même patch, même set…), puis rédige un débrief de
3 priorités, chacune prouvée par des moments précis de la partie. Pendant la partie, un
second écran (téléphone) affiche l'essentiel sans rien analyser de lourd.

Spécification complète : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md) · suivi des lots
et décisions : [PLAN.md](PLAN.md) · ce qui attend une action de Mathieu :
[A_VALIDER.md](A_VALIDER.md).

---

## Sommaire

1. [État réel du projet](#état-réel-du-projet)
2. [Ce que fait Postgame, jeu par jeu](#ce-que-fait-postgame-jeu-par-jeu)
3. [Comment ça marche](#comment-ça-marche)
4. [Installation sur le PC de jeu](#installation-sur-le-pc-de-jeu)
5. [Configuration](#configuration)
6. [Utilisation](#utilisation)
7. [Données, sécurité et respect des jeux](#données-sécurité-et-respect-des-jeux)
8. [Développement](#développement)
9. [Limites connues](#limites-connues)

---

## État réel du projet

Tout le code des lots L0 à L10 est écrit et testé (**226 tests automatiques**). Ce qui a
tourné sur de **vraies données** et ce qui ne l'a pas encore fait est distingué ci-dessous.
Aucune mesure n'est encore « vérifiée à la main sur 5 cas » : le débrief les signale
toutes « en cours de validation » tant que ce n'est pas fait (voir
[A_VALIDER.md](A_VALIDER.md)).

| Partie | Vérifié sur données réelles | Reste à faire |
|---|---|---|
| CS2 — lecture des démos et fiche | 2 vraies démos pros (ESL Pro League S24, Falcons vs Spirit, Mirage et Anubis) : mode, score 13-8, mi-temps, vainqueurs de chaque round justes | Tes démos Premier, compétitif, deathmatch, FACEIT, Wingman |
| CS2 — mesures (mécanique, utilitaires, positionnement, décisions, économie) | Exécutées sur les 2 démos avec un pro (donk, m0NESY) à ta place ; valeurs contrôlées (précision, trades, AWP, clutchs, sites de pose) | Vérification à la main sur 5 cas par mesure |
| CS2 — lineups pros (stuffs) | **72 lineups** tirés de 781 grenades réelles, avec technique, timing, raison et trajectoire | Démos pros des autres cartes |
| CS2 — cibles par arme | 124 références tirées des joueurs des 2 démos | Plus de démos pros |
| CS2 — revoir un moment dans le jeu, capture de la vue d'un lineup, annotations, radars | Fichiers préparés et testés | **Jamais lancé dans CS2** (PC de jeu) |
| CS2 — second écran (GSI) | Flux simulé | Une vraie partie |
| LoL / TFT | Noms TFT vérifiés sur le Data Dragon réel (set 18 compris) ; format de l'API locale du client vérifié sur la doc Riot | **Clé API Riot** puis de vraies parties |
| Geometry Dash | Analyses sur séances construites | **Mod jamais compilé** ni lancé |
| Débrief rédigé (Gemini) | Contrôle anti-chiffres-inventés testé | **Clé Gemini**, coût réel |
| Interface web | Vérifiée dans le navigateur (PC et format téléphone) sur vraies données | Installation sur le téléphone |

Trois relectures indépendantes du code ont corrigé une trentaine de défauts, la plupart
révélés par les vraies démos (fins de round absentes des démos de tournoi, lunette de l'AWP,
entités réutilisées, sécurité du service…). Le détail est dans [PLAN.md](PLAN.md).

---

## Ce que fait Postgame, jeu par jeu

### Counter-Strike 2

**Récupération automatique** (rien à faire après la partie) :
- démos Premier / compétitif téléchargées dans le jeu (dossier `replays`) ;
- démos de deathmatch enregistrées d'une touche (`F8`, config fournie dans
  [config/cs2](config/cs2/LISEZMOI.md)) ; le second écran rappelle d'appuyer sur F8 ;
- parties FACEIT par l'API officielle FACEIT ; codes de partage Steam des parties Premier.

**Fiche** : carte, mode (Premier, compétitif, Wingman, FACEIT, deathmatch), score, résultat,
durée, CS Rating / rang.

**Mesures**, toutes jugées **par arme et par catégorie** (une AWP n'est pas jugée sur les
headshots, le seuil de précision tient compte de la lunette, un tir en l'air n'est jamais
« précis ») et, en Wingman, séparées du 5 contre 5 :

| Domaine | Exemples |
|---|---|
| Mécanique | contre-strafe, première balle, spray (balle de décrochage), réaction, TTK, placement du viseur à l'apparition, AWP (lunette, délai lunette → tir) |
| Utilitaires | flashs (adversaires et coéquipiers aveuglés, flashs converties), HE, molotovs (dégâts, adversaires délogés), grenades perdues à la mort |
| Positionnement | cartes de chaleur, morts isolées, trades (morts vengées, occasions manquées) — distances en 3D |
| Références pros | tes smokes, molotovs et flashs rattachées aux lineups pros, positions tenues comparées aux pros |
| Décisions | duels d'ouverture, rotations après la pose, saves, après-pose, retakes, clutchs |
| Économie et stratégie | achats désynchronisés, victoires par type d'achat, sites de pose, répétitions |

Méthode de chaque mesure : [docs/MESURES_CS2.md](docs/MESURES_CS2.md).

**Stuffs — apprendre les lineups des pros, carte par carte** (toutes les cartes, y compris
hors pool et Wingman) :
- seuls les **vrais lineups** sont retenus : un lancer reproduit depuis le même point (48 u)
  avec la même visée (3°), au moins 3 fois ou par 2 joueurs ; les grenades lancées au jugé
  sont écartées ;
- position et visée prises au **vrai lâcher** (le clic est relâché 5 à 10 ticks avant
  l'évènement de lancer) ; technique reconnue : jumpthrow, W + saut, clic gauche / droit,
  accroupi… ;
- **quand et pourquoi** : moment dans le round, phase (début de round, exécution, après la
  pose, retake), délai avant la pose, durée réelle de la smoke, effet obtenu, rounds
  gagnés — uniquement à partir de faits relevés dans les démos ;
- un lancer parfait dont la molotov tombe dans une smoke **reste dans le lineup** (« éteinte
  par une smoke ») ;
- fiche en 3 étapes : où te placer (radar officiel, trajectoire réelle), où viser (vraie vue
  du pro capturée dans la démo), comment lancer ; commandes `setpos` / `setang`, annotations
  officielles CS2, notes, révisions espacées, maîtrise mesurée dans tes parties.

**Revoir les vrais moments, dans le jeu** (pas d'animation reconstituée) : depuis le replay
radar ou une preuve du débrief, Postgame prépare la démo (la tienne ou celle d'un pro) ; dans
la console de CS2 : `exec postgame` puis `pg` → la démo s'ouvre 5 s avant le moment, caméra
sur le bon joueur ; `v1`, `v2`… pour passer sur les yeux des autres joueurs. Liste des
**vrais rounds pros** où un joueur de ton camp était au même endroit que toi.

**Démos pros** : un `.dem` (≈ 375 Mo) est résumé en un extrait `.pgpro` (≈ 2 Mo) qui
s'importe en 1 s sur une autre machine ; un dossier (Google Drive…) est importé seul.

### League of Legends

- parties récupérées par l'API Riot (match-v5 et timeline), rang joint ;
- mesures par **champion, rôle et patch** : farm, or et XP à 10/15/20 min contre
  l'adversaire direct, morts isolées ou avant un objectif, vision, objectifs, combats ; pas de
  jugement du farm pour un support, pas de rôle inventé en ARAM ;
- références de **haut classement** (Challenger) du même patch, construites par Postgame à
  partir de l'API Riot ;
- carte minute par minute ; second écran par l'API locale du client (`127.0.0.1:2999`).

Méthode : [docs/MESURES_LOL_TFT.md](docs/MESURES_LOL_TFT.md).

### Teamfight Tactics

- parties par l'API Riot ; ce qui te fait **gagner ou perdre des places** (traits, unités,
  objets, augments), **par set et par patch**, face au haut classement du même patch ;
- noms officiels en français (Data Dragon TFT de Riot), y compris le format d'identifiants du
  set 18 sous Unreal Engine.

### Geometry Dash

- un mod Geode ([mods/gd-journal](mods/gd-journal/LISEZMOI.md)) **journalise** chaque essai,
  chaque clic et chaque mort, sans rien modifier au jeu ;
- régularité de chaque input attendu (trop tôt / trop tard, en ms), passages instables et
  morts qui les suivent, carte des morts, survie par tranche de 10 %, spam, effet de
  l'entraînement ; essais superposés ;
- second écran pendant la séance : position, meilleur %, moyenne récente, zones de mort,
  rappel des passages irréguliers des séances précédentes.

Méthode : [docs/MESURES_GD.md](docs/MESURES_GD.md).

### Débrief (tous les jeux)

3 priorités classées par impact, des points forts et le détail ; chaque constat porte sa
valeur, ta moyenne dans le même contexte, une cible (référence pro ou haut classement, sinon
« cible provisoire » signalée) et des moments cliquables. Le texte est rédigé par Gemini (ou
un modèle local Ollama) **sans pouvoir inventer de chiffre** : tout nombre absent des
données fait rejeter le texte. Coût suivi. Détails : [docs/DEBRIEF.md](docs/DEBRIEF.md).

---

## Comment ça marche

```
 PC de jeu ─────────────────────────────────────────────────────────────────────────────
  CS2 ── démos (replays, F8) ──┐                                ┌── interface web (PWA)
  CS2 ── GSI (HTTP local) ─────┤                                │   PC, téléphone, Mac
  FACEIT / Steam (API) ────────┤   service Postgame (Python)    │
  Riot API (LoL, TFT) ─────────┼─▶ surveillance → import →  ────┼── second écran (WebSocket)
  Client LoL (127.0.0.1:2999) ─┤   fiche → mesures → débrief    │
  Mod Geode (journal GD) ──────┤   SQLite + archives locales    └── API JSON (/docs)
  Démos pros (.dem / .pgpro) ──┘
```

- **Aucune analyse pendant une partie** : imports et analyses attendent que le jeu soit
  fermé (processus du jeu, flux GSI) ; le service tourne en priorité basse. Seul le second
  écran (léger) fonctionne en jeu.
- Chaque partie est archivée ; tout l'historique peut être recalculé (`reanalyser`) quand
  une mesure évolue.

---

## Installation sur le PC de jeu

Ordre conseillé détaillé : en tête de [A_VALIDER.md](A_VALIDER.md).

### 1. Prérequis

- Windows, **Python 3.13** ([python.org](https://www.python.org/downloads/)) ;
- **Node.js 24** pour construire l'interface ([nodejs.org](https://nodejs.org/)) ;
- facultatif : Source2Viewer-CLI ([s2v.app](https://s2v.app/)) pour exporter les radars
  officiels ; Geode et Visual Studio Build Tools pour compiler le mod Geometry Dash.

### 2. Installer le service

```powershell
git clone https://github.com/mathieu-ferrante/Postgame.git
cd Postgame
powershell -ExecutionPolicy Bypass -File scripts\installer.ps1
```

Le script crée l'environnement Python (`.venv`), installe Postgame, construit l'interface
(`web\dist`) si Node.js est présent, et crée `postgame.toml` à partir de
`postgame.exemple.toml`.

### 3. Renseigner la configuration

- `postgame.toml` (voir [Configuration](#configuration)) : SteamID64 ou pseudos, Riot ID,
  dossiers ;
- `secrets.toml` (copie de `secrets.exemple.toml`) : clés Riot, Gemini, FACEIT, Steam.
  **Ces deux fichiers sont ignorés par git.**

### 4. Brancher les jeux

| Jeu | Action | Détail |
|---|---|---|
| CS2 — second écran | `.venv\Scripts\python -m postgame gsi-config` | écrit la config Game State Integration dans le dossier du jeu |
| CS2 — deathmatch | copier `config/cs2/postgame.cfg`, touche F8 | [config/cs2/LISEZMOI.md](config/cs2/LISEZMOI.md) |
| CS2 — radars | `source2viewer = "…"` dans `postgame.toml`, puis `postgame radars` | export depuis les fichiers du jeu |
| Geometry Dash | compiler et installer le mod | [mods/gd-journal/LISEZMOI.md](mods/gd-journal/LISEZMOI.md) |
| LoL / TFT | clé API Riot dans `secrets.toml` | collecte toutes les 10 min |

### 5. Lancer

```powershell
powershell -ExecutionPolicy Bypass -File scripts\lancer.ps1
```

Interface : `http://localhost:8765/` sur le PC, `http://<IP du PC>:8765/` sur le téléphone
(même Wi-Fi). Pour l'installer comme une application sur le téléphone (HTTPS avec mkcert) :
[A_VALIDER.md](A_VALIDER.md), point 16.

---

## Configuration

`postgame.toml` (modèle commenté : [postgame.exemple.toml](postgame.exemple.toml)) :

| Section | Clé | Rôle |
|---|---|---|
| `[service]` | `hote`, `port` | adresse d'écoute (`0.0.0.0` pour le téléphone), port 8765 |
| | `dossier_donnees` | base SQLite, archives, extraits pros, radars, captures |
| | `certificat`, `cle_privee` | HTTPS (installation sur le téléphone) |
| `[joueur]` | `steamid`, `noms` | qui analyser dans une démo (le SteamID64 est appris tout seul à partir du pseudo) |
| `[cs2]` | `dossiers_demos` | dossiers surveillés (`replays`, `game/csgo`) |
| | `source2viewer` | chemin de Source2Viewer-CLI pour les radars |
| | `dossiers_pros` | démos et extraits pros importés automatiquement (ex. Google Drive) |
| `[gd]` | `dossiers_journaux` | journaux du mod Geode |
| `[faceit]` | `pseudo` | compte FACEIT |
| `[steam]` | `code_connu`, `dossier` | point de départ des codes de partage ; dossier Steam (captures F12) |
| `[riot]` | `riot_id`, `plateforme`, `region`, `synchro_minutes` | compte Riot (« Pseudo#TAG »), serveur (euw1), routage (europe) |
| `[surveillance]` | `intervalle_s`, `delai_stabilite_s` | scrutation des dossiers |
| `[debrief]` | `fournisseur`, `modele`, `prix_*`, `automatique`, `mesures_experimentales`, `historique` | rédaction (gemini, local, aucun), coût, mesures non encore validées |

`secrets.toml` (modèle : [secrets.exemple.toml](secrets.exemple.toml)) : `[gemini] cle`,
`[riot] cle`, `[faceit] cle` et `jeton_telechargement`, `[steam] cle` et
`code_historique`. Les variables d'environnement (`RIOT_API_KEY`…) ont priorité.

---

## Utilisation

### Interface web

| Page | Contenu |
|---|---|
| Parties (`/`) | historique, import par glisser-déposer |
| Partie (`/partie/:id`) | fiche, débrief, preuves cliquables (replay radar ou « ▶ CS2 ») |
| Replay (`/replay/:id`) | radar 2D, éliminations, « Revoir ce moment dans CS2 », pros au même endroit |
| Progression (`/progression`) | chaque mesure dans le temps, par contexte |
| Chaleur (`/chaleur`) | morts et kills par carte, camp, période |
| Stuffs (`/stuffs`) | lineups pros par carte, quand et pourquoi, capture de la vue, révisions |
| TFT (`/tft`) | ce qui te fait gagner des places, par set et patch |
| En direct (`/direct`) | second écran CS2, LoL, Geometry Dash |
| Comptes (`/comptes`) | comptes liés, CS Rating et rang LoL dans le temps |

### Ligne de commande

`.venv\Scripts\python -m postgame [--config postgame.toml] <commande>` :

| Commande | Rôle |
|---|---|
| `serve [--sans-surveillance]` | lance le service (API, interface, surveillance, collectes) |
| `importer <fichiers…>` | importe des fichiers à la main |
| `parties [--jeu cs2]` | liste les parties |
| `reanalyser [--jeu cs2]` | recalcule fiches et mesures de tout l'historique |
| `references ajouter <dossiers ou fichiers>` | ajoute des démos pros (`.dem`) ou des extraits (`.pgpro`) |
| `references reconstruire` / `references lister` | recalcule ou résume le catalogue de lineups |
| `debrief <partie> [--sans-modele]` | (re)génère le débrief d'une partie |
| `fiabilite <mesure> [--non]` | marque une mesure vérifiée à la main |
| `couts` | coût cumulé des débriefs rédigés |
| `gsi-config [--hote IP]` | écrit la config Game State Integration de CS2 |
| `riot synchroniser` / `riot meta` | récupère les parties LoL/TFT ; construit les références de haut classement du patch |
| `radars [cartes…]` | exporte les radars officiels depuis les fichiers du jeu |
| `annotations [cartes…]` | écrit les annotations CS2 des stuffs (`annotation_load postgame_<carte>` en jeu) |
| `verifier <partie>` | fiche de vérification manuelle (5 moments par mesure) |
| `diagnostic <demo.dem>` | décrit une démo CS2 (en-tête, évènements, fiche) dans un JSON |

### API

API JSON locale : [docs/API.md](docs/API.md) ; documentation interactive sur
`http://localhost:8765/docs`.

---

## Données, sécurité et respect des jeux

- **Respect des jeux** : uniquement les démos, Game State Integration, l'API Riot, l'API
  locale du client Riot et un mod Geode qui journalise sans rien modifier. Rien ne lit ni
  n'écrit la mémoire d'un jeu ; « revoir dans CS2 » n'utilise que les commandes de démo
  standard (`playdemo`, `demo_gototick`, `spec_player`).
- **Tout reste local** : base SQLite et archives sur le PC de jeu ; seuls partent les appels
  aux API (Riot, FACEIT, Steam, Gemini pour la rédaction du débrief).
- **Aucun secret dans le dépôt** : clés et identifiants dans `postgame.toml` /
  `secrets.toml`, ignorés par git, comme les démos, la base et les captures.
- **Service local protégé** : requêtes venant d'autres sites refusées (une page web ouverte
  dans le navigateur ne peut pas piloter Postgame), noms d'hôte limités à `localhost`, aux
  adresses IP et au nom de la machine, paramètres de chemin validés. Pas de mot de passe sur
  le réseau local : choix assumé pour un service personnel.
- **Honnêteté des chiffres** : chaque mesure est versionnée, testée sur des cas construits,
  puis vérifiée à la main sur de vraies parties avant d'être « fiable » ; le débrief signale
  les autres. Les données simulées (`scripts/donnees_demo.py`) sont marquées comme telles.

---

## Développement

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest                # 226 tests
.venv\Scripts\ruff check src tests ; .venv\Scripts\ruff format src tests
cd web ; npm ci ; npm test ; npm run build    # interface (vitest, Vite)
```

- **Vraies démos pour les tests** : déposer des `.dem` dans `tests/donnees/` (ignoré par
  git) ; les tests marqués `demo_reelle` les utilisent.
- **Essayer sans vraie partie** : `.venv\Scripts\python scripts\donnees_demo.py data_demo`,
  puis `.venv\Scripts\python -m postgame --config data_demo\postgame.toml serve
  --sans-surveillance` (**données simulées**).
- **Interface en développement** : `cd web ; npm run dev` (port 5173, l'API est relayée vers
  le service sur 8765).

Organisation :

```
src/postgame/
  __main__.py      ligne de commande
  api.py           API HTTP et WebSockets (FastAPI), sert l'interface
  securite.py      protection du service local (origine, nom d'hôte)
  config.py        postgame.toml et secrets.toml
  db.py            SQLite versionné (migrations) : parties, mesures, preuves, références…
  importation.py   import : déduplication, archive, fiche, mesures, débrief, réanalyse
  surveillance.py  surveillance des dossiers ; performance.py : aucune analyse en jeu
  mesures.py       registre des mesures (nom, version, unité, fiabilité) et preuves
  comptes.py       comptes liés et classements
  debrief/         constats, cibles par contexte, rédaction contrôlée (Gemini, Ollama)
  live/            second écran : GSI et conseil d'achat CS2, client LoL, journal GD
  games/
    cs2/           lecture des démos (demoparser2), mesures, lineups, extraits pros,
                   revoir dans CS2, radars, cartes, stuffs, annotations, sources (FACEIT…)
    lol/, tft/     analyses League of Legends et TFT
    riot/          client API Riot, collecte, Data Dragon, références de haut classement
    gd/            lecture des journaux du mod, analyses Geometry Dash
web/               interface React + Vite + TypeScript (PWA)
mods/gd-journal/   mod Geode (C++)
config/cs2/        config d'enregistrement des démos de deathmatch
scripts/           installation, lancement, base de démonstration, simulateur GSI
docs/              méthode des mesures, débrief, API
tests/             tests (pytest) et fabriques de données
```

---

## Limites connues

- Démos GOTV de tournoi : pas d'évènement de fin de round, ni d'aveuglement, ni de recul ;
  Postgame les reconstitue (score, durée de flash) et écarte les mesures de spray quand le
  recul manque.
- Deux molotovs ou HE du même joueur qui touchent en même temps se partagent mal les
  dégâts (le jeu ne dit pas quelle grenade a touché).
- Les démos Premier exigent un téléchargement dans le jeu (pas d'accès automatique au
  coordinateur de jeu) ; les démos FACEIT exigent l'accès à la Downloads API.
- HLTV demande une vérification humaine : les démos pros se téléchargent à la main.
- Le format des annotations CS2 et l'ouverture des démos par fichier de commandes restent à
  confirmer en jeu.
