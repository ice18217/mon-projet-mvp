# Résumé du projet

## 1. Résumé de l'application
L'application est un système de pointage et de gestion de présence/absence pour le personnel de l’EIGSI Casablanca. Elle propose :
- Pointage par QR code et vérification faciale IA
- Horodatage et calcul automatique des heures
- Détection d’absence/retard avec alertes automatiques
- Correction d’heures par RH
- Tableau de bord et export paie
- Interface web d’administration (Next.js/TypeScript + Supabase)
- Gestion multi-rôles (Personnel, RH/Scolarité, Finance, Admin technique)
- Sécurité et gestion des accès
- Suivi des missions et emplois du temps
- Design moderne adapté à l’école

## 2. Inventaire des fichiers trouvés
- S1_Rapport_Pointage.pdf (rapport, contenu non lisible directement)
- S2_Rapport_Pointage.pdf (rapport, contenu non lisible directement)
- MAQUETTEExp2.png (wireframe page pointage)
- MAQUETTEExp3.png (wireframe page pointage campus La Rochelle)
- MAQUETTEExp4.png (wireframe page connexion)
- docs/00-resume-projet.md (ce résumé)

### Ce qui manque :
- Schéma de la base de données (structure décrite ci-dessous, pas de schéma visuel)
- Product backlog détaillé (liste fournie ci-dessus, pas de fichier dédié)
- Fichiers de description fonctionnelle (README, .txt, .csv, .xlsx)

## 3. Incohérences repérées
- Les fonctionnalités du backlog sont cohérentes avec les wireframes (QR, visage, alertes, export paie).
- La structure des tables (PERSONNEL, PERMANENT, VACATAIRE, EMBEDDING_FACIAL, POINTAGE, EMPLOI_DU_TEMPS, DECLARATION_MISSION, ACCES_UTILISATEUR, EXPORT_PAIE) couvre les besoins, mais il manque un schéma visuel pour vérifier les liens exacts.
- Les rôles sont bien définis, mais la gestion fine des droits d’accès n’est pas détaillée.

## 4. Questions pour avancer
1. Peux-tu fournir un schéma visuel (image) de la base de données ?
2. Souhaites-tu détailler les droits de chaque rôle (qui fait quoi précisément) ?
3. Faut-il prévoir une gestion multi-campus (Casablanca/La Rochelle) dans la BDD ?
4. Y a-t-il des besoins spécifiques pour l’export paie (format, fréquence) ?
5. L’interface RH doit-elle permettre la validation manuelle des corrections d’heures ?
