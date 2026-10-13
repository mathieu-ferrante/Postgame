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

## L7 — Second écran CS2

### 17. Installer la config GSI et journaliser une vraie partie (PC de jeu)
- [ ] Service lancé, puis `.venv\Scripts\python -m postgame gsi-config` : écrit
      `gamestate_integration_postgame.cfg` directement dans `game\csgo\cfg\` si le
      dossier est trouvé (sinon dans `data\`, à copier dans `game\csgo\cfg\`).
- [ ] Relancer CS2, jouer une partie Premier (ou compétitive) en entier.
- **Attendu** :
  - `http://localhost:8765/direct` (et sur le téléphone) affiche carte, score, argent, vie,
    et pendant chaque phase d'achat un conseil (Achat complet / Force possible / Éco…) ;
  - un journal `data\gsi\journal_<date>.jsonl` existe : **me l'envoyer** (il contient le
    pseudo et le SteamID de Mathieu, rien d'autre de personnel). Il dira ce que GSI expose
    vraiment (risque du cahier des charges : l'argent des coéquipiers n'est probablement
    pas fourni).
- [ ] Juger le conseil d'achat sur quelques rounds : est-il cohérent avec ce que l'équipe
      a fait ? Me dire les cas faux.

### 18. Mesurer le retard du second écran (PC de jeu + téléphone)
- [ ] Pendant un achat, comparer l'argent affiché en jeu et sur le téléphone : le
      téléphone doit suivre en moins d'une demi-seconde (NF-03). Une vidéo au ralenti du
      téléphone posé devant l'écran donne une mesure précise.

## L8 — Geometry Dash

### 19. Compiler et installer le mod (PC de jeu)
- [ ] Vérifier la version de GD (écran titre, en bas) et de Geode installées ; me les
      donner si ce n'est pas GD 2.2081 / Geode 5.11.x (`mods/gd-journal/mod.json`).
- [ ] Suivre `mods/gd-journal/LISEZMOI.md` : Visual Studio Build Tools, Geode CLI,
      `geode sdk install`, puis `geode build` dans `mods/gd-journal`.
- **Attendu** : le mod « Postgame — journal » apparaît dans la liste des mods de Geode.
  S'il ne compile pas, **me copier le message d'erreur** : le code n'a pas pu être compilé
  sur le poste de développement.

### 20. Enregistrer une vraie séance d'entraînement (PC de jeu)
- [ ] Service lancé ; jouer 15 à 30 minutes sur un niveau en cours d'apprentissage
      (essais normaux, puis un peu d'entraînement, puis normaux), puis quitter le niveau.
- **Attendu** :
  - un fichier `.gdsession` dans
    `%LOCALAPPDATA%\GeometryDash\geode\mods\mathieu.postgame-journal\sessions\` ;
  - la séance apparaît dans l'interface (badge « Geometry Dash »), avec son débrief et la
    page « essais superposés » ;
  - le jeu se comporte exactement comme sans le mod (aucune différence de gameplay).
- [ ] Me donner la valeur de `gd.technique.resolution_ms` (fiche de la séance) : elle dit
      si l'horodatage des clics est assez fin (≈ 4,17 ms attendu si le jeu tourne à 240
      pas par seconde).
- [ ] Juger les « inputs les plus irréguliers » : sont-ce bien les passages où Mathieu
      se sent le moins sûr ? (critère de fin de L8)

## L9 — League of Legends et TFT

Riot ID enregistré dans `postgame.toml` (local) : `iamheremyfriend#hiii`.

### 21. Créer la clé API Riot (n'importe quelle machine)
- [ ] developer.riotgames.com → se connecter avec le compte Riot → « Register Product » →
      **Personal API Key** (n'expire pas, contrairement à la clé de développement de 24 h).
- [ ] La coller dans `secrets.toml` : `[riot] cle = "RGAPI-…"` (jamais commitée).
- [ ] Confirmer le serveur : EUW (`plateforme = "euw1"`, `region = "europe"`) ; sinon me dire
      lequel.
- **Attendu** : `.venv\Scripts\python -m postgame riot synchroniser` affiche le nombre de
  parties LoL et TFT importées ; elles apparaissent dans l'interface.

### 22. Construire les références de haut classement du patch (PC de jeu ou autre)
- [ ] `.venv\Scripts\python -m postgame riot meta` (environ 5 à 10 minutes avec la clé
      personnelle) ; à relancer **à chaque nouveau patch**.
- **Attendu** : les débriefs LoL affichent des cibles « haut classement EUW1, N
  échantillons, patch X » ; la page TFT montre la colonne « Haut classement ».

### 23. Juger un débrief LoL et un débrief TFT réels
- [ ] Ouvrir le débrief d'une vraie partie de chaque (critère de fin de L9).
- [ ] Pendant une partie LoL, ouvrir « En direct » sur le téléphone : le panneau LoL doit
      apparaître au chargement de la partie (API locale du client).
- Me dire ce qui est faux ou inutile.

## Récupération automatique des parties CS2 (AUTO-01)

### 24. FACEIT
- [ ] Me donner le pseudo FACEIT (ou le mettre dans `postgame.toml`, `[faceit] pseudo`).
- [ ] developers.faceit.com → créer une application → clé « Server side » : `secrets.toml`,
      `[faceit] cle = "…"`.
- [ ] Demander l'accès à la **Downloads API** (formulaire FACEIT, réponse en ~30 jours),
      puis mettre le jeton dans `[faceit] jeton_telechargement`.
- **Attendu** : les parties FACEIT apparaissent seules dans Postgame après chaque match
  (`http://localhost:8765/api/sources/etat`).

### 25. Codes de partage Steam (Premier / compétitif)
- [ ] Clé API Web Steam : steamcommunity.com/dev/apikey → `[steam] cle` dans `secrets.toml`.
- [ ] Code d'authentification de l'historique des matchs : page d'aide Steam « Counter-Strike 2
      → Je souhaite gérer mon code d'authentification de l'historique des matchs » →
      `[steam] code_historique`.
- [ ] Un code de partage récent (CS2 → Regarder → Vos matchs → icône de partage) dans
      `postgame.toml`, `[steam] code_connu = "CSGO-…"`.
- **Attendu** : Postgame liste chaque nouvelle partie classée, même sans démo téléchargée.

## Stuffs CS2 (STUFF-01)

### 26. Annotations en jeu (PC de jeu)
- [ ] Une fois des démos pros ajoutées : page Stuffs → « Installer les annotations » (ou
      `.venv\Scripts\python -m postgame annotations`).
- [ ] CS2 → Jouer → Entraînement sur la carte → console : `annotation_load postgame_de_mirage`.
- **Attendu** : marqueurs au sol aux points de lancer, point à viser avec la technique écrite
  (« jumpthrow (clic gauche) »…), zone d'arrivée. Si rien ne s'affiche ou si le jeu signale
  une erreur, me le dire : le format des annotations a pu changer depuis 2024.

### 27. Technique de lancer
- [ ] Sur un stuff connu (ex. smoke window de Mirage en jumpthrow), vérifier que la page
      Stuffs annonce la bonne technique. Si toutes les techniques affichent « clic ? », les
      démos ne contiennent pas les touches des joueurs : me le dire.

## L10 — Revoir les vrais moments dans CS2

### 28. Revoir un de mes moments dans CS2 (PC de jeu)
- [ ] Prérequis : dans `postgame.toml`, `[cs2] dossiers_demos` pointe vers
      `…\Counter-Strike Global Offensive\game\csgo\replays` (ou `game\csgo`) : c'est
      ainsi que Postgame trouve `game\csgo\cfg`.
- [ ] Dans le débrief d'une vraie partie, cliquer « ▶ CS2 » sur une preuve. Dans CS2,
      console : `exec postgame`, attendre le chargement, puis `pg`.
- **Attendu** : la démo s'ouvre, saute 5 s avant le moment, caméra sur moi.
- Si `playdemo` ne trouve pas la démo, ou si `pg` arrive avant la fin du chargement sans
  effet, me le dire (message exact de la console).
- [ ] CS2 fermé : le lien « Le lancer directement sur la démo » (steam://run/730//+exec
      postgame/) doit démarrer CS2 sur la démo.

### 29. Revoir un pro (PC de jeu)
- [ ] Relancer `postgame references ajouter <dossier des démos pros>` : les démos lues avant
      cette version sont relues (tick et joueur). **Ne pas déplacer les démos pros
      ensuite** : Postgame les rejoue depuis leur emplacement.
- [ ] Page Stuffs → un stuff → « Le voir lancé par un pro » → « ▶ CS2 », puis `exec
      postgame` et `pg`.
- **Attendu** : caméra sur le pro, 5 s avant son lancer. Profites-en pour faire la
  capture d'écran du stuff (F12) et l'ajouter à la fiche.
- [ ] Replay 2D d'une de mes parties → « Chercher à cet instant » : la liste montre des
      pros du même camp au même endroit, et « ▶ CS2 » les montre vraiment là.
