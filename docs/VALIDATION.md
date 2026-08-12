# FLOWTRUST-AFR — Carte de validation du MVP

## Positionnement de la preuve

Le MVP est **valide comme preuve de faisabilité numérique et démonstrateur de hackathon**. Il n'est pas encore validé comme système industriel SOCOCIM. La documentation sépare donc explicitement trois niveaux de preuve.

| Niveau | Source | Ce que cela démontre | Ce que cela ne démontre pas |
|---|---|---|---|
| 1 | Banc SIL synthétique reproductible | cohérence du pipeline, séparation des scénarios, comportement d'abstention, tests de robustesse | performance terrain ou économie réelle |
| 2 | Données physiques publiques hors domaine | capacité partielle de transfert de signatures dynamiques/visuelles | performance cimenterie/AFR |
| 3 | Données SOCOCIM | à réaliser pendant le pilote | aucun résultat site n'est revendiqué avant cette étape |

## Banc SIL principal

Le déploiement public v0.2.0 expose un banc synthétique de **4 800 exemples**, seed 2026, six classes connues :

- `normal`
- `weighing_drift`
- `hopper_bridging`
- `conveyor_blockage`
- `spillage`
- `unstable_feed`

Le septième scénario, `degraded_observability`, sert à vérifier l'abstention.

Les métriques synthétiques élevées sont attendues dans ce contexte de scénarios générés et **ne sont pas transposées au site**.

## Torture tests

La version publique vérifie notamment :

- bruit croissant ;
- données manquantes ;
- capteurs bloqués ;
- pertes de rafales ;
- désynchronisation détectable ;
- pics isolés ;
- flou, obscurité, déplacement de ROI, compression JPEG et poussière côté vision ;
- absence de toute violation du mode read-only.

Les critères d'acceptation publiés imposent l'abstention lorsque l'observabilité devient insuffisante et limitent les diagnostics erronés non-abstentionnistes sous perturbations fortes.

## Preuves auxiliaires réelles

### UCI Condition Monitoring of Hydraulic Systems

- Données physiques réelles hors domaine ciment/AFR.
- DOI : `10.24432/C5CW21`.
- Utilisation : preuve auxiliaire à faible poids pour la détection de dynamique instable.
- Le modèle public de transfert atteint environ 0,713 de balanced accuracy et 0,791 d'AUC ROC dans le déploiement v0.2.0.
- Ces valeurs ne prouvent ni un bourrage de convoyeur AFR ni une performance SOCOCIM.

### Iron Ore Conveyor

- Images réelles de convoyeur de minerai sur banc physique.
- DOI : `10.17632/s25x2bnshz.1`.
- Utilisation : prior visuel à faible autorité.
- Le déploiement v0.2.0 publie environ 0,938 de balanced accuracy et 0,992 d'AUC ROC sur ce jeu spécifique.
- Ces performances ne sont pas extrapolées à la poussière, à l'éclairage ni aux matériaux AFR de SOCOCIM.

## Critères de validation du futur pilote

Les KPI terrain prioritaires seront :

1. taux de faux diagnostics ;
2. taux d'abstention pertinente ;
3. délai de détection ;
4. accord avec diagnostic opérateur/maintenance ;
5. disponibilité et qualité des sources ;
6. capacité à localiser la cause probable ;
7. impact sur temps de diagnostic, pertes matière ou fonctionnement dégradé, uniquement après mesure réelle.

## Règle de communication

Aucune précision, économie, fiabilité, réduction d'arrêt ou probabilité de panne ne doit être revendiquée comme résultat SOCOCIM avant une campagne de validation industrielle documentée.
