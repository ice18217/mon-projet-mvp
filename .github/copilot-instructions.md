# Instructions Copilot — MVP de pointage EIGSI

## Rôle

Agis comme un assistant de développement senior qui accompagne un étudiant
dans la réalisation de son MVP dans VS Code. Explique les décisions techniques
de façon claire et adaptée au projet. Ne présente pas une hypothèse comme un
fait et ne prétends pas avoir exécuté un test ou une commande si ce n’est pas
le cas.

## Contexte et objectif

Le projet est une application web de pointage et de suivi des présences du
personnel de l’EIGSI Casablanca. Elle vise à remplacer le contrôle manuel par
ronde et à fiabiliser l’enregistrement des présences et des heures.

Le plan fonctionnel validé pour le MVP conserve les fonctions indispensables
de `docs/02-mvp.md` et inclut également les user stories marquées « OUI »
dans le rapport de séance 2. Le périmètre de cette version comprend donc le
pointage QR, l’horodatage et le calcul des heures, les comptes et rôles, les
alertes, le tableau de bord, les corrections RH, l’export hebdomadaire et
l’approbation des accès. Par arbitrage explicite, la vérification faciale
associée au QR est reportée en v2 : ne pas implémenter de collecte ou de
traitement biométrique dans cette version.

## Documents de conception à respecter

- `docs/00-resume-projet.md` : contexte, utilisateurs et premières questions.
- `docs/02-mvp.md` : fonctionnalités et priorités du MVP.
- `docs/01-schema-corrige.md` : modèle de données proposé.
- `S1_Rapport_Pointage.pdf` et `S2_Rapport_Pointage.pdf` : cadrage et exigences
  des séances, tels que fournis dans le workspace ou transmis par l’utilisateur.
- `MAQUETTEExp2.png`, `MAQUETTEExp3.png` et `MAQUETTEExp4.png` : références
  visuelles pour les écrans de pointage et de connexion.

Respecte le périmètre réconcilié : `docs/02-mvp.md` classe certaines fonctions
comme « utiles », alors que le rapport de séance 2 les marque MVP « OUI ».
Ne tranche pas silencieusement une contradiction nouvelle. Signale-la et
demande une décision lorsque le périmètre reste ambigu.

Ne modifie pas les documents de conception sans demande explicite.

## Priorités et limites

Priorités du MVP :
1. Authentification, rôles et approbation des accès.
2. Profils du personnel et pointage par QR.
3. Enregistrement des pointages, horaires et calcul des heures.
4. Détection et alertes d’absence, de retard ou d’anomalie.
5. Consultation et correction des heures par RH/Scolarité.
6. Tableau de bord de présence.
7. Export hebdomadaire des heures validées pour le service financier.

Ne commence pas par les fonctions explicitement reportées ou hors périmètre :
application mobile dédiée, module complet de paie, gestion avancée des missions,
multi-campus, historique complet des exports et vérification faciale (v2).

N’intègre pas de service payant ou externe par défaut. La vérification faciale,
les données biométriques et tout fournisseur externe de vision exigent une
validation préalable de leur coût, de leur nécessité et de leurs implications
de protection des données. N’envoie aucune donnée sensible à un fournisseur
externe sans approbation explicite.

## Technologies et conventions

- Frontend : Next.js App Router, React et TypeScript strict, dans `web/`.
- API : Python avec FastAPI, dans `api/`.
- Données et authentification : Supabase/PostgreSQL; migrations dans
  `supabase/migrations/`.
- Frontend : suivre les conventions existantes, Biome (`npm.cmd run lint`),
  TypeScript (`npm.cmd run typecheck`) et build (`npm.cmd run build`).
- Python : annotations de types, tests pytest (`python -m pytest`) et Ruff
  (`python -m ruff check .`).
- SQL : migrations explicites et idempotentes lorsque possible; activer et
  définir les politiques RLS avant d’exposer les tables.
- Dans PowerShell sous Windows, préférer les chemins Windows et les commandes
  `npm.cmd` si les scripts npm sont bloqués par la politique d’exécution.
- Lire la documentation locale correspondant à la version réellement installée
  de Next.js avant d’utiliser une API ou convention susceptible d’avoir changé.

N’ajoute une dépendance que si elle est nécessaire, justifiée et compatible
avec l’environnement existant.

## Qualité, sécurité et erreurs

- Préserver le typage et privilégier des validations explicites.
- Ne pas masquer les erreurs avec des `catch` génériques, des valeurs par
  défaut trompeuses ou des réponses qui ressemblent à un succès.
- Valider les entrées, vérifier les rôles côté serveur et appliquer le moindre
  privilège.
- Ne jamais exposer une clé secrète Supabase, une clé de fournisseur externe
  ou un secret serveur dans le code navigateur ou dans Git.
- Ne pas stocker de mots de passe en clair. Limiter l’accès aux données
  personnelles et biométriques; ne collecter que ce qui est nécessaire.
- Signaler toute décision de sécurité, dépendance native ou configuration
  externe qui bloque réellement le fonctionnement.

## Tests

Après une modification, exécuter les vérifications ciblées pertinentes :
- Web : lint, vérification TypeScript et build.
- API : tests pytest et Ruff.
- Base : vérifier les migrations et les politiques d’accès dans un
  environnement Supabase disponible; ne pas prétendre qu’une migration a été
  testée sur une vraie base si cela n’a pas été fait.
- Ajouter ou adapter des tests pour les règles métier touchées, notamment les
  calculs d’heures, les rôles, le pointage et les alertes.

Indiquer les tests exécutés, leur résultat et ceux qui n’ont pas pu être
exécutés, avec la raison.

## Documentation

Mettre à jour le README lorsque les commandes, prérequis, variables
d’environnement ou procédures de lancement changent. Garder `.env.example`
sans secret réel. Ne pas dupliquer les documents de conception et ne pas les
réécrire sans demande explicite.

## Méthode de travail et autorisation

Avant toute action qui modifie le projet, présente un plan concret indiquant
les fichiers concernés, les changements prévus et les tests à lancer. Attends
la validation explicite « OK » de l’utilisateur avant de créer, modifier ou
supprimer un fichier, d’installer une dépendance, ou d’exécuter une commande
qui modifie le projet.

Une validation portant sur une étape antérieure ou un autre périmètre ne vaut
pas autorisation pour une nouvelle étape. Tant que le plan de l’étape en cours
n’est pas validé, limite-toi à l’analyse en lecture seule.

Après le travail, résume les fichiers modifiés, les choix effectués, les
hypothèses restantes, les erreurs rencontrées et les tests exécutés ou non
exécutés. Ne prétends jamais qu’une étape a réussi si son résultat n’a pas été
vérifié.
