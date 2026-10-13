# Postgame — plan et avancement

Référence : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md). Ce qui attend Mathieu :
[A_VALIDER.md](A_VALIDER.md).

Légende : `[x]` fait et testé · `[~]` codé et testé sur données de substitution, **pas encore
vérifié sur données réelles / PC de jeu** · `[ ]` à faire.

## L0 — Socle (COM-01/02/07, CS-SRC-01/02)

- [x] Dépôt, `pyproject.toml`, environnement `.venv`, ruff, pytest
- [x] Configuration locale `postgame.toml` (ignoré par git) + modèle `postgame.exemple.toml`
- [x] Stockage SQLite versionné : parties, mesures, fichiers vus (migrations)
- [x] Interface commune des modules de jeu + registre
- [x] Import : déduplication par SHA-256, archivage de la démo, fiche, mesures, re-analyse
- [x] Surveillance des dossiers (scrutation + attente de taille stable)
- [x] API HTTP locale + documentation (`docs/API.md`, `/docs`)
- [x] Ligne de commande : `serve`, `importer`, `parties`, `reanalyser`, `diagnostic`
- [x] Scripts d'installation / lancement pour le PC de jeu
- [~] Fiche CS2 depuis une démo (carte, mode, résultat, score, durée) — testée sur données
      fabriquées ; **aucune vraie démo lue à ce jour**
- [~] Config d'enregistrement DM en une touche (`config/cs2/postgame.cfg`) — **non testée
      dans le jeu**
- [ ] Critère de fin : une vraie démo importée produit une fiche correcte ; l'enregistrement
      DM est validé sur le PC de jeu → voir A_VALIDER.md

## L1 — CS2 mécanique (CS-AIM-*)
- [x] Registre des mesures (nom, version, unité, sens, fiabilité) + table des preuves
- [x] Extraction des données de match CS2 dans un schéma stable (`DonneesMatch`)
- [~] Contre-strafe (CS-AIM-01) — scénarios synthétiques uniquement
- [~] Première balle (CS-AIM-02) — idem
- [~] Spray : touche et erreur par rang, balle de décrochage (CS-AIM-03) — idem
- [~] Réaction et TTK (CS-AIM-04) — idem
- [~] Placement du viseur à l'apparition, tendance, hauteur en déplacement (CS-AIM-05) — idem
- [~] Statistiques par arme (CS-AIM-06) — idem
- [x] Preuves (moments du replay) et fiche de vérification manuelle (`verifier`)
- [x] Analyse d'un match synthétique de taille réelle (16 joueurs, 10 min) : 2 s hors lecture
- [ ] **Extraction `extraire_match` jamais exécutée sur une vraie démo**
- [ ] Critère de fin : sur une démo DM réelle, chaque mesure vérifiée à la main sur 5 cas

## L2 — CS2 utilitaires et positionnement (CS-UTL-02/03/04, CS-POS-01/02/03)
- [x] Extraction : aveuglements, éclatements de grenades (durées smoke / feu), lancers,
      inventaires aux moments clés
- [~] Flashs (CS-UTL-02) — scénarios synthétiques uniquement
- [~] HE et molotovs : dégâts, durée, adversaires délogés (CS-UTL-03) — idem
- [~] Gaspillage : valeur perdue à la mort, rounds sans lancer (CS-UTL-04) — idem
- [~] Cartes de chaleur : preuves de position + `GET /api/cs2/chaleur` (CS-POS-01) — idem
- [~] Morts isolées (CS-POS-02) — idem
- [~] Trades : morts vengées, tradables non vengées (et par qui), trades réussis, délai,
      occasions manquées (CS-POS-03) — idem
- [ ] Critère de fin : sur une démo Premier réelle, chaque mesure vérifiée à la main sur 5 cas

## L3 — Références pro (CS-REF-01, CS-UTL-01, CS-POS-04)
- [x] Observations par démo pro (lancers, positions installées, lieux), stockées une fois
- [x] Regroupement des points d'arrivée et construction du catalogue par carte (migration 3)
- [x] Commandes `references ajouter / reconstruire / lister`, route `GET /api/cs2/references`
- [~] Rattachement des smokes et molotovs de Mathieu : reconnue / ratée de N u / hors
      référence (CS-UTL-01) — données synthétiques uniquement
- [~] Lignes de vue coupées par les smokes (approximation 2D) — idem
- [~] Positions installées comparées aux pros (CS-POS-04) — idem
- [ ] **Aucune démo pro lue** : catalogue vide tant que Mathieu n'en a pas fourni
- [ ] Critère de fin : chaque smoke de Mathieu rattachée à une référence ou signalée hors
      référence, sur un vrai match

## L4 — Décisions et économie (CS-DEC-*, CS-ECO-01, CS-STR-01)
- [x] Extraction : vainqueur des rounds, bombe, économie, lieu à la pose
- [x] Déroulé des rounds (vivants par équipe à chaque mort)
- [~] Duels d'ouverture (CS-DEC-01) — scénarios synthétiques uniquement
- [~] Rotations après la pose (CS-DEC-02) — idem
- [~] Sauver ou rejouer (CS-DEC-03) — idem
- [~] Après pose et retakes (CS-DEC-04) — idem
- [~] Clutchs (CS-DEC-05) — idem
- [~] Économie : achats désynchronisés, victoire par type d'achat, valeur perdue (CS-ECO-01) — idem
- [~] Stratégie : sites de pose, répétitions, adversaires, moitiés (CS-STR-01) — idem
- [x] Analyse complète d'un match synthétique de 24 rounds : 1,9 s hors lecture de la démo
- [ ] Critère de fin : mesures produites et vérifiées sur 3 vrais matchs

## L5 — Débrief (COM-04/05/06)
- [x] Constats : référence personnelle, cible provisoire, impact estimé, 3 priorités
- [x] Preuves rattachées à chaque constat, avec lien vers le replay (COM-04)
- [x] Fiabilité validée à la main par version de mesure (`fiabilite`, NF-06)
- [x] Rédaction Gemini / Ollama / aucune ; données sans nom ni identifiant (NF-05)
- [x] Rejet de tout texte contenant un chiffre absent des mesures (COM-05)
- [x] Coût par débrief calculé sur les jetons facturés, cumul (NF-04)
- [x] Débrief automatique à l'import, API `GET /api/parties/{id}/debrief`
- [~] Gemini et Ollama testés avec des réponses simulées uniquement : **aucun appel réel**
- [ ] Coût mesuré sur un vrai débrief (clé Gemini de Mathieu)
- [ ] Critère de fin : le débrief d'un vrai match apprend quelque chose à Mathieu

## L6 — Interface et replay 2D (COM-03, CS-RPL-01, NF-02)
- [ ] Tableau de bord, débrief, progression, replay radar, PWA

## L7 — Second écran CS2 (CS-LIVE-01)
- [ ] GSI en direct

## L8 — Geometry Dash (GD-*)
- [ ] Mod Geode + analyses + replay

## L9 — LoL et TFT (LOL-*, TFT-*)
- [ ] API Riot, analyses, second écran LoL

## L10 — Replay 3D (CS-RPL-02)
- [ ] three.js

## Décisions

| Date | Lot | Décision | Pourquoi |
|---|---|---|---|
| 2026-10-13 | L0 | Disposition `src/postgame/` + `tests/` à la racine, un sous-paquet par jeu dans `postgame/games/` | Un jeu = un module derrière `ModuleJeu`, sans toucher au reste |
| 2026-10-13 | L0 | Surveillance par **scrutation** (5 s) plutôt que `watchdog` | Gère simplement les démos en cours d'écriture (taille stable N s) et les dossiers réseau ; coût négligeable |
| 2026-10-13 | L0 | Toute démo importée est **copiée** dans `data/archives/<jeu>/` | Le jeu purge les démos Premier ; les démos DM tournent sur 10 noms fixes ; la re-analyse (COM-08) a besoin des originaux |
| 2026-10-13 | L0 | Déduplication par empreinte SHA-256 du contenu | Un même fichier vu à deux endroits (replays + import manuel) n'est importé qu'une fois |
| 2026-10-13 | L0 | Dates des parties stockées en UTC ISO 8601 ; date = date de modification du fichier | La démo ne contient pas de date fiable ; l'interface convertit en heure locale |
| 2026-10-13 | L0 | Lecture CS2 en deux temps : `extraire()` (demoparser2) puis `construire_fiche()` (pure) | Tester la logique sans vraie démo ; ajuster sur les diagnostics réels |
| 2026-10-13 | L0 | Mode CS2 déduit par heuristique (morts par round, joueurs, score 13) | demoparser2 n'expose ni `game_mode` ni `game_type` ; Premier et compétitif non distingués tant qu'on n'a pas vu `match_making_mode` sur vraies démos |
| 2026-10-13 | L0 | Joueur suivi = SteamID64 de `postgame.toml`, sinon nom du client de l'en-tête | Indispensable au résultat ; le repli par nom couvre les démos enregistrées par le client |
| 2026-10-13 | L0 | Enregistrement DM : bascule F8 sur 10 noms tournants `postgame_XX.dem` | Les fichiers de config CS2 n'ont ni horodatage ni déclencheur de début de partie |
| 2026-10-13 | L0 | Commande `diagnostic` qui résume une démo en JSON | Permet de caler la lecture sur les vraies démos sans transférer les démos elles-mêmes |
| 2026-10-13 | L1 | Analyses en pandas + numpy (pas polars) | demoparser2 renvoie du pandas ; volumes modestes (~600 k lignes par DM) ; 2 s par match |
| 2026-10-13 | L1 | Précision max sous 34 % de la vitesse max de l'arme | Règle du moteur ; vitesses max dans `armes.py`, à revérifier après les mises à jour |
| 2026-10-13 | L1 | Direction du tir = vue + 2 × aim punch | `weapon_recoil_scale` = 2 ; permet de mesurer la compensation du recul sans évènement d'impact |
| 2026-10-13 | L1 | Apparition = passage à « repéré par moi » après 0,5 s sans l'être | Exigence CS-AIM-05 ; lancer de rayons repoussé tant que la vérification manuelle ne montre pas de biais |
| 2026-10-13 | L1 | En DM (≤ 1 round), tous les autres joueurs sont adversaires | Le DM officiel peut être en chacun pour soi ; l'indicateur « repéré » ne concerne de toute façon que les ennemis |
| 2026-10-13 | L1 | Toute mesure naît `fiable=False` | NF-06 : seule une vérification manuelle sur données réelles la rend utilisable par le débrief |
| 2026-10-13 | L2 | Aveuglement significatif ≥ 1 s ; flash convertie = kill de l'équipe sur un aveuglé dans les 2 s | Exigence CS-UTL-02 ; seuils notés dans docs/MESURES_CS2.md, ajustables après vérification |
| 2026-10-13 | L2 | Trade = tueur abattu par l'équipe dans les 5 s ; tradable = coéquipier à moins de 800 u ; isolée au-delà de 1000 u | Seuils usuels des outils d'analyse ; distance 2D sans géométrie de carte |
| 2026-10-13 | L2 | Kills et morts stockés comme preuves avec position et camp | Une seule table sert les débriefs et les cartes de chaleur multi-parties |
| 2026-10-13 | L3 | Lieux nommés par `last_place_name` (callouts de la carte) | Exigence « rien n'est écrit à la main » : la carte fournit ses propres noms |
| 2026-10-13 | L3 | Regroupement maison (centres mobiles, rayon 120 u, ≥ 3 lancers) plutôt que scikit-learn | Évite une dépendance lourde ; volumes de quelques milliers de points |
| 2026-10-13 | L3 | Observations brutes stockées par démo pro, catalogue recalculé à chaque ajout | Ajout incrémental de démos ; seuils ajustables sans relire les démos |
| 2026-10-13 | L3 | Smoke reconnue < 150 u, ratée < 400 u, hors référence au-delà | Une smoke CS2 fait ~144 u de rayon : à 150 u, elle couvre encore l'essentiel de la zone visée |
| 2026-10-13 | L3 | « Ligne de vue utile » approchée en 2D (segment adversaire–allié traversant la smoke) | Pas de géométrie de carte disponible ; le lancer de rayons reste une piste (CS-AIM-05) |
| 2026-10-13 | L4 | Round « perdu d'avance » = Mathieu vivant, équipe ≤ 2, adversaires ≥ équipe + 2 | Définition simple et vérifiable à l'œil ; à ajuster après vérification |
| 2026-10-13 | L4 | Rotation déclenchée par la pose seulement | La démo ne contient ni les annonces vocales ni les pings |
| 2026-10-13 | L4 | Types d'achat : éco < 1 500 $, partiel < 4 000 $, complet au-delà ; rounds 1 et 13 = pistolet | Seuils usuels ; MR12 en Premier et compétitif |
| 2026-10-13 | L4 | Site de pose déduit du lieu du poseur (« BombsiteA » → A) | `bomb_planted.site` est un index d'entité, pas une lettre |
| 2026-10-13 | L5 | Modèle par défaut `gemini-3.1-flash-lite` | Le moins cher de la génération 3 (0,25 $ / 1,50 $ par Mjetons) ; la tâche est de la reformulation contrainte |
| 2026-10-13 | L5 | Contrôle automatique des chiffres de la réponse | Garantit « n'invente aucun chiffre » sans relecture humaine |
| 2026-10-13 | L5 | Les textes des preuves ne partent pas vers le modèle | Ils contiennent des pseudos (NF-05) ; les preuves sont rattachées par l'appli, pas par le modèle |
| 2026-10-13 | L5 | Fiabilité stockée en base par (mesure, version), modifiable sans toucher au code | Mathieu valide ses mesures au fil des vérifications |
| 2026-10-13 | L5 | `httpx` passe en dépendance principale | Client HTTP testable (MockTransport) pour Gemini, Ollama, puis l'API Riot |
