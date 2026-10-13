# Postgame — cahier des charges

*Coach personnel multi-jeux : analyse, replays, second écran.*
*Version 1.1 du 2026-10-13.*

> **Pour lancer le projet dans une nouvelle conversation :** « Lis `CAHIER_DES_CHARGES.md`
> et mène le projet de bout en bout. » Le mode de travail (autonomie) est dans `CLAUDE.md`.

---

## 1. Contexte

Mathieu joue à **Counter-Strike 2** (Premier / matchmaking, et surtout **beaucoup de
deathmatch et de modes d'entraînement** ; FACEIT plus tard, quand il s'estimera au niveau),
à **League of Legends**, à **TFT** et à **Geometry Dash** (Steam PC, mod loader **Geode**
déjà installé).

Il veut progresser dans chacun. Les outils existants (Leetify, Scope.gg, Mobalytics,
Blitz…) sont payants pour l'analyse fine, génériques, éclatés jeu par jeu, et aucun ne
fait d'analyse sérieuse pour Geometry Dash.

Projet personnel, non lié au travail. Projet frère : **Jarvis** (autre dépôt), un assistant
local qui interrogera Postgame comme un outil.

## 2. Objectifs

1. **Dire précisément quoi corriger** après chaque session : quoi, où, de combien, chiffres
   et moments du replay à l'appui. Pas de conseils génériques.
2. **Montrer la progression** dans le temps sur des mesures stables.
3. **Réunir en une seule appli** le coach, les replays et le second écran, pour tous ses jeux.

**Critère de réussite global :** après chaque session, Mathieu ouvre le débrief parce qu'il
y apprend quelque chose de précis qu'il ne savait pas, et ses mesures clés (contre-strafe,
placement du viseur, trades, utilité des smokes, régularité des clics GD) s'améliorent de
façon visible d'un mois sur l'autre.

## 3. Utilisateur et usages

Un seul utilisateur : Mathieu. Trois moments d'usage :

| Moment | Où | Ce qu'il fait |
|---|---|---|
| **Après une session** | PC (ou téléphone) | Lit le débrief, clique sur un point pour voir le moment dans le replay |
| **Pendant une partie** | Téléphone posé à côté | Consulte le second écran (CS2, LoL) |
| **De temps en temps** | PC | Regarde sa progression sur plusieurs semaines, compare ses cartes, ses armes, ses niveaux |

Plus un usage machine : **Jarvis** interroge l'API locale de Postgame.

## 4. Exigences fonctionnelles

Chaque exigence porte un identifiant pour être suivie dans les lots et les tests.

### 4.1 Commun à tous les jeux

| ID | Exigence |
|---|---|
| COM-01 | Import automatique : le service surveille les dossiers de démos / journaux et importe chaque nouveau fichier sans action de l'utilisateur. Import manuel possible (glisser-déposer). |
| COM-02 | Chaque partie importée produit une fiche : jeu, date, mode, carte/niveau, résultat, durée. |
| COM-03 | Chaque mesure est stockée par partie, pour suivre l'évolution dans le temps (courbes sur 7 jours, 30 jours, tout). |
| COM-04 | Chaque constat du débrief renvoie vers ses preuves : partie, round, tick ou position dans le niveau, et s'ouvre dans le replay au bon moment. |
| COM-05 | Débrief rédigé en français par un modèle de langage, qui **ne reçoit que des mesures déjà calculées** et doit citer leur source. Il reformule et hiérarchise, il n'invente aucun chiffre. Fournisseur interchangeable (Gemini par défaut, modèle local possible, aucun). Sans modèle, le débrief existe quand même sous forme de liste structurée. |
| COM-06 | Le débrief met en avant **3 points prioritaires** maximum, classés par impact estimé, puis le détail. |
| COM-07 | API locale (HTTP, JSON) documentée, pour l'interface et pour Jarvis : liste des parties, fiche, mesures, débrief, progression. |
| COM-08 | Re-analyse : quand une mesure change de version, on peut recalculer tout l'historique. |

### 4.2 Counter-Strike 2 — « absolument tout »

**Sources.**

| ID | Exigence |
|---|---|
| CS-SRC-01 | Démos Premier / matchmaking téléchargées depuis le jeu (dossier `game\csgo\replays`). |
| CS-SRC-02 | Démos de deathmatch et d'entraînement enregistrées côté client (`record` / `stop`). Le projet fournit une config (`autoexec` / alias) qui rend l'enregistrement automatique ou en une touche. Vérifier dès L0 que l'enregistrement client fonctionne sur les serveurs DM officiels ; sinon, prévoir les serveurs communautaires. |
| CS-SRC-03 | FACEIT (plus tard) : récupération des démos via l'API FACEIT. |
| CS-SRC-04 | Démos de joueurs professionnels (téléchargées par Mathieu) pour construire les références. |

**Analyses.** Le DM alimente la mécanique ; les démos Premier alimentent tout.

| ID | Domaine | Mesures |
|---|---|---|
| CS-AIM-01 | **Contre-strafe** | Vitesse du joueur au moment de chaque tir ; part des tirs effectués à une vitesse permettant la précision maximale de l'arme ; par arme. |
| CS-AIM-02 | **Première balle** | Précision de la première balle d'un engagement ; headshot à la première balle. |
| CS-AIM-03 | **Spray** | Dispersion des impacts au fil d'une rafale, comparée au motif de l'arme ; à partir de quelle balle le contrôle décroche. |
| CS-AIM-04 | **Temps pour tuer et réaction** | Délai entre l'apparition de l'adversaire et le premier tir ; entre le premier tir et le kill. |
| CS-AIM-05 | **Placement du viseur** | Écart angulaire (horizontal et vertical) entre le viseur et la tête de l'adversaire **au moment où il devient visible** ; hauteur du viseur en déplacement ; tendance (trop bas, trop à gauche…). Visibilité estimée par l'indicateur « repéré » de la démo ; affiner plus tard par lancer de rayons sur la géométrie de la carte si nécessaire. |
| CS-AIM-06 | **Taux par arme** | Kills, headshots, précision, dégâts par arme. |
| CS-UTL-01 | **Smokes** | Point d'impact comparé aux smokes de référence de la carte (CS-REF) ; smoke reconnue / ratée de combien ; a-t-elle coupé une ligne de vue utile pendant sa durée. |
| CS-UTL-02 | **Flashs** | Adversaires aveuglés et durée totale ; coéquipiers aveuglés ; kill d'un coéquipier ou de soi dans les 2 s suivant une flash utile ; flashs inutiles. |
| CS-UTL-03 | **HE et molotovs** | Dégâts infligés ; zone refusée et durée ; adversaires forcés à bouger. |
| CS-UTL-04 | **Gaspillage** | Valeur des utilitaires encore en poche à la mort ; utilitaires jamais lancés du round. |
| CS-POS-01 | **Cartes de chaleur** | Positions de mort et de kill par carte, par camp, sur le radar. |
| CS-POS-02 | **Morts isolées** | Distance au coéquipier vivant le plus proche au moment de la mort. |
| CS-POS-03 | **Trades** | Morts tradables non tradées (et par qui), trades réussis par Mathieu, délai de trade. |
| CS-POS-04 | **Positions de référence** | Positions habituelles de Mathieu par site et par camp, comparées aux positions pros (CS-REF). |
| CS-DEC-01 | **Duels d'ouverture** | Qui prend le premier duel, taux de victoire, conséquence sur le round. |
| CS-DEC-02 | **Rotations** | Délai de rotation après une information (bombe vue, site appelé). |
| CS-DEC-03 | **Sauver ou rejouer** | Rounds perdus d'avance : sauvegarde de l'arme ou mort inutile. |
| CS-DEC-04 | **Retakes et après pose** | Positions et issues des retakes et des situations après pose de la bombe. |
| CS-DEC-05 | **Clutchs** | Situations 1vX : fréquence, issue, décisions clés. |
| CS-ECO-01 | **Économie** | Achat de Mathieu comparé à l'argent et aux achats de l'équipe ; force-buys et écos ; valeur de matériel perdue. |
| CS-STR-01 | **Stratégie d'équipe** (Premier) | Exécutions par site, défauts de round, schémas répétés, adaptation au fil du match. |
| CS-REF-01 | **Références apprises** | À partir de démos pros : regroupement des points d'impact des smokes / flashs / molotovs par carte → catalogue des lancers de référence ; positions courantes par site et par camp. Rien n'est écrit à la main. |

**Replay et second écran.**

| ID | Exigence |
|---|---|
| CS-RPL-01 | Replay 2D vue du dessus sur le radar officiel : joueurs, orientation du regard, tirs, grenades, timeline, vitesse réglable, saut au tick d'un constat. |
| CS-RPL-02 | Replay 3D dans le navigateur (three.js), partageable par lien local. |
| CS-LIVE-01 | Second écran par **Game State Integration** (fonction officielle de Valve) : argent, état du round, score, stats du match, recommandation d'achat. Vérifier dès L7 ce que GSI expose réellement pour un joueur (l'argent des coéquipiers n'est peut-être pas fourni). |

### 4.3 Geometry Dash

| ID | Exigence |
|---|---|
| GD-01 | Mod **Geode** qui **journalise sans rien modifier** : pour chaque essai, niveau, mode (normal / entraînement), chaque appui et relâchement avec horodatage précis, frame et position X dans le niveau, la mort (position, cause si disponible), la progression en %. Écriture dans un fichier lu par le service. |
| GD-02 | **Régularité des clics** : alignement de tous les essais sur la position dans le niveau ; pour chaque saut / input attendu, décalage moyen et dispersion en ms ; tendance (trop tôt / trop tard). |
| GD-03 | **Passages instables** : inputs où la dispersion est la plus forte, corrélés avec les morts. |
| GD-04 | **Carte des morts** par niveau, et taux de survie par segment. |
| GD-05 | **Spam et timings serrés** : régularité et cadence en clics par seconde sur les passages de spam ; intervalles entre clics. |
| GD-06 | **Progression** : meilleure tentative, % moyen, régularité d'une session à l'autre, effet de l'entraînement en mode practice sur le mode normal. |
| GD-07 | Replay : superposition de tous les essais sur le profil du niveau, avec les clics. |
| GD-08 | Second écran (optionnel) : régularité de la session en cours et prochain passage à risque. |

### 4.4 League of Legends

| ID | Exigence |
|---|---|
| LOL-01 | Récupération des parties par l'**API Riot** (match + chronologie) avec la clé de Mathieu. |
| LOL-02 | Farm à 10 et 20 min, or et expérience comparés à un benchmark de son rang et de son rôle. |
| LOL-03 | Morts : isolées, sans vision, avant un objectif ; positions sur la carte. |
| LOL-04 | Vision : balises posées, détruites, score de vision par minute. |
| LOL-05 | Objectifs : participation aux dragons, nashors, tours. |
| LOL-06 | Replay : carte minute par minute avec positions et combats (la chronologie Riot donne les positions à la minute). |
| LOL-07 | Second écran : API locale de Riot pendant la partie (or, objets, scores). |

### 4.5 TFT

| ID | Exigence |
|---|---|
| TFT-01 | Récupération des parties par l'API Riot TFT. |
| TFT-02 | Compos, unités, objets et augments qui réussissent ou coûtent des places **à Mathieu**. |
| TFT-03 | Comparaison avec ce qui gagne en haut classement (statistiques calculées à partir de parties de haut classement via l'API, pas de site tiers). |
| TFT-04 | Déroulé de la partie étape par étape (selon ce que l'API fournit). |

## 5. Exigences non fonctionnelles

| ID | Exigence |
|---|---|
| NF-01 | **Plateforme** : service et collecte sur Windows (PC de jeu). Interface consultable depuis le PC, un téléphone ou un Mac du réseau local. |
| NF-02 | **Téléphone** : interface installable (PWA), pas d'appli native. |
| NF-03 | **Performance** : une démo Premier complète analysée en moins de 60 s sur le PC de jeu (Ryzen 5800X, 32 Go). Le second écran a moins de 500 ms de retard sur le jeu. |
| NF-04 | **Coût** : gratuit hors débrief rédigé ; le débrief tient dans le crédit Gemini de 15 € (mesurer le coût par débrief dès L5). |
| NF-05 | **Données** : stockage local (SQLite + fichiers). Seules les mesures chiffrées partent vers le modèle de langage, jamais les démos brutes ni d'identifiants. Le débrief doit pouvoir être désactivé ou passer sur un modèle local. |
| NF-06 | **Fiabilité des mesures** : chaque mesure a des tests sur des cas vérifiés à la main. Une mesure non fiable n'apparaît pas dans le débrief. |
| NF-07 | **Respect des jeux** : aucune lecture ni écriture de la mémoire des jeux, aucune injection, rien qui puisse être assimilé à de la triche ou déclencher un anti-triche (VAC, Vanguard). Uniquement : démos, GSI, API Riot, API locale de Riot, et pour GD un mod Geode qui journalise sans modifier le gameplay. |
| NF-08 | **Clé Riot** : jamais commitée ; dans un fichier local ignoré par git. |
| NF-09 | **Langue** : interface, débriefs, documentation et commits en français. |

## 6. Architecture

```
                 ┌────────────────────────── PC de jeu (Windows) ──────────────────────────┐
  CS2 démos ───► │                                                                         │
  CS2 GSI ─────► │  Service Postgame (Python, FastAPI)                                      │
  Mod Geode ───► │   ├─ collecteurs (un par jeu)                                           │
  API Riot ────► │   ├─ analyseurs (mesures versionnées, testées)                          │
                 │   ├─ stockage SQLite + fichiers                                         │
                 │   ├─ débrief (modèle de langage interchangeable)                        │
                 │   └─ API HTTP + WebSocket (temps réel)                                  │
                 └───────────────┬───────────────────────────────┬─────────────────────────┘
                                 │                               │
                    Interface web (React + Vite,          Jarvis (projet frère)
                    three.js) — PC, téléphone, Mac
```

- **Python 3.13** : `demoparser2` (lecture des démos CS2, Rust), polars, numpy, FastAPI.
- **Interface** : React + Vite + TypeScript ; three.js pour la 3D.
- **Mod Geode** : C++ (SDK Geode), compilé pour la version de GD de Mathieu.
- **Organisation par jeu** : chaque jeu est un module (collecteur, analyseurs, replay, live)
  derrière une interface commune, pour en ajouter sans toucher au reste.
- **Mesures versionnées** : chaque mesure a un nom, une version, une unité, une description.

## 7. Contraintes

- **Le poste de développement n'est pas le PC de jeu** : poste Windows d'entreprise, sans
  Steam, avec Gradle bloqué. On y développe avec des démos et journaux copiés ; tout ce qui
  touche au jeu lui-même (dossiers, GSI, mod Geode, performances) se valide sur le PC de jeu.
- Pas d'Android natif (Gradle bloqué) : téléphone en PWA.
- CS2 ne tourne pas sur Mac : le Mac n'est qu'un écran de consultation.
- Clé API Riot : créée par Mathieu lui-même sur developer.riotgames.com.

## 8. Hors périmètre

- Bot CS2, IA qui joue, aide à la visée.
- Pronostics esport.
- Toute modification d'un jeu ou de sa mémoire.
- Comptes, serveurs, cloud : tout tourne chez Mathieu.

## 9. Plan par lots

| Lot | Contenu | Exigences | Fini quand |
|---|---|---|---|
| **L0 — Socle** | Dépôt, service, stockage, tests, import d'une démo, config d'enregistrement DM | COM-01/02/07, CS-SRC-01/02 | Une démo importée produit une fiche en base ; l'enregistrement DM est validé sur le PC de jeu |
| **L1 — CS2 mécanique** | Contre-strafe, première balle, spray, réaction, placement du viseur, armes | CS-AIM-* | Sur une démo DM réelle, chaque mesure est vérifiée à la main sur 5 cas |
| **L2 — CS2 utilitaires et positionnement** | Flashs, HE, molotovs, gaspillage, chaleur, morts isolées, trades | CS-UTL-02/03/04, CS-POS-01/02/03 | Idem sur une démo Premier |
| **L3 — Références pro** | Catalogue des lancers et positions appris sur démos pros | CS-REF-01, CS-UTL-01, CS-POS-04 | Chaque smoke de Mathieu est rattachée à une référence ou signalée hors référence |
| **L4 — Décisions et économie** | Duels d'ouverture, rotations, saves, retakes, clutchs, économie, stratégie | CS-DEC-*, CS-ECO-01, CS-STR-01 | Mesures produites et vérifiées sur 3 matchs |
| **L5 — Débrief** | Rédaction, priorisation, liens vers les preuves, coût mesuré | COM-04/05/06 | Le débrief d'un vrai match apprend quelque chose à Mathieu |
| **L6 — Interface et replay 2D** | Tableau de bord, débrief, progression, replay radar, PWA | COM-03, CS-RPL-01, NF-02 | Utilisable au quotidien sur PC et téléphone |
| **L7 — Second écran CS2** | GSI en direct | CS-LIVE-01 | Fonctionne pendant une vraie partie |
| **L8 — Geometry Dash** | Mod Geode + analyses + replay | GD-* | Analyse d'une vraie session d'entraînement |
| **L9 — LoL et TFT** | API Riot, analyses, second écran LoL | LOL-*, TFT-* | Débrief d'une vraie partie de chaque |
| **L10 — Replay 3D** | three.js | CS-RPL-02 | Un round rejoué en 3D |

Chaque lot se termine par : tests verts, vérification sur données réelles, commit, mise à jour
du README.

## 10. Risques

| Risque | Conséquence | Comment le tester tôt |
|---|---|---|
| L'enregistrement client ne marche pas en DM officiel | Pas de données de mécanique | Premier essai de `record` sur le PC de jeu, dès L0 |
| Le placement du viseur est faussé par une visibilité approximative | Mesure phare peu fiable | Vérifier 20 cas à la main en L1 ; prévoir le lancer de rayons |
| Débrief générique (« améliore ton placement ») | Le projet ne sert à rien | Critère de L5 : Mathieu juge sur un vrai match |
| GSI n'expose pas l'argent des coéquipiers | Conseil d'achat limité | Journaliser le flux GSI réel en début de L7 |
| Le mod Geode ne peut pas horodater assez finement | Analyse GD imprécise | Prototype du mod en début de L8, mesurer la résolution |
| Limites de la clé API Riot personnelle | Collecte lente | Mettre en cache, collecter en tâche de fond |
| Mise à jour d'un jeu qui casse un format | Analyse en panne | Tests sur démos de référence, versions de format suivies |

## 11. Ce que Mathieu fournit

- 2 ou 3 démos Premier, 1 ou 2 sessions de DM enregistrées (pour démarrer L0–L1).
- Quelques démos pros (HLTV) pour L3.
- Sa clé API Riot et son Riot ID pour L9.
- Les tests sur le PC de jeu à la fin de chaque lot.
