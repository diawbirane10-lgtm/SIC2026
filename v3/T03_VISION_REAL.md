# FLOWTRUST-AFR — T03 Vision réelle

## Objectif
Remplacer le faux raisonnement « image nette = analyse AFR exploitable » par une chaîne de perception qui refuse d'abord les scènes hors domaine, puis seulement analyse un convoyeur reconnu.

## T03-A — Scene gate
Backbone bootstrap exécutable : DINOv2 ViT-L/14 with registers (~300 M paramètres), poids préentraînés Meta. La tête FLOWTRUST apprend `conveyor_applicable` vs `non_conveyor` sur des embeddings gelés.

### Données A0
- CoalAD : scènes réelles de flux charbon sur convoyeur, normal + objets étrangers ; archives officielles ModelScope référencées par le dépôt USAD.
- COCO val2017 : hard negatives généraux pour empêcher l'acceptation de scènes arbitraires. Les images ne sont pas redistribuées dans ce dépôt.

### Anti-fuite
Avant split, regroupement des quasi-doublons par pHash (distance de Hamming <= 4), puis split 70/15/15 par groupes. Le seuil d'acceptation convoyeur est choisi uniquement sur validation.

### Gates fermés A0
- false conveyor accept rate <= 2 % ;
- conveyor recall >= 90 % ;
- Brier <= 0.12 ;
- aucune intégration production sur un run CPU : le même protocole doit passer sur CUDA.

## T03-A1 — Durcissement domaine
Ajouter sans mélange train/test :
- BeltCrack (séquences industrielles de bande réelle) ;
- Iron Ore Conveyor (flux minerai + objets étrangers) ;
- VisA (industriel non-convoyeur, CC BY 4.0) ;
- Open Images, hard negatives généraux dont licences image vérifiées à l'échantillon utilisé.

## T03-B — Perception dans le ROI
Après validation du scene gate seulement : segmentation/suivi de la bande et de la matière, occupation, accumulation, déversement et objets étrangers. SAM 3.1 est le candidat principal de segmentation/track ; ses checkpoints nécessitent un accès accepté, donc il ne doit pas bloquer T03-A.

## T03-C — Anomalie et OOD
Mémoire de normalité sur embeddings denses DINO + détecteur d'anomalie/localisation inspiré des benchmarks CoalAD. Une scène hors domaine ou une image techniquement inutilisable doit produire `VISION_ABSTAIN`, jamais un score AFR positif.

## T03-D — Fusion T02
La vision n'envoie à T02 que :
- `scene_applicable` ;
- `scene_confidence` ;
- qualité caméra ;
- occupation/accumulation/spillage ;
- anomalie/localisation ;
- indicateur OOD.

Si `scene_applicable=false` ou confiance insuffisante, la fiabilité vision tombe à zéro dans T02. Aucune commande machine n'est autorisée.
