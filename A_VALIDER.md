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

## L2 — Utilitaires et positionnement CS2

### 7. Vérifier les mesures à la main sur une démo Premier (PC de jeu)
- [ ] Même mode opératoire que le point 5, sur une démo **Premier** (`verifier <numéro>`).
- Mesures concernées : `cs2.flash.*`, `cs2.he.*`, `cs2.molotov.*`, `cs2.utilitaires.*`,
  `cs2.position.*`, `cs2.trades.*`.
- **Attendu** : pour chaque mesure, les 5 moments listés correspondent à ce qu'on voit
  (ex. « Flash qui aveugle X 1,8 s » : l'écran de X est bien blanc ; « Mort tradable non
  vengée : Y (450 u) à proximité » : Y était bien tout près et n'a pas tué le tueur).
- Point particulier : vérifier qu'un molotov lancé par Mathieu est bien compté comme le
  sien (le rattachement du feu au lanceur est indirect).

## L3 — Références pros

### 8. Fournir des démos pros (n'importe quelle machine)
- [ ] Télécharger sur HLTV (onglet « Matches » → un match → « GOTV Demo ») des démos
      récentes de **CS2**, en priorité sur les cartes que Mathieu joue le plus. Viser
      **5 démos par carte** au minimum (une démo = une carte d'un match).
- [ ] Décompresser les archives (`.rar` / `.zip`) et poser les `.dem` dans un dossier,
      par exemple `D:\Postgame\demos_pros\`.
- [ ] `.venv\Scripts\python -m postgame references ajouter D:\Postgame\demos_pros`
- **Attendu** : pour chaque carte, plusieurs dizaines de lancers et une dizaine de
  positions (`references lister`). `http://localhost:8765/api/cs2/references?carte=de_mirage`
  montre des smokes nommées avec des lieux connus (« Window », « Jungle »…).
- [ ] Puis `.venv\Scripts\python -m postgame reanalyser --jeu cs2` pour rattacher les
      smokes des parties déjà importées.

### 9. Vérifier le rattachement des smokes (PC de jeu)
- [ ] `verifier <numéro>` sur un match Premier, section `cs2.smoke.part_reconnues`.
- **Attendu** : une smoke « reconnue : smoke Window depuis TSpawn » est bien la smoke
  fenêtre classique ; une smoke « ratée de 220 u » est visiblement à côté ; une smoke
  « hors référence » n'est pas une smoke usuelle.

## L4 — Décisions et économie CS2

### 10. Vérifier sur 3 matchs Premier (PC de jeu)
- [ ] Pour 3 matchs importés : `verifier <numéro>`, sections `cs2.ouverture.*`,
      `cs2.rotation.*`, `cs2.save.*`, `cs2.apres_pose.*` / `cs2.retake.*`, `cs2.clutch.*`,
      `cs2.eco.*`, `cs2.strat.*`.
- **Attendu** : les rounds cités correspondent (ex. « Round 7 : 1v3 perdu, 1 kill » : c'est
  bien le round 7 du tableau des scores ; « Mathieu en achat complet (4 700 $) alors que
  l'équipe est en éco » : vrai dans le tableau d'achat du jeu).
- Point particulier : la numérotation des rounds suit les fins de freeze vues dans la
  démo ; si un round d'échauffement ou une pause technique décale tout d'un cran, le dire.

## L5 — Débrief

### 11. Créer la clé Gemini (n'importe quelle machine)
- [ ] Sur aistudio.google.com → « Get API key » → créer une clé (le projet doit avoir la
      facturation activée pour utiliser le crédit de 15 € ; sinon le niveau gratuit suffit
      pour essayer).
- [ ] Copier `secrets.exemple.toml` en `secrets.toml` (à côté de `postgame.toml`, ignoré
      par git) et y coller la clé dans `[gemini] cle = "…"`.
- **Attendu** : `.venv\Scripts\python -m postgame debrief <numéro>` affiche un débrief
  rédigé et une ligne `[redige] gemini gemini-3.1-flash-lite — N + M jetons, 0.00x $`.
- Si la ligne affiche `[rejete]`, me transmettre le message (le modèle a écrit un chiffre
  qui n'est pas dans les mesures).

### 12. Juger le débrief d'un vrai match (PC de jeu)
- [ ] Pendant la validation des mesures, mettre `mesures_experimentales = true` dans la
      section `[debrief]` de `postgame.toml` (sinon le débrief est vide tant qu'aucune
      mesure n'est marquée fiable).
- [ ] Lire le débrief d'un match Premier récent.
- **Attendu** (critère de fin de L5) : au moins un des 3 points prioritaires apprend quelque
  chose de précis à Mathieu, et les moments cités se retrouvent dans le replay.
- Me dire ce qui sonne faux, générique ou mal priorisé : j'ajusterai les poids et les
  cibles (`src/postgame/debrief/objectifs.py`).

### 13. Marquer les mesures fiables (au fil des vérifications)
- [ ] Pour chaque mesure dont les 5 cas sont confirmés (points 5, 7, 9, 10) :
      `.venv\Scripts\python -m postgame fiabilite <nom de la mesure> --note "5 cas vérifiés"`
- **Attendu** : elle apparaît dans le débrief même avec `mesures_experimentales = false`.

## L6 — Interface, replay 2D, téléphone

### 14. Installer Node.js et construire l'interface (PC de jeu)
- [ ] Installer Node.js LTS (nodejs.org), puis relancer `scripts\installer.ps1` (il
      construit l'interface dans `web\dist`).
- **Attendu** : `http://localhost:8765/` affiche la liste des parties.

### 15. Exporter les radars officiels (PC de jeu)
- [ ] Avec Source 2 Viewer (outil libre « ValveResourceFormat », à télécharger par Mathieu
      s'il le souhaite), ouvrir `game\csgo\pak01_dir.vpk` et exporter, pour chaque carte :
  - `panorama\images\overheadmaps\<carte>_radar_psd.vtex_c` → PNG 1024×1024, enregistré
    sous `data\radars\<carte>.png` ;
  - `resource\overviews\<carte>.txt` → copié tel quel dans `data\radars\<carte>.txt`.
- **Attendu** : le replay 2D affiche le radar du jeu et les joueurs tombent pile dans les
  couloirs (sinon, le .txt corrige le calage). Sans ces fichiers, le replay dessine la
  silhouette de la carte à partir des déplacements.

### 16. Ouvrir l'interface sur le téléphone et l'installer (PC de jeu + téléphone)
- [ ] Sur le même Wi-Fi : `http://<IP du PC>:8765/` dans le navigateur du téléphone
      (pare-feu Windows : autoriser Python sur les réseaux privés).
- [ ] Pour l'**installer comme une appli** (PWA), il faut du HTTPS :
  1. installer mkcert sur le PC (`winget install FiloSottile.mkcert`) ;
  2. `mkcert -install` puis, dans le dossier du dépôt :
     `mkdir certs; mkcert -cert-file certs\postgame.pem -key-file certs\postgame-key.pem <IP du PC> localhost`
  3. dans `postgame.toml`, section `[service]` : `certificat = "certs/postgame.pem"` et
     `cle_privee = "certs/postgame-key.pem"`, puis relancer le service ;
  4. copier le certificat racine de mkcert (`mkcert -CAROOT` donne le dossier,
     fichier `rootCA.pem`) sur le téléphone et l'installer (Android : Paramètres →
     Sécurité → Chiffrement → Installer un certificat → Certificat CA) ;
  5. ouvrir `https://<IP du PC>:8765/` → menu du navigateur → « Installer l'application ».
  - Alternative plus simple si Tailscale est utilisé : `tailscale serve` fournit le HTTPS.
- **Attendu** : l'icône Postgame sur l'écran d'accueil ; l'appli s'ouvre en plein écran,
  les débriefs et le replay sont lisibles au doigt.
- Me dire ce qui gêne au quotidien (lisibilité, boutons trop petits, pages lentes).
