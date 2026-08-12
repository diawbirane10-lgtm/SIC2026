# FLOWTRUST-AFR V2 — Rebuild complet du socle IA

## Principe

La V2 ne se limite pas à la vision. Toutes les composantes apprenantes sont réévaluées, réentraînées ou remplacées par un modèle préentraîné plus adapté, puis revalidées ensemble. Les fonctions non apprenantes (HMI, alarmes, tests guidés, règles de sécurité, orchestration) ne sont pas « entraînées » : elles sont restructurées, testées et reliées aux modèles réels.

## Architecture cible

### 1. Vision industrielle
- Backbone : DINOv3 distillé / adapté au domaine convoyage.
- Segmentation / tracking : SAM 3.1.
- Têtes spécialisées : présence de convoyeur, occupation matière, accumulation, déversement, objet étranger, scène hors domaine.
- Données : jeux industriels publics + images/vidéos de convoyeurs + augmentations poussière, éclairage, flou, occlusion, vibration, cadrage.
- Sortie : features + masques + score OOD + niveau de qualité caméra.

### 2. Séries temporelles procédé / électromécaniques
- Foundation model candidat : Chronos-2 (120M) pour multivarié/covariables.
- Ensemble de référence : Random Forest / gradient boosting + règles physiques + résidus de prévision.
- Signaux : débit, niveau, vitesse, courant, couple, vibration, consigne, qualité de données.
- Tâches : prévision courte, détection de rupture, dérive, désynchronisation et classification d'état.

### 3. Fusion multimodale et confiance
- Entrées : vision + procédé + électromécanique + qualité de source.
- Modèle : ensemble calibré + détecteur hors domaine + règles de cohérence physique.
- Objectif principal : minimiser les erreurs non-abstentionnistes ; l'abstention est une sortie valide.

### 4. Assistant de raisonnement opérateur
- Modèle de base : LLM open-weight de taille déployable, candidat Qwen3.5/3.6.
- Fine-tuning : SFT/LoRA sur cas de diagnostic industriel, procédures, arbres de causes, explications et séquences de vérification.
- RAG : documentation technique, procédures de site, manuel équipement, alarmes, historiques et sorties du moteur de diagnostic.
- Garde-fou : le LLM ne crée pas le diagnostic primaire et n'envoie aucune commande ; il reformule les preuves, explique, propose des tests et ordonne les vérifications autorisées.

### 5. Tests guidés opérateur
Les tests deviennent de vraies fonctions analytiques appelant les modèles correspondants :
- santé capteur ;
- caméra/CV ;
- entraînement convoyeur ;
- cohérence multimodale ;
- observabilité ;
- replay / injection de défaut.

Chaque test renvoie : résultat, confiance, preuves, contradiction éventuelle, prochaine vérification suggérée et statut d'abstention.

## Règle sur les paramètres

Le nombre de paramètres ne sera jamais un KPI en lui-même. On sélectionne le plus petit modèle atteignant les critères de validation. On peut fine-tuner des modèles de 100M, 1B ou plusieurs milliards de paramètres, mais on n'additionne pas « 100M de paramètres par jour ». Ce qui augmente quotidiennement est le volume de données utiles, la couverture des scénarios, les étapes d'entraînement, les augmentations et les tests adversariaux.

## Calendrier 12–20 août 2026

### 12–13 août — Audit et données
- figer V1 ;
- inventorier toutes les fonctions ;
- collecter/curer datasets publics ;
- définir labels, splits sans fuite et métriques ;
- préparer pipelines reproductibles.

### 14–15 août — Vision V2
- DINOv3 embeddings ;
- SAM 3.1 segmentation/tracking ;
- têtes convoyeur/anomalie/OOD ;
- torture tests caméra.

### 16 août — Procédé / électromécanique V2
- Chronos-2 + modèles de référence ;
- forecast residuals ;
- détection dérive/rupture ;
- classification et calibration.

### 17 août — Fusion V2
- fusion multimodale ;
- calibration des probabilités ;
- observabilité et abstention ;
- tests de contradiction entre sources.

### 18 août — Assistant opérateur V2
- corpus de procédures et scénarios ;
- fine-tuning LoRA/SFT si compute disponible ;
- RAG ;
- tests de suggestions sûres et explicables.

### 19 août — Intégration HMI
- brancher l'interface temps réel aux vraies sorties modèles ;
- tests guidés ;
- injection de défaut ;
- alarmes et replay.

### 20 août — Gel candidat
- benchmark final ;
- tests smartphone/tablette ;
- revue des revendications ;
- merge V2 dans main uniquement si les critères sont satisfaits ;
- note conceptuelle finale.

## Critères de merge vers main

1. Une scène non industrielle doit être rejetée par la vision.
2. Une caméra mauvaise doit faire baisser l'autorité de la branche vision.
3. Les défauts injectés doivent modifier réellement les entrées analysées, pas seulement le texte de l'interface.
4. Les diagnostics affichés doivent provenir du moteur backend ou d'un modèle local documenté.
5. Les probabilités doivent être calibrées sur un jeu de validation séparé.
6. Les cas hors domaine / données insuffisantes doivent déclencher l'abstention.
7. L'assistant opérateur ne doit jamais inventer une mesure ni proposer une commande automatique.
8. Les métriques SIL et publiques doivent être clairement séparées des futures métriques SOCOCIM.
