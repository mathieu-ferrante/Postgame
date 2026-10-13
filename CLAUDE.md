# Postgame — consignes pour Claude

Le projet est entièrement décrit dans [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md). C'est la
référence : le lire en entier avant toute chose.

## Mode de travail : autonomie de A à Z

Mathieu veut que Claude mène **tout le projet, du lot L0 au lot L10, sans s'arrêter**.

- **Enchaîner les lots** dans l'ordre du cahier des charges, sans demander de validation entre
  deux lots ni entre deux étapes. Pour chaque lot : planifier → se documenter (doc officielle,
  vérifier les API plutôt que supposer) → coder → tester → corriger jusqu'au vert → commiter →
  mettre à jour `PLAN.md` et le README → passer au lot suivant.
- **Trancher seul** les choix techniques ordinaires (bibliothèque, structure, nommage) en
  suivant le cahier des charges ; noter les décisions importantes dans `PLAN.md`.
- **Ne s'arrêter que pour poser une question**, dans l'un de ces cas :
  1. une décision qui appartient à Mathieu et que ni le cahier des charges ni le code ne
     permettent de trancher ;
  2. une action que seul Mathieu peut faire : fournir des démos ou des journaux, tester sur
     le PC de jeu, créer sa clé API Riot, installer quelque chose sur le PC de jeu ;
  3. une action irréversible ou visible de l'extérieur : créer un dépôt GitHub, pousser,
     publier quoi que ce soit.
- **Regrouper les questions** : en poser plusieurs d'un coup plutôt qu'une par une.
- **Ne jamais rester bloqué** : si un lot attend une donnée ou une validation de Mathieu,
  l'inscrire dans `A_VALIDER.md` (quoi faire, sur quelle machine, résultat attendu), avancer
  autant que possible avec des données de substitution clairement marquées comme telles, et
  continuer sur les lots qui n'en dépendent pas.
- **Dire la vérité** sur l'état réel : un test non lancé, une mesure non vérifiée sur données
  réelles ou une fonction non validée sur le PC de jeu est signalé comme tel, jamais présenté
  comme fini.

## Fichiers de suivi

- `PLAN.md` : lots, état d'avancement (cases à cocher), décisions prises. Créé au lot L0.
- `A_VALIDER.md` : ce que Mathieu doit faire ou tester, lot par lot, avec le mode opératoire.

## Environnement

- **Le poste de développement n'est pas le PC de jeu.** Poste Windows d'entreprise : pas de
  Steam ni de CS2, sockets AF_UNIX bloqués, donc **Gradle ne démarre pas** (pas d'Android
  natif ; le téléphone passe par une PWA). Python 3.13 et Node 24 sont disponibles ; `uv` ne
  l'est pas (utiliser `py -3.13 -m venv`).
- Tout ce qui touche au jeu lui-même (dossiers des démos, GSI, mod Geode, performances) se
  valide sur le PC de jeu : Ryzen 5800X, RX 6750 XT, 32 Go, Windows.

## Conventions

- Tout en français : code commenté, interface, documentation, messages de commit.
- Un commit par étape cohérente, message à l'indicatif présent (« Ajoute… », « Corrige… »).
- Jamais de secret commité (clé Riot, jetons) : fichier local ignoré par git.
- Respect des jeux : uniquement démos, GSI, API Riot, API locale de Riot, et un mod Geode qui
  journalise sans rien modifier. Rien qui touche à la mémoire d'un jeu.
