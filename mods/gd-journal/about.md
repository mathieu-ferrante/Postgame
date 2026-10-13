# Postgame — journal

Journalise, pour chaque essai sur un niveau : le mode (normal ou entraînement), chaque appui
et relâchement avec son horodatage, sa frame et la position X, la mort (position, objet
touché), la progression en %. Les fichiers vont dans le dossier de sauvegarde du mod et sont
lus par le service Postgame.

**Le mod ne modifie rien** : chaque fonction du jeu interceptée est d'abord appelée telle
quelle, puis le mod se contente d'écrire une ligne dans un fichier.
