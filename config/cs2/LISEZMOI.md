# Enregistrer ses démos de deathmatch et d'entraînement (CS-SRC-02)

CS2 ne garde aucune démo des parties de deathmatch : il faut les enregistrer soi-même avec
la commande client `record`. `postgame.cfg` réduit ça à une touche.

## Installation (une fois, sur le PC de jeu)

1. Copier `postgame.cfg` dans
   `C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg\`
2. Dans ce même dossier, ouvrir (ou créer) `autoexec.cfg` et ajouter à la fin :
   ```
   exec postgame
   ```
3. Steam → clic droit sur Counter-Strike 2 → Propriétés → Options de lancement : ajouter
   `+exec autoexec` (CS2 n'exécute pas toujours `autoexec.cfg` tout seul).
4. Activer la console : Paramètres → Jeu → Activer la console développeur → Oui.

## Usage

- En jeu (une fois connecté au serveur), **F8** démarre l'enregistrement, **F8** l'arrête.
  La console affiche `[Postgame] enregistrement en cours` / `arrete`.
- La démo apparaît dans `game\csgo\postgame_XX.dem`. Le service Postgame la voit, attend
  qu'elle ne grossisse plus, puis l'importe et l'archive.
- Penser à arrêter avant de quitter le serveur (sinon CS2 arrête lui-même l'enregistrement
  à la déconnexion, ce qui convient aussi).

Pour changer de touche : remplacer `F8` à la ligne `bind` de `postgame.cfg`.

## Limites connues

- Il n'existe pas de déclencheur « début de partie » dans les fichiers de config : on ne
  peut pas démarrer l'enregistrement tout seul. La touche unique est le meilleur compromis.
- Ce qu'un enregistrement client contient en DM officiel (les autres joueurs sont-ils
  tous présents, ou seulement ceux proches de soi ?) reste à vérifier : c'est l'objet du
  test L0 dans `A_VALIDER.md`.
