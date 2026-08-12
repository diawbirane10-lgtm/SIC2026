# FLOWTRUST-AFR — Carte de validation du MVP

## Positionnement de la preuve

Le MVP est **valide comme preuve de faisabilité numérique et démonstrateur de hackathon**. Il n'est pas encore validé comme système industriel SOCOCIM. La documentation sépare donc explicitement trois niveaux de preuve.

| Niveau | Source | Ce que cela démontre | Ce que cela ne démontre pas |
|---|---|---|---|
| 1 | Banc SIL synthétique reproductible | cohérence du pipeline, séparation des scénarios, comportement d'abstention, tests de robustesse | performance terrain ou économie réelle |
| 2 | Données physiques publiques hors domaine | capacité partielle de transfert de signatures dynamiques/visuelles | performance cimenterie/AFR |
| 3 | Données SOCOCIM | à réaliser pendant le pilote | aucun résultat site n'est revendiqué avant cette étape |

## Banc SIL principal

Le snapshot public utilise un banc synthétique de **4 800 exemples**, seed 2026, six classes connues :

- `normal`
- `weighing_drift`
- `hopper_bridging`
- `conveyor_blockage`
- `spillage`
- `unstable_feed`

Le septième scénario, `degraded_observability`, sert à vérifier l'abstention.

Les métriques synthétiques élevées sont attendues dans ce contexte de scénarios générés et **ne sont pas transposées au site**.

## T02 — Fusion multimodale de confiance et abstention

La version logicielle `0.3.0` ajoute le bloc `t02-v1`. La décision n'est plus le simple résultat du Random Forest : elle combine trois canaux interprétables et le modèle statistique n'agit que comme **prior de soutien**.

Les trois canaux sont :

- **procédé** : débit, niveau et dérive de trémie, résidu de bilan matière, variabilité du débit ;
- **électromécanique** : vitesse réelle/consigne, courant, charge, couple, vibration et variabilité du courant ;
- **vision** : proxy de flux, accumulation, déversement et qualité caméra.

Chaque canal reçoit une fiabilité calculée à partir de la qualité des signaux et de la complétude de ses variables. Une modalité de fiabilité inférieure à `0.35` est exclue de la fusion. **Au moins deux modalités indépendantes doivent rester actives** ; une confiance élevée du modèle statistique ne peut pas contourner cette règle.

Lorsque le Random Forest est disponible, la fusion conserve une majorité de poids aux évidences interprétables (`58 %`) et limite le prior statistique à `42 %`. Ces coefficients sont des paramètres de prototype à recalibrer sur données site ; ils ne constituent pas une optimisation SOCOCIM.

La sortie passe en `unknown` dès qu'un des mécanismes de sûreté suivants est déclenché : soutien insuffisant des modalités pertinentes, contradiction forte entre anomalies portées par des sources fiables, contradiction forte entre modèle et évidences physiques, désaccord débit/vision élevé sans mécanisme explicatif cohérent, confiance fusionnée insuffisante ou marge trop faible entre les deux meilleurs candidats.

Le retour API conserve pour chaque diagnostic la fiabilité, le vote et la force de chaque modalité, la marge, le niveau d'accord et les scores fusionnés. Cette traçabilité est destinée à l'HMI opérateur et au journal d'audit ; elle ne donne aucun droit de commande au système.

### Torture gates T02 exécutés en CI

La suite `tests/test_fusion.py`, exécutée par GitHub Actions sur `main`, vérifie notamment :

- 384 tirages synthétiques propres avec prior modèle aligné : **zéro diagnostic erroné parmi les décisions non abstentionnistes** et couverture minimale imposée de 70 % ;
- perte complète de la vision sur un cas de bourrage : la décision peut rester disponible si procédé + électromécanique restent cohérents ;
- perte de deux modalités : abstention obligatoire, même avec un modèle statistique très confiant ;
- conflit modèle/évidences physiques : abstention obligatoire ;
- deux anomalies incompatibles portées par des modalités indépendantes : abstention obligatoire ;
- désaccord débit mesuré / vision élevé et inexpliqué : abstention obligatoire ;
- présence dans la sortie des éléments nécessaires à la traçabilité HMI/audit.

Le workflow `FLOWTRUST-AFR CI` correspondant au commit d'intégration T02 a terminé avec succès : tests Python puis reconstruction du snapshot ML.

## Torture tests généraux

La version publique vérifie également :

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
- Le modèle public de transfert atteint environ 0,713 de balanced accuracy et 0,791 d'AUC ROC dans le déploiement de référence.
- Ces valeurs ne prouvent ni un bourrage de convoyeur AFR ni une performance SOCOCIM.

### Iron Ore Conveyor

- Images réelles de convoyeur de minerai sur banc physique.
- DOI : `10.17632/s25x2bnshz.1`.
- Utilisation : prior visuel à faible autorité.
- Le déploiement de référence publie environ 0,938 de balanced accuracy et 0,992 d'AUC ROC sur ce jeu spécifique.
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
