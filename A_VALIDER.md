# À valider par Mathieu

Ce que seul Mathieu peut faire ou tester, lot par lot. Chaque point dit **quoi faire, sur
quelle machine, et le résultat attendu**. Une fois fait, cocher la case et noter le
résultat (ou me le dire).

## L0 — Socle

### 1. Fournir des démos (n'importe quelle machine)
- [ ] 2 ou 3 démos **Premier** (`.dem`, dans `...\game\csgo\replays\` après « Télécharger »
      dans l'onglet « Regarder » du jeu).
- [ ] 1 ou 2 démos de **deathmatch** enregistrées avec F8 (voir point 3).
- Les déposer dans `tests/donnees/` du dépôt (dossier ignoré par git : rien n'est publié).
- **Attendu** : `.venv\Scripts\python -m pytest -m demo_reelle` passe ; je calerai la
  lecture (mode, résultat, durée) sur ces démos.

### 2. Donner son SteamID64 (n'importe quelle machine)
- [ ] Le SteamID64 (17 chiffres, visible sur steamid.io à partir du profil Steam).
- Il va dans `postgame.toml` (local, ignoré par git), section `[joueur]`.
- **Attendu** : la fiche d'une démo Premier affiche `victoire` / `defaite` et le bon score.

### 3. Valider l'enregistrement des démos de deathmatch (PC de jeu)
- [ ] Installer `config/cs2/postgame.cfg` comme décrit dans `config/cs2/LISEZMOI.md`.
- [ ] Lancer une partie de **deathmatch officiel** (serveur Valve), appuyer sur **F8**,
      jouer 2-3 minutes, appuyer de nouveau sur **F8**.
- **Attendu** :
  - la console affiche `[Postgame] enregistrement en cours` puis `arrete` ;
  - un fichier `game\csgo\postgame_01.dem` de plusieurs Mo existe ;
  - `python -m postgame diagnostic "<chemin>\postgame_01.dem"` crée un fichier
    `postgame_01.diagnostic.json` : **me l'envoyer** (il ne contient pas la démo, seulement
    sa description ; il contient les pseudos et SteamID des joueurs présents).
- Si `record` est refusé sur les serveurs DM officiels (message dans la console), le noter :
  on passera par des serveurs communautaires (exigence CS-SRC-02, risque n°1).

### 4. Installer et lancer le service (PC de jeu)
- [ ] Python 3.13 installé (`py -3.13 --version`).
- [ ] À la racine du dépôt : `powershell -ExecutionPolicy Bypass -File scripts\installer.ps1`
- [ ] Renseigner `postgame.toml` (SteamID, vérifier les deux dossiers CS2).
- [ ] `powershell -ExecutionPolicy Bypass -File scripts\lancer.ps1`
- **Attendu** :
  - `http://localhost:8765/api/jeux` montre les deux dossiers CS2 avec `"existe": true` ;
  - les démos déjà présentes dans `replays` apparaissent dans
    `http://localhost:8765/api/parties` après quelques secondes ;
  - une nouvelle démo enregistrée avec F8 apparaît ~10 s après l'arrêt ;
  - `http://localhost:8765/api/import/etat` ne montre pas d'erreur.
- [ ] Depuis le téléphone (même Wi-Fi) : `http://<IP du PC>:8765/api/sante` répond.
      Si non : autoriser Python dans le pare-feu Windows (réseau privé).

## L1 — Mécanique CS2

Dépend du point L0-3 (une démo de DM enregistrée) et du SteamID (L0-2).

### 5. Vérifier les mesures à la main sur une démo DM (PC de jeu)
- [ ] Importer une démo DM (automatique si le service tourne), relever son numéro avec
      `.venv\Scripts\python -m postgame parties`.
- [ ] `.venv\Scripts\python -m postgame verifier <numéro>` → crée
      `data\verifications\partie_<numéro>.md`.
- [ ] Dans CS2 : `playdemo "<chemin indiqué dans la fiche>"`, puis pour chaque ligne
      `demo_gototick <tick>` ; regarder depuis les yeux de Mathieu (touche espace / clic).
- **Attendu** : pour chaque mesure, les 5 cas décrits sont visibles à l'écran (ex. « première
  balle à 180 u/s » : Mathieu tire en courant ; « apparaît à 20° à gauche, 5° trop bas » :
  l'adversaire surgit bien à gauche, viseur sous sa tête). Cocher, ou noter ce qui diffère.
- **Me renvoyer** la fiche cochée : les mesures confirmées passeront « fiables ».
- Point particulier : si tous les moments sont décalés d'un même délai, le dire (décalage
  de ticks entre demoparser2 et le lecteur du jeu).

### 6. Mesurer le temps d'analyse (PC de jeu)
- [ ] Noter le temps d'import d'une démo Premier complète (visible dans le journal du
      service, entre « découvert » et « importe »).
- **Attendu** : moins de 60 s (NF-03).
