# FLOWTRUST-AFR — SIC2026

**FLOWTRUST-AFR** est un assistant de diagnostic industriel multimodal pour la chaîne d'alimentation en **Alternative Fuels and Raw Materials (AFR)** d'une cimenterie. Le MVP reste strictement en **mode conseil / lecture seule** : il observe, confronte les sources, diagnostique ou s'abstient, puis propose des vérifications à l'opérateur. Il ne commande ni PLC, ni variateur, ni SCADA.

## Démonstration publique

**Application :** https://flowtrust-afr-sic2026.vercel.app  
**API santé :** https://flowtrust-afr-sic2026.vercel.app/api/health

État vérifié du déploiement public au **12 août 2026** :

- `version = 0.3.1`
- `fusion_version = t02-edge-v1`
- `mode = advisory_read_only`
- `automatic_control_allowed = false`
- `model_id = flowtrust-linear-prior-v1`

## Expérience opérateur

L'application ouvre directement sur une supervision temps réel de démonstration, sans page marketing intermédiaire. Elle propose :

- synoptique trémie → doseur → convoyeur → transfert ;
- débit, flux visuel, courant moteur, vitesse, niveau et vibration ;
- tendances temps réel ;
- diagnostic T02, confiance et état des modalités ;
- explication des preuves et suggestion opérateur ;
- journal chronologique ;
- tests guidés à la demande ;
- laboratoire d'injection de défauts ;
- alarmes visuelles et buzzer pour les événements critiques ;
- historique et replay progressif.

Les défauts de démonstration couvrent notamment dérive de pesage, pontage de trémie, bourrage convoyeur, déversement, alimentation instable, perte caméra, capteur bloqué, désynchronisation et données manquantes.

## T02 — fusion multimodale de confiance

FLOWTRUST ne traite plus un classifieur unique comme arbitre absolu. T02 sépare trois familles de preuves :

1. **procédé** — débit, trémie, bilan matière et dynamique de flux ;
2. **électromécanique** — vitesse réelle/commandée, courant, charge, couple et vibration ;
3. **vision** — proxy visuel, accumulation, déversement et qualité/disponibilité caméra.

Chaque modalité reçoit une fiabilité indépendante. Une source dégradée perd du poids ou est exclue. Le runtime edge exige au moins deux modalités fiables pour conclure. Les évidences multimodales portent **78 %** de la fusion ; le prior statistique distillé apporte **22 %** et ne peut pas contourner les gates d'observabilité, de contradiction ou de hors-domaine.

Lorsque les preuves sont insuffisantes ou incompatibles, la réponse attendue est `unknown` / **ABSTENTION**, et non un diagnostic forcé.

## Prior statistique edge

Pour rester léger et déployable sur Vercel/edge, le runtime public utilise `flowtrust-linear-prior-v1`, un prior logistique distillé et exporté en coefficients purs. Il a été entraîné hors ligne le **12/08/2026** sur le banc SIL public de 4 800 exemples, seed 2026, six classes.

Sur son split fermé SIL, ce prior atteint :

- balanced accuracy : **0,99917** ;
- log loss multiclasses : **0,00405**.

Ces métriques caractérisent uniquement le banc synthétique reproductible. Elles ne constituent pas une mesure de performance SOCOCIM. Le fichier versionné est [`models/linear_prior_v1.json`](models/linear_prior_v1.json).

## Random Forest (RF)

**RF signifie Random Forest, ou forêt aléatoire.** Il s'agit d'un ensemble d'arbres de décision entraînés sur des sous-échantillons de données et/ou de variables. Les votes des arbres sont agrégés pour produire une classe et des probabilités. RF reste présent dans le banc R&D comme baseline explicable ; dans le runtime edge v0.3.1, il a été distillé vers un prior linéaire beaucoup plus léger, tandis que la décision finale reste assurée par la fusion T02.

## Caméra de la tablette

La caméra du navigateur est activée uniquement après autorisation utilisateur. Dans la version publique actuelle, le test local mesure :

- luminosité ;
- contraste ;
- netteté ;
- qualité technique globale de l'image.

**Ce score ne signifie pas qu'un convoyeur ou un défaut AFR a été reconnu.** Le scene-gate industriel basé sur des backbones de vision préentraînés reste dans la trajectoire V2 et ne sera activé publiquement qu'après validation de son gate hors-domaine.

## Discipline de sélection des modèles V2

La branche `v2-model-rebuild` conserve les expériences de reconstruction : vision à grande échelle, intégrité capteurs, séries temporelles, audio/vibration et copilote opérateur. Un modèle n'est pas retenu parce qu'il est plus gros : il doit battre une baseline adaptée sur un split fermé et respecter un gate prédéfini.

Exemples du premier cycle :

- MOMENT initial : rejeté après comparaison à la baseline capteur ;
- challenger capteurs T01-F1 : macro-F1 ≈ **0,884**, amélioration forte mais sous le gate volontaire de 0,90 ;
- Chronos / forecasting : non retenu pour ce bloc lorsque la persistance s'est révélée meilleure.

Cette discipline évite d'intégrer artificiellement des foundation models qui n'apportent pas de gain mesuré au MVP.

## Données et validation

Le dépôt sépare trois niveaux de preuve :

- **SIL synthétique reproductible** pour le pipeline, les scénarios, la fusion et l'abstention ;
- **données physiques publiques hors domaine** comme preuves auxiliaires de transférabilité ;
- **données SOCOCIM** pour la calibration et la validation du futur pilote.

Le système teste notamment données manquantes, capteurs bloqués, qualité caméra dégradée, perte de modalité, désynchronisation et contradictions entre sources. Aucune écriture automatique n'est autorisée.

## Structure du dépôt

- `flowtrust_core.py` — génération SIL, règles physiques et observabilité ;
- `fusion_trust.py` — implémentation R&D complète de la fusion T02 ;
- `models/linear_prior_v1.json` — prior statistique distillé et traçable ;
- `api/main.py` — implémentation Python de référence du runtime edge ;
- `deploy/vercel/` — runtime Node minimal correspondant au déploiement Vercel ;
- `index.html`, `styles.css`, `app.js` — HMI de démonstration ;
- `t02-live.js` — liaison HMI ↔ `/api/diagnose` ;
- `tests/test_core.py` — règles de sûreté du cœur ;
- `tests/test_fusion.py` — gates et contradictions T02 ;
- `tests/test_api_t02.py` — contrat API, abstention et perte de modalité ;
- `.github/workflows/ci.yml` — CI de reconstruction et tests.

La CI vérifie également la syntaxe JavaScript de l'HMI et reconstruit le snapshot ML avant les tests API.

## Reproduire le cœur R&D

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
python train_models.py
uvicorn api.main:app --reload
```

## Pilote industriel proposé

Le premier pilote reste non intrusif : **OPC UA / historian en lecture seule**, acquisition des variables utiles, caméra industrielle fixe sur une zone AFR choisie, edge computer local, écran opérateur, journalisation, replay historique puis shadow mode. Le passage au mode conseil intervient après calibration et validation site.

FLOWTRUST-AFR n'est ni un SIS ni une protection machine. La décision finale reste à l'opérateur.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Validation](docs/VALIDATION.md)
- [Pilote SOCOCIM](docs/PILOT_SOCOCIM.md)

## Licence

Code du snapshot public : [MIT](LICENSE). Les jeux de données externes conservent leurs licences respectives.
