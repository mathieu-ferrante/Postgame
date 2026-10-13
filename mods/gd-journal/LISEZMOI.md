# Mod Geode « Postgame — journal » (GD-01)

Journalise les essais, clics et morts dans Geometry Dash pour l'analyse Postgame.
**Il ne modifie rien** : chaque fonction interceptée est appelée telle quelle, puis le mod
écrit une ligne dans un fichier. Aucune lecture ni écriture de la mémoire du jeu en dehors
de ce que l'API Geode expose.

Cible : Geometry Dash **2.2081**, Geode **5.11.1** (à adapter dans `mod.json` si la version
installée diffère).

## Compiler (PC de jeu, Windows)

Prérequis (une fois) :

1. Visual Studio 2022 Build Tools avec « Développement Desktop en C++ » (ou Visual Studio
   Community), et CMake.
2. Geode CLI : `winget install GeodeSDK.GeodeCLI` (ou depuis github.com/geode-sdk/cli).
3. `geode sdk install` puis `geode sdk install-binaries` (définit `GEODE_SDK`).

Puis, dans ce dossier :

```powershell
geode build
```

Le fichier `mathieu.postgame-journal.geode` produit est copié automatiquement dans le
dossier des mods de Geode si `geode config` connaît l'installation de GD ; sinon, le copier
dans `…\Geometry Dash\geode\mods\`.

## Où vont les journaux

`%LOCALAPPDATA%\GeometryDash\geode\mods\mathieu.postgame-journal\sessions\`

Un fichier par passage dans un niveau : `AAAAMMJJ-HHMMSS_<niveau>.gdsession`, écrit d'abord
en `.gdsession.part` puis renommé quand on quitte le niveau. Le service Postgame surveille
ce dossier (`[gd] dossiers_journaux` dans `postgame.toml`).

## Format (JSON Lines, une ligne par évènement)

| type | champs |
|---|---|
| `session` | `format`, `debut` (heure locale), `niveau {id, nom, createur}`, `plateforme`, `mod` |
| `essai` | `n` (compteur d'essais du jeu), `mode` (`normal` / `practice`), `t`, `tn`, `f`, `x` |
| `input` | `t`, `tn`, `f`, `x`, `y`, `appui` (true = appui, false = relâchement), `bouton`, `j` (joueur 1 ou 2) |
| `pos` | `t`, `tn`, `f`, `x`, `y` (toutes les 4 frames, joueur 1 vivant) |
| `mort` | `t`, `tn`, `f`, `x`, `y`, `pct`, `objet` (identifiant de l'objet touché) |
| `fin` | niveau terminé : `t`, `tn`, `f`, `pct` = 100, `practice` |
| `fin_session` | `t` |

`t` : millisecondes depuis l'entrée dans le niveau (horloge haute précision du PC, au moment
où le jeu traite l'évènement). `tn` : temps du niveau selon le jeu (secondes). `f` : numéro
de frame. La précision réelle de l'horodatage des clics est à mesurer (risque du cahier des
charges) : le service la calcule à partir des écarts entre `t` et `tn`.
