# Guide de démonstration — Pointage EIGSI

Ce guide propose un scénario de vidéo montrant le flux réel du MVP : accès,
QR, horaires et alertes, correction auditée, tableau de bord et export. Utiliser
uniquement un projet Supabase dédié aux tests et des identités synthétiques.
Ne pas filmer de vrais noms, adresses e-mail, QR personnels, mots de passe,
clés ou URL privées.

## Préparer l’environnement

1. Suivre les instructions d’installation du [README](../README.md) et vérifier
   que le web et l’API démarrent.
2. Utiliser un projet Supabase de démonstration distinct de la production et
   appliquer toutes les migrations après revue.
3. Préparer des comptes de test déjà liés à des lignes `personnel` actives :
   - un compte opérateur RH/Scolarité;
   - un compte personnel avec le rôle `personnel`;
   - un compte Finance (il peut aussi être opérateur RH si nécessaire).
4. Pour montrer l’approbation des accès, préparer en plus un compte
   d’administrateur technique actif/approuvé et un personnel en attente. Les
   utilisateurs doivent déjà exister dans Supabase Auth et avoir leur fiche
   personnel liée; l’application n’a pas d’inscription publique.
5. Si le scan est filmé sur deux appareils, servir le site via HTTPS sur une
   adresse accessible aux deux appareils. La caméra n’est autorisée que sur un
   contexte sécurisé (HTTPS ou `localhost`).
6. Vérifier que le QR de test a été créé et ne contient aucune donnée
   personnelle lisible. Ne pas inclure son image dans la vidéo ni la publier.

### Préparer les données nécessaires à l’export

L’export ne concerne que les semaines entièrement terminées (lundi à dimanche)
en `Africa/Casablanca`. Les scans créés pendant la vidéo sont horodatés par le
serveur et ne peuvent donc pas alimenter une semaine antérieure.

Pour montrer un export non vide, préparer au préalable des pointages de test
sur une semaine passée dans le projet isolé, via une procédure de préparation
de données de démonstration autorisée et revue. Aucun script de peuplement
historique n’est fourni par le dépôt. Ne pas modifier des données de production
ni contourner les validations du MVP pour fabriquer un résultat à présenter
comme une opération réelle. Si aucun jeu historique contrôlé n’est disponible,
montrer la page et expliquer cette limite; un CSV vide ne démontre pas un
calcul d’heures rempli.

## Scénario à enregistrer

### 1. Présenter le périmètre

**À l’écran :** page d’accueil.

**À dire :** « Cette application permet au personnel de pointer avec un QR
personnel. L’opérateur enregistre l’entrée ou la sortie; les heures sont
calculées côté serveur dans le fuseau de Casablanca. La vérification faciale
est reportée et aucune donnée biométrique n’est utilisée. »

### 2. Montrer l’approbation d’un accès (facultatif)

1. Se connecter avec le compte administrateur technique de démonstration.
2. Ouvrir `/admin/access`, sélectionner le personnel en attente et attribuer
   seulement le rôle nécessaire au scénario.
3. Se déconnecter avant de se connecter au compte de démonstration concerné.

Ne pas afficher d’adresse réelle, de mot de passe temporaire ou d’information
de connexion dans l’enregistrement.

### 3. Créer et scanner le QR

1. Se connecter au compte Personnel puis ouvrir `/my-qr`.
2. Créer le QR de test et l’afficher temporairement sur un appareil privé.
3. Sur un autre appareil ou une session RH/Scolarité, ouvrir `/attendance`,
   choisir **Entrée**, démarrer le scanner et présenter le QR.
4. Vérifier le message de confirmation et l’horodatage Casablanca.
5. Répéter avec **Sortie** pour obtenir un intervalle complet. Les deux scans
   peuvent être rapprochés dans le temps pendant la vidéo; ne pas présenter
   cette durée comme une journée de travail représentative.

### 4. Montrer horaire, retard et alerte

1. Ouvrir `/admin/schedules` avec le compte RH/Scolarité.
2. Pour la date locale du jour, créer un créneau du personnel de démonstration
   qui a commencé depuis plus de dix minutes et qui n’est pas encore terminé.
   Si les scans viennent d’être faits, l’entrée doit être après le début du
   créneau et avant sa fin pour déclencher un retard.
3. Ouvrir `/admin/alerts` et vérifier l’alerte de retard. La page évalue les
   alertes lors de la consultation; marquer l’alerte comme traitée si souhaité.
4. Ouvrir `/admin/dashboard` pour montrer le statut de présence et le total
   journalier.

Les horaires et alertes sont en heure locale Casablanca. Ne pas affirmer qu’un
SMS ou un courriel a été envoyé : les alertes sont consultables dans
l’application uniquement.

### 5. Montrer une correction avec historique

1. Ouvrir `/admin/corrections`, choisir aujourd’hui et repérer un pointage de
   test.
2. Entrer une heure différente, antérieure à l’heure actuelle et située dans
   la même journée locale que le pointage original. Saisir un motif de
   correction explicite.
3. Enregistrer et vérifier l’heure effective ainsi que l’entrée d’historique.
4. Revenir au tableau de bord ou au résumé quotidien pour montrer que les
   calculs consomment l’heure effective corrigée; l’heure originale reste
   conservée.

### 6. Montrer l’export hebdomadaire

1. Se connecter avec le compte RH ou Finance puis ouvrir `/admin/exports`.
2. Sélectionner le lundi d’une semaine terminée pour laquelle le jeu de
   démonstration autorisé a été préparé.
3. Télécharger et ouvrir le CSV. Montrer les heures admissibles, les journées
   complètes retenues et les journées exclues pour revue.
4. Préciser que toute journée incomplète ou anomale est exclue en entier, que
   le calcul est informatif et que le fichier n’est pas archivé par
   l’application.

Le fichier CSV est encodé en UTF-8 avec BOM, séparé par des points-virgules et
utilise la virgule décimale. Vérifier que le fichier téléchargé est bien celui
de l’environnement de démonstration avant de le partager.

## Vérifications et précautions avant la vidéo

- Vérifier `/health`, puis tester la connexion des comptes synthétiques.
- Vérifier le statut des rôles et le fonctionnement des migrations dans le
  projet de démonstration.
- Utiliser un navigateur et des comptes dédiés; fermer les autres onglets
  pouvant révéler des informations privées.
- Ne pas montrer les variables `.env`, la clé service-role, la console réseau,
  les journaux contenant des identifiants, ou le tableau de bord Supabase avec
  des données de tiers.
- Après l’enregistrement, révoquer le QR de démonstration s’il a été capturé,
  réinitialiser ou désactiver les comptes temporaires, et supprimer les données
  de démonstration selon la procédure du projet isolé.
- Mentionner que la migration et l’intégration doivent être validées dans le
  projet Supabase retenu; les tests automatisés locaux seuls ne certifient pas
  une base réelle.
