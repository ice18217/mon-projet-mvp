# MVP (Minimum Viable Product) — Projet Pointage EIGSI

## 1. Classement des fonctionnalités
- **Indispensable** :
  1. Pointage par QR code
  2. Horodatage/calcul d'heures
  3. Gestion des utilisateurs (connexion, rôles)
  4. Détection d'absence/alertes simples
  5. Tableau de bord de présence
- **Utile** :
  - Vérification faciale IA
  - Correction d'heures par RH
  - Export paie
- **Plus tard** :
  - Gestion avancée des missions
  - Multi-campus
  - Historique complet des exports

## 2. Fonctionnalités indispensables retenues
1. Pointage par QR code
2. Horodatage/calcul d'heures
3. Gestion des utilisateurs (connexion, rôles)
4. Détection d'absence/alertes simples
5. Tableau de bord de présence

## 3. Découpage en petites étapes
1. **Gestion des utilisateurs**
   - Création d’un compte utilisateur (email, mot de passe, rôle)
   - Connexion/déconnexion
   - Attribution d’un rôle (Personnel, RH)
2. **Pointage par QR code**
   - Génération d’un QR code unique par utilisateur
   - Scan du QR code pour enregistrer la présence
3. **Horodatage/calcul d'heures**
   - Enregistrement de la date et l’heure du pointage
   - Calcul automatique du temps de présence journalier
4. **Détection d'absence/alertes**
   - Comparaison des pointages avec l’emploi du temps
   - Génération d’une alerte simple si absence ou retard
5. **Tableau de bord de présence**
   - Affichage des présences/absences par jour pour chaque utilisateur
   - Visualisation simple pour RH

## 4. Stack technique recommandée
- **Frontend** : Next.js (React)
- **Backend** : Supabase (API REST et authentification intégrée)
- **Base de données** : PostgreSQL (géré par Supabase)

*Cette stack est idéale pour un débutant : pas de backend à coder, documentation abondante, déploiement facile.*
