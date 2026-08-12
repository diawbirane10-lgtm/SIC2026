# FLOWTRUST-AFR V2 — Sources de données ciblées pour Training 01

**Recherche effectuée le 12 août 2026.**

Cette sélection n'est pas une collecte web aveugle. Elle privilégie :

1. des données de convoyeurs réels ou de bancs physiques ;
2. des signaux électriques, vibration/audio et procédé réellement instrumentés ;
3. des licences explicites ;
4. des données permettant des splits par run/vidéo afin d'éviter la fuite de données ;
5. des hard negatives suffisamment différents pour apprendre l'abstention.

## Vision — convoyeur / matière

### P0 — Iron Ore Conveyor

- DOI `10.17632/s25x2bnshz.1`
- Licence CC BY 4.0
- Vidéo haute vitesse 120 fps, 1280×720, convoyeur de minerai, fonctionnement normal et objets étrangers.
- Sous-ensembles frames, normal/anormal et annotations de démonstration.
- Usage : scene gate DINOv3, anomalie visuelle, ROI, hard positives convoyeur.

### P0 — Construction & Demolition Waste Object Detection

- DOI `10.17632/24d45pf8wm.2`
- Licence CC BY 4.0
- 550 images RGB, environ 6 600 objets béton/brique/tuile ; convoyeur d'une plateforme de tri grandeur réelle.
- Deux tests séparés : objets espacés et cas fortement empilés/adhérents.
- Usage : robustesse aux occlusions et diversité de matériaux sur bande.

### P0 — Rock/Transport Conveyor 2026

- DOI `10.17632/v9grvgsrh9.1`
- Licence CC BY 4.0
- Sous-ensemble transport capté par caméra industrielle Dalsa face à un convoyeur de 400 mm ; segmentation manuelle.
- Usage : apparence rocheuse/minérale et généralisation géométrique.

### P0 sous revue — CoalAD

- Code officiel : `xjpp2016/USAD`
- Charbon/gangue, poussière, usure, occultations et objets étrangers à faible contraste.
- Usage technique extrêmement pertinent pour anomalie locale, mais la redistribution de poids dérivés attend la validation des conditions de réutilisation du dataset.

### P1 — CUMT-BelT

- Dépôt/lab : `CUMT-AIPR-Lab/CUMT-AIPR-Lab`
- Dataset publié pour la classification d'objets étrangers sur convoyeur de charbon : grosses gangues, boulons/autres corps étrangers pouvant rayer/déchirer la bande ou bloquer le point de décharge.
- Licence des données à confirmer avant inclusion dans les poids distribués.

### P1 — BeltCrack

- Dépôt : `UESTC-nnLab/BeltCrack`
- Séquences réelles de fissures de bandes industrielles.
- Usage : santé de bande, distincte de la détection du flux matière.

### P2 — diversité convoyeur sous licences ouvertes

- DeepSort-3C, DOI `10.17632/gzmtph8zs2.1`, CC BY 4.0.
- CocoaBeansQCV, DOI `10.17632/sr279sf4hs.1`, CC BY 4.0.
- Postharvest Bok Choy Conveyor, DOI `10.17632/84z7hs67fm.1`, CC BY 4.0.
- Chili conveyor/empty-scene, DOI `10.17632/vrby4t2w57.1`, CC BY 4.0.

Ces jeux ne portent pas sur l'AFR mais apportent matière, mouvement, bande vide, objets et textures. Ils ne doivent pas dominer l'adaptation AFR.

## Hard negatives vision

### Open Images V7

Le foundation model DINOv3 a déjà hérité d'un pré-entraînement massif. Pour FLOWTRUST, Open Images sert surtout à créer un test/jeu de hard negatives : murs, visages, bureaux, routes, animaux, intérieurs, véhicules et machines non-convoyeurs.

Règle : conserver l'ID d'image, l'auteur et la licence ; rejeter les images dont la licence individuelle n'est pas vérifiable.

L'objectif n'est pas de télécharger des millions d'images au hasard mais d'obtenir un jeu négatif difficile et traçable.

## Audio / vibration convoyeur

### P0 — SSCC 2026

- Single-Speed Chain Conveyor benchmark.
- 3 canaux audio + 4 canaux vibration.
- Normal + dry lubrication + guide-rail misalignment + chain slack + screw drop/obstruction.
- Plusieurs vitesses/charges et bruit d'usine.
- Usage : Dasheng-0.6B côté audio, MOMENT/encodeurs temporels côté vibration, puis fusion.

### P0 sous revue — ToyADMOS conveyor subset

- Dépôt `YumaKoizumi/ToyADMOS-dataset`, archive Zenodo 3351307.
- Environ 540 h de fonctionnement normal et >12 000 anomalies sur l'ensemble ; tâche explicitement dédiée au toy conveyor.
- Corpus complet >440 GB : ne télécharger que le sous-ensemble convoyeur.
- Le fichier de licence du dataset doit être revu avant entraînement distribué.

### P1 — IMAD-DS

- Microphone 16 kHz + accéléromètre/gyroscope 6.7 kHz.
- Domaines source/cible pour tester le changement de domaine.
- Bon benchmark de robustesse multimodale, licence du record à confirmer avant intégration training.

## Moteur / transmission

### P0 — MCC5-THU Motor

- DOI `10.17632/6s3dggj9mw.1`, CC BY 4.0.
- vibration triaxiale, courants triphasés, couple et key-phase synchronisés.
- défauts simples/composés et fonctionnement stationnaire/transitoire.

### P1 — Belt-drive vibration

- DOI `10.17632/jf8v2ndydr.1`, CC BY 4.0.
- 459 runs ; 17 vitesses ; 3 prétensions ; bande saine, bande défectueuse et déséquilibre.

### P1 — Variable-speed bearing / multimodal rotating machine

- DOI `10.17632/x3vhp8t6hg.1`, CC BY 4.0, 5.15 GB, vibration + courant + vitesse variable.
- DOI `10.17632/ztmf3m7h5x.4`, CC BY 4.0, vibration + acoustique + température + courant + charge.

## Procédé / séries temporelles

### P0 — Extended Tennessee Eastman

- 132.96 GB, CC0.
- 28 défauts, 6 modes, 500 répétitions stochastiques par défaut, transitions et changements de consigne.
- Usage : Chronos-2/MOMENT et tests de généralisation par seed/mode.
- Ne pas télécharger les 133 GB d'un coup : commencer avec des runs complets stratifiés tout en réservant des seeds/modes fermés.

### P0 — UCI Hydraulic Systems

- DOI `10.24432/C5CW21`, CC BY 4.0.
- 2 205 cycles avec pression, débit, température, puissance moteur et vibration.
- Usage : transfert réel multicapteur et validation OOD.

### P0-next — MetroPT-3

- DOI `10.24432/C5VW3R`, CC BY 4.0.
- 1 516 948 lignes opérationnelles réelles, 15 variables incluant pression, température, courant moteur et états de vannes.
- Usage : test temporel externe pour maintenance prédictive et détection d'anomalies.

## Assistant opérateur / RAG

### P0 — IBM AssetOpsBench

- Dépôt Apache-2.0.
- Environnement d'agents sur actifs industriels avec IoT, modes de défaillance, FMEA, ordres de travail, outils de prévision/anomalie et analyse vibration.
- Usage : comportement outils → preuves → explication, sans copier les scénarios comme vérité SOCOCIM.

### P0 — Industrial Maintenance Synthetic

- 2 097 558 lignes, Apache-2.0.
- ~1 M tags capteurs + ~1 M ordres de maintenance ; 37 familles d'équipements dont belt conveyor, motor, gearbox et dosing pump.
- Usage : vocabulaire maintenance, RAG, tests de qualité de données et entraînement de sélection d'outils.
- Données synthétiques : jamais utilisées comme autorité de procédure sécurité.

## Modèles foundation associés

- DINOv3 ViT-L/16 : 300 M paramètres, pré-entraînement LVD-1689M.
- SAM 3.1 : ~848 M paramètres, segmentation/suivi.
- Dasheng-0.6B : 600 M paramètres, pré-entraînement 272k heures audio.
- MOMENT-1-large : **341 231 104 paramètres encoder**, reconstruction/anomalie/imputation/embedding.
- Chronos-2 : 120 M paramètres, prévision multivariée/covariables + LoRA.
- TimesFM 2.5 : 200 M paramètres, benchmark temporel indépendant + LoRA disponible.
- Qwen3-0.6B : 600 M paramètres, copilote opérateur avec LoRA + RAG + outils structurés.

## Règle de crédibilité

Le volume n'est jamais une métrique de qualité en soi. Les données sont séparées par **run, vidéo, machine ou seed**, pas par frame/fenêtre voisine. Une source n'entre dans les poids que si sa provenance et sa licence sont documentées. Les modèles V2 ne sont promus dans l'interface qu'après réussite d'un test fermé et enregistrement des cas d'échec à forte confiance.
