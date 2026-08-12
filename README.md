# FLOWTRUST-AFR — SIC2026

**FLOWTRUST-AFR** est un assistant de diagnostic industriel multimodal pour la chaîne d'alimentation en **Alternative Fuels and Raw Materials (AFR)** d'une cimenterie. Le MVP fonctionne exclusivement en **mode conseil / lecture seule** : aucune commande automatique n'est autorisée et la décision finale reste à l'opérateur.

## Démonstration publique

**Application :** https://flowtrust-afr-sic2026.vercel.app  
**API santé :** https://flowtrust-afr-sic2026.vercel.app/api/health

État vérifié du déploiement public : `version 0.2.0`, `advisory_read_only`, `automatic_control_allowed=false`, modèle principal `afr-rf-diagnostic-v1`.

## Documentation rapide

- [Architecture et logique de confiance](docs/ARCHITECTURE.md)
- [Carte de validation et limites scientifiques](docs/VALIDATION.md)
- [Proposition de pilote SOCOCIM](docs/PILOT_SOCOCIM.md)

## Ce que le MVP surveille

La fusion exploite 25 caractéristiques couvrant notamment :

- commande doseur et vitesse convoyeur ;
- vitesse réelle et ratio de vitesse ;
- débit massique mesuré et proxy visuel ;
- désaccord entre débit pesé et estimation visuelle ;
- niveau et dérivée de niveau de trémie ;
- résidu de bilan matière ;
- courant, charge et couple moteur ;
- vibration ;
- variabilité temporelle du débit et du courant ;
- accumulation et déversement vus par caméra ;
- qualité des signaux instrumentation et caméra.

## Diagnostics démontrés

Le replay public contient sept situations :

1. fonctionnement nominal ;
2. dérive du système de pesage ;
3. pontage de trémie ;
4. bourrage convoyeur ;
5. déversement de matière ;
6. alimentation instable ;
7. observabilité insuffisante, avec abstention obligatoire.

## Modèles actifs dans le déploiement v0.2.0

- `afr-physics-rules-v1` — règles de cohérence physique ;
- `afr-rf-diagnostic-v1` — classifieur diagnostic ;
- `afr-isolation-known-domain-v1` — détection hors domaine / abstention ;
- `opencv-fixed-camera-occupancy-v1` — baseline vision caméra fixe ;
- `public-iron-ore-conveyor-extra-trees-v1` — prior visuel issu d'un convoyeur de minerai public ;
- `uci-real-flow-dynamics-rf-v1` — preuve auxiliaire de transfert sur dynamique réelle hors domaine AFR.

Deux adaptateurs vision restent volontairement non activés dans le MVP (`segformer-onnx-industrial-adapter-v1` et `visual-changenet-onnx-adapter-v1`) car les poids spécialisés et la calibration caméra de site ne sont pas disponibles.

## Validation et limites

Le modèle diagnostic principal a été évalué sur un banc **SIL synthétique** de 4 800 exemples, seed 2026, six classes. Le déploiement expose les métriques et les tests de torture via :

- `/api/models`
- `/api/validation`
- `/api/scenarios`
- `/api/datasets`

Les performances du banc synthétique ne doivent **jamais** être présentées comme une performance SOCOCIM réelle. Les validations de transfert sur UCI Hydraulic Systems et sur le jeu d'images de convoyeur de minerai constituent uniquement des preuves auxiliaires hors domaine ciment/AFR.

Les tests de robustesse du MVP vérifient notamment le bruit, les données manquantes, les capteurs bloqués, les pertes de rafales, la désynchronisation, les perturbations caméra et l'absence de violation du principe read-only.

## Snapshot reproductible dans ce dépôt

Le dépôt contient une reconstruction publique et auditable du cœur SIL :

- `flowtrust_core.py` — générateur synthétique, règles physiques, contrôle d'observabilité ;
- `train_models.py` — entraînement déterministe Random Forest + Isolation Forest ;
- `api/main.py` — endpoint FastAPI de diagnostic en mode conseil ;
- `index.html`, `styles.css`, `app.js` — miroir web léger pour lecture du concept ;
- `tests/test_core.py` — tests de reproductibilité, observabilité et règles de sûreté ;
- `.github/workflows/ci.yml` — CI de test et reconstruction du snapshot ML.

Le déploiement Vercel v0.2.0 reste la démonstration de référence. Le snapshot GitHub rend la logique scientifique principale lisible et reproductible sans publier de données industrielles propriétaires.

## Reproduire le cœur ML

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
python train_models.py
uvicorn api.main:app --reload
```

Les modèles sont générés localement dans `models/` afin d'éviter de versionner inutilement des artefacts binaires lourds.

## Trajectoire pilote industriel

Le premier pilote doit rester non intrusif : connexion OPC UA en lecture seule, acquisition des variables pertinentes, caméra industrielle fixe sur une zone AFR choisie, edge computer/IPC local, écran opérateur, journalisation, replay historique puis **shadow mode**. Le passage au mode conseil ne vient qu'après calibration et validation site. Toute écriture dans le SCADA ou tout contrôle automatique est hors périmètre du MVP.

## Sécurité et revendications

FLOWTRUST-AFR n'est ni un SIS, ni une protection machine, ni un système certifié de contrôle-commande. Il s'agit d'un assistant de diagnostic et d'aide à la décision. Aucune économie, fiabilité, probabilité de panne ou performance site-specific ne doit être revendiquée avant une campagne de validation industrielle.

## Licence

Code du snapshot public : [MIT](LICENSE). Les jeux de données externes conservent leurs licences respectives.
