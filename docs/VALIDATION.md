# FLOWTRUST-AFR — Carte de validation du MVP

## Positionnement de la preuve

FLOWTRUST-AFR v0.3.1 est un **démonstrateur fonctionnel de faisabilité numérique et d'aide au diagnostic**. La preuve est organisée en trois étages afin de distinguer clairement ce qui est déjà démontré de ce qui sera calibré pendant le pilote industriel.

| Niveau | Source | Fonction démontrée |
|---|---|---|
| 1 | Banc SIL synthétique reproductible | pipeline, diagnostics de scénarios, fusion, abstention, tests de robustesse |
| 2 | Données physiques publiques hors domaine | transfert partiel de signatures dynamiques/visuelles et comparaison de modèles |
| 3 | Données SOCOCIM | calibration finale, KPI terrain et validation du pilote |

## Banc SIL principal

Le banc reproductible contient **4 800 exemples**, seed 2026, répartis entre six états : `normal`, `weighing_drift`, `hopper_bridging`, `conveyor_blockage`, `spillage` et `unstable_feed`. Des perturbations complémentaires vérifient l'observabilité insuffisante, les pertes de sources et les contradictions volontaires.

Les métriques de ce banc sont utilisées pour valider le comportement logiciel et comparer les architectures ; elles ne sont pas transposées comme métriques SOCOCIM.

## v0.3.1 — T02 edge

Le déploiement public actif expose :

- `version = 0.3.1` ;
- `fusion_version = t02-edge-v1` ;
- `model_id = flowtrust-linear-prior-v1` ;
- `mode = advisory_read_only` ;
- `automatic_control_allowed = false`.

T02 sépare trois avis :

- **procédé** : débit, niveau/dérivée de trémie, bilan matière et variabilité de flux ;
- **électromécanique** : vitesse réelle/consigne, courant, charge, couple, vibration et variabilité ;
- **vision** : proxy de flux, accumulation, déversement et disponibilité/qualité caméra.

Chaque canal reçoit une fiabilité. Une modalité sous `0.35` est exclue. **Deux modalités indépendantes au minimum** doivent rester actives pour qu'un diagnostic puisse être émis.

La fusion edge donne **78 %** du poids aux évidences multimodales et **22 %** au prior statistique distillé. Le prior ne peut pas contourner un gate d'observabilité, de données manquantes, de désynchronisation ou de contradiction.

## Prior statistique distillé

`flowtrust-linear-prior-v1` est un classifieur logistique entraîné hors ligne sur le banc SIL puis exporté en coefficients purs afin de conserver un runtime edge léger et traçable.

Entraînement 12/08/2026 :

- 4 800 exemples SIL ;
- seed 2026 ;
- six classes ;
- balanced accuracy sur split fermé : **0,99917** ;
- log loss multiclasses : **0,00405**.

Une seule erreur a été observée sur ce split fermé : un cas `weighing_drift` classé `normal`. Le prior n'est pas utilisé seul : T02 confronte ensuite ses probabilités aux modalités physiques indépendantes.

## Gates d'abstention

Le runtime renvoie `unknown` notamment lorsque :

- plus de 20 % des caractéristiques sont absentes ou non finies ;
- moins de deux modalités restent suffisamment fiables ;
- le capteur de pesage est identifié comme fortement suspect ;
- les principales sources deviennent simultanément désynchronisées/de mauvaise qualité ;
- le point est très éloigné de l'enveloppe SIL sur les variables cœur ;
- le soutien fusionné ou la marge entre hypothèses est insuffisant ;
- les modalités fiables portent des explications incompatibles sans consensus suffisant.

Toutes les sorties conservent `automatic_control_allowed=false`.

## Torture gates et CI

Les suites `tests/test_fusion.py` et `tests/test_api_t02.py` vérifient notamment :

- décisions propres avec traçabilité des modalités ;
- perte de vision avec poursuite possible si procédé + électromécanique restent fiables ;
- perte de plusieurs modalités avec abstention obligatoire ;
- contradictions volontaires ;
- données manquantes/non finies ;
- capteur bloqué / faible qualité ;
- contrat strict read-only.

La CI vérifie également la syntaxe de l'HMI, le runtime Node réellement utilisé sur Vercel, reconstruit le snapshot ML puis exécute les tests Python/API.

## Caméra dans v0.3.1

La caméra de l'appareil peut être activée après autorisation explicite du navigateur. Le test actuellement publié mesure **uniquement la qualité technique de l'image** : luminosité, contraste et netteté.

Ce score n'est pas présenté comme une reconnaissance de convoyeur ni comme une détection de défaut AFR. Le scene-gate industriel V2 sera activé seulement après validation de son propre test hors-domaine.

## Sélection des modèles V2

La branche `v2-model-rebuild` impose une comparaison fermée avant intégration. Les modèles foundation ne sont conservés que lorsqu'ils battent une baseline adaptée.

Premier cycle :

- MOMENT initial : inférieur à la baseline capteur, donc non retenu ;
- challenger capteurs T01-F1 : macro-F1 ≈ **0,884**, progression majeure mais sous le gate de 0,90 ;
- Chronos / forecasting : non retenu pour cette fonction lorsque la persistance a obtenu de meilleurs résultats.

Cette sélection protège le MVP contre l'ajout de modèles volumineux sans gain démontré.

## Preuves auxiliaires physiques

### UCI Condition Monitoring of Hydraulic Systems

- DOI : `10.24432/C5CW21` ;
- données physiques réelles hors domaine ciment/AFR ;
- utilisées comme banc auxiliaire de dynamique et d'intégrité des signaux.

### Iron Ore Conveyor

- DOI : `10.17632/s25x2bnshz.1` ;
- images réelles de convoyeur de minerai sur banc physique ;
- utilisées comme preuve auxiliaire vision, sans extrapolation directe au matériau AFR de SOCOCIM.

## KPI du futur pilote

Les KPI prioritaires seront le taux de faux diagnostics, l'abstention pertinente, le délai de détection, l'accord avec opérateur/maintenance, la disponibilité des sources, la localisation de la cause probable et l'impact mesuré sur le temps de diagnostic ou les pertes matière.

## Règle de communication

Les résultats SIL et hors domaine sont présentés comme **preuves de faisabilité et de robustesse du MVP**. Les performances spécifiques au site et les gains économiques seront quantifiés pendant le pilote à partir de données industrielles réelles.
