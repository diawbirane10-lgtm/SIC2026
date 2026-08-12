# FLOWTRUST-AFR V2 — GPU Runbook

Ce runbook décrit l'ordre d'exécution de **Training 01 — 12 août 2026**. Il est volontairement séparé du MVP public : aucun résultat n'est promu vers l'HMI avant validation.

## 0. Matériel cible

### Minimum pratique pour commencer

- NVIDIA GPU 24 GiB VRAM ;
- 32–64 GiB RAM ;
- 100+ GiB de stockage temporaire si plusieurs datasets sont utilisés ;
- CUDA compatible avec la version PyTorch retenue.

### Recommandé

- 48 GiB VRAM pour DINOv3 ViT-L, Chronos-2 et Qwen3 en adaptation confortable ;
- 80 GiB ou multi-GPU pour expérimentations SAM 3.1 plus lourdes.

Le full fine-tuning de tous les paramètres n'est **pas** l'objectif de T01. On commence par backbone gelé / LoRA / adapters et on n'ouvre davantage de couches que si la validation le justifie.

## 1. Préparer l'environnement

```bash
git clone https://github.com/diawbirane10-lgtm/SIC2026.git
cd SIC2026
git checkout v2-model-rebuild
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-v2.txt
python v2/training/training_01_preflight.py
python v2/training/build_training01_manifest.py
```

Le preflight doit afficher CUDA disponible avant toute expérience >100 M paramètres.

## 2. Installer les modèles à licence séparée

### DINOv3

Lire/accepter la licence officielle DINOv3, puis installer/utiliser le dépôt officiel `facebookresearch/dinov3`. Ne pas copier les poids dans le dépôt SIC2026.

### SAM 3 / SAM 3.1

Lire/accepter la licence officielle SAM et suivre l'installation CUDA du dépôt `facebookresearch/sam3`. Conserver les poids hors Git et ne versionner que la configuration, les hashes et les métriques.

## 3. Données — ordre de priorité

### Download first / petits à moyens

1. Iron Ore Conveyor — vision directement pertinente ;
2. SSCC — convoyeur audio/vibration ;
3. UCI Hydraulic Systems — réel multicapteur ;
4. MetroPT-3 — 1.5 M lignes réelles d'exploitation ;
5. Industrial Maintenance Synthetic — 2.1 M lignes pour vocabulaire/RAG ;
6. MCC5-THU Motor — signaux moteur multimodaux.

### Stream/sample plutôt que télécharger intégralement

- Tennessee Eastman Extended : 132.96 GB ; échantillonner des runs complets avec séparation stricte par seed/mode.
- Open Images V7 : sélectionner uniquement des hard negatives utiles et dont la licence de l'image est vérifiée.

### Sources bloquées jusqu'à revue des conditions

`build_training01_manifest.py` les place automatiquement dans `blocked_sources`. Aucun fichier de ces sources ne doit entrer dans les poids finaux avant validation des conditions de réutilisation.

## 4. T01-A — Scene Gate DINOv3

**Question testée :** l'image montre-t-elle réellement une scène de convoyage industriel compatible avec une analyse FLOWTRUST ?

Classes de travail :

- `conveyor_applicable`
- `industrial_non_conveyor`
- `non_industrial`
- `uncertain`

Procédure :

1. split au niveau vidéo/source ;
2. extraire embeddings DINOv3 ViT-L ;
3. entraîner une tête linéaire/MLP légère ;
4. calibration température/isotonic sur validation ;
5. hard-negative test séparé ;
6. exporter confusion matrix, ECE et `false_conveyor_accept_rate`.

**Gate : <= 2 % de faux `conveyor_applicable` sur le test hard-negative fermé.**

Un mur, un visage, un bureau ou une route doivent conduire à `non_industrial` ou `uncertain`, jamais à un score AFR.

## 5. T01-B — Segmentation/anomalie vision

1. baseline SAM 3.1 sur belt/material/foreign object ;
2. mesurer stabilité des masques et IoU lorsque GT disponible ;
3. ajouter embeddings DINOv3 / anomalie locale ;
4. comparer avec baseline PatchCore/CoalAD ;
5. analyser manuellement toutes les erreurs à forte confiance.

Ne pas connecter cette sortie au dashboard avant revue de vidéos jamais vues.

## 6. T01-C — Convoyeur audio/vibration

1. convertir SSCC en manifest/shards compatibles avec Dasheng ;
2. commencer avec Dasheng-0.6B gelé + tête ;
3. split leave-speed/load/condition-out ;
4. comparer audio seul, vibration seule, fusion ;
5. si gain réel, ouvrir un adapter/LoRA ou couches supérieures ;
6. enregistrer macro-F1, balanced accuracy et calibration.

Une augmentation du nombre de paramètres entraînables n'est acceptée que si le test fermé s'améliore.

## 7. T01-D — Chronos-2 procédé / électrique

Chronos-2 est utilisé comme modèle de prévision probabiliste et de représentation temporelle, pas comme oracle de diagnostic.

1. construire DataFrame multivarié avec target(s) et covariables ;
2. baseline zero-shot ;
3. calculer quantiles et résidus ;
4. LoRA fine-tuning sur train uniquement ;
5. test sur seeds/modes/runs jamais vus ;
6. transformer résidus/embeddings en preuves pour la fusion.

Comparer obligatoirement à une baseline simple : persistance + seuil robuste / Random Forest sur features physiques.

## 8. T01-E — Copilote opérateur Qwen3

Le LLM n'a jamais le droit d'inventer les mesures. Son entrée est un JSON structuré issu des outils :

```json
{
  "diagnostic_engine": "conveyor_blockage",
  "confidence": 0.91,
  "evidence": {
    "speed_ratio": 0.46,
    "motor_current_delta_pct": 38,
    "vibration_mm_s": 6.2,
    "vision_accumulation": true
  },
  "available_tools": ["sensor_test", "camera_test", "drive_test", "coherence_test"]
}
```

Sorties attendues :

- explication en français clair ;
- test suivant recommandé ;
- étapes de vérification ordonnées ;
- rappel read-only / opérateur décisionnaire.

Fine-tuning initial : Qwen3-0.6B + LoRA/SFT. Évaluer Qwen3-1.7B comme teacher/candidat si la mémoire GPU le permet.

**Gates :** `unsafe_command_rate = 0` et `numeric_hallucination_rate <= 1 %` sur le jeu fermé.

## 9. Fusion finale

La fusion n'est entraînée qu'après obtention de sorties OOF/held-out des spécialistes. Ne jamais entraîner la fusion sur les prédictions in-sample des sous-modèles.

Entrées :

- probabilité/OOD vision ;
- résidus temporels Chronos ;
- scores moteur/convoyeur ;
- qualité de chaque source ;
- cohérence temporelle.

Sorties : diagnostic, confiance calibrée, abstention, preuves.

Métriques : Brier, ECE, macro-F1, erreur non-abstentionniste, selective risk / coverage.

## 10. Promotion vers le MVP

Une expérience est promue uniquement si :

1. son split fermé est documenté ;
2. ses données/licences sont dans `data_provenance.json` ;
3. ses poids ont un hash ;
4. ses métriques sont enregistrées ;
5. ses cas d'échec à forte confiance sont examinés ;
6. son gate est passé.

Le premier objectif n'est donc pas « faire tourner un gros modèle », mais **obtenir une brique qui gagne un test fermé et dont on sait quand ne pas lui faire confiance**.
