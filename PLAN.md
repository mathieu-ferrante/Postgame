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
- [ ] Flashs, HE, molotovs, gaspillage, chaleur, morts isolées, trades

## L3 — Références pro (CS-REF-01, CS-UTL-01, CS-POS-04)
- [ ] Catalogue des lancers et positions appris sur démos pros

## L4 — Décisions et économie (CS-DEC-*, CS-ECO-01, CS-STR-01)
- [ ] Duels d'ouverture, rotations, saves, retakes, clutchs, économie, stratégie

## L5 — Débrief (COM-04/05/06)
- [ ] Rédaction, priorisation, liens vers les preuves, coût mesuré

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
