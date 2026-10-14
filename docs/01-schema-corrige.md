# Schéma de base de données corrigé

## Tables principales

- **PERSONNEL** (id_personnel [PK], nom, prénom, email, type [permanent/vacataire], ...)
- **EMBEDDING_FACIAL** (id [PK], id_personnel [FK], vecteur, date_ajout)
- **POINTAGE** (id_pointage [PK], id_personnel [FK], date_heure, type_pointage [entrée/sortie], mode [QR, facial, badge], validé_par_RH [bool], correction_id [FK], ...)
- **CORRECTION_POINTAGE** (id_correction [PK], id_pointage [FK], id_rh [FK], date_correction, motif, ancienne_valeur, nouvelle_valeur)
- **EMPLOI_DU_TEMPS** (id_edt [PK], id_personnel [FK], date, heure_debut, heure_fin, type_cours/mission)
- **DECLARATION_MISSION** (id_mission [PK], id_personnel [FK], date_debut, date_fin, description)
- **ALERTE_ABSENCE** (id_alerte [PK], id_personnel [FK], date, type [absence/retard], statut [envoyée, traitée])
- **ACCES_UTILISATEUR** (id_acces [PK], id_personnel [FK], role [RH, Finance, Admin, Personnel], date_debut, date_fin)
- **EXPORT_PAIE** (id_export [PK], periode, date_export, id_personnel [FK], montant, statut)
- **CAMPUS** (id_campus [PK], nom)
- **PERSONNEL_CAMPUS** (id_personnel [FK], id_campus [FK])

## Explications
- [PK] = clé primaire, [FK] = clé étrangère
- Les relations sont explicites (ex : POINTAGE lié à PERSONNEL, corrections tracées, rôles gérés, multi-campus possible)
- Les fonctionnalités du backlog sont toutes couvertes par ce schéma

N’hésite pas à demander un schéma visuel ou des exemples de requêtes !