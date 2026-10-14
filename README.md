# 9anoun AI

Assistant juridique bilingue arabe / français sur le droit du travail tunisien.

## Vision : 5 rôles (DS1-DS5), couplage faible

Le dépôt est partagé entre **5 rôles (DS1-DS5)**. Chacun possède son dossier
dans `src/`, sa branche et ses dépendances. Les rôles échangent uniquement
des messages JSON décrits par des schémas versionnés (voir
[Schémas partagés](#schémas-partagés)) : aucun rôle n'importe le code
interne d'un autre.

L'**évaluation n'est pas un rôle à part** : chaque rôle tient ses propres
golden sets et métriques dans `src/<rôle>/evaluation/`.

## Équipe

| Rôle DS | Intitulé | Dossier | Catégorie | Personne(s) | Responsabilité principale | Branche |
|---|---|---|---|---|---|---|
| DS1 | Orchestration & Context | [`src/orchestrator/`](src/orchestrator/) | Backbone | Achraf Chaabane | Orchestrator, planner, state machine, context/card resolver, intent & entity understanding | `DS1_Orchestration_Track` |
| DS2 | Legal Knowledge & Retrieval | [`src/legal_retrieval/`](src/legal_retrieval/) | Foundation | Abd Mouhib Souri | Legal knowledge graph, legal metadata, hybrid retrieval, reranking, legal research agent | `DS2_Legal_Retrieval_Track` |
| DS3 | Document Intelligence | [`src/document_intelligence/`](src/document_intelligence/) | Foundation | Hadil Lajili & Wiem Saafi | File processing, OCR, table & clause extraction, confidence scoring, document-analysis agent | `DS3_Document_Intelligence_Track` (partagée) |
| DS4 | Lawyer Track (Track A) | [`src/track_a_legal/`](src/track_a_legal/) | Vertical | Ghofran Maaoui | Case-analysis agent, evidence mapping, legal drafting, domain validation for legal answers | `DS4_Lawyer_Track` |
| DS5 | Comptable Track (Track B) | [`src/track_b_accounting/`](src/track_b_accounting/) | Vertical | Oumaima Souissi | Accounting & payroll agent, deterministic calculation tools, financial analysis, domain validation for accounting answers | `DS5_Comptable_Track` |

Chaque personne tient un seul rôle. DS3 est la seule exception : deux
personnes partagent le même rôle et la même branche.

## Règle « Citation ou Silence »

Toute réponse factuelle (article de loi, montant, date d'effet…) doit être
accompagnée de sa source vérifiable : document, page, article. Si la source
manque, le système répond par un **refus explicite**, sans approximation.
Exemple de mise en œuvre : le contrat Track B
([`docs/CONTRACT_TRACK_B.md`](docs/CONTRACT_TRACK_B.md)), où le schéma de
réponse exige au moins une citation pour tout montant renvoyé.

## Arborescence

```
data/
  raw/            corpus source (PDF + OCR) — lecture seule, ne jamais modifier
  processed/      données vérifiées produites par les rôles
  mock_cards/     données de test et schémas échangés (préfixe par rôle, voir README)
docs/
  DECISIONS.md    journal des décisions techniques
src/
  orchestrator/           DS1
  legal_retrieval/        DS2
  document_intelligence/  DS3
  track_a_legal/          DS4
  track_b_accounting/     DS5
  shared/                 conventions communes (schémas partagés)
```

Chaque rôle suit la même structure minimale : `README.md`, `tools/`,
`tests/` et `evaluation/`. Track B, plus avancé, a sa propre organisation
(`calc/`, `contract/`) ; son `evaluation/` contient un jeu de référence lu dans les PDF
et un script de métriques ([`src/track_b_accounting/evaluation/`](src/track_b_accounting/evaluation/README.md)).

## Conventions

### Branches et pull requests
- Une branche par rôle, de la forme `DS<n>_<nom-court>_Track` (tableau
  ci-dessus). DS3 partage une seule branche entre ses deux membres.
- Les changements transverses passent par des branches `chore/…` ou `docs/…`.
- Personne ne pousse directement sur `main` : tout passe par une pull request
  relue par l'équipe.

### Données de test (`data/mock_cards/`)
Chaque fichier porte le préfixe de son rôle (`orchestrator_`,
`legal_retrieval_`, `document_intelligence_`, `track_a_`, `track_b_`), y
compris dans `schemas/`. Détails : [`data/mock_cards/README.md`](data/mock_cards/README.md).

### Schémas partagés
Il s'agit de JSON Schema draft 2020-12, nommés
`<rôle>_<objet>.v<N>.schema.json`, marqués « vN — proposition, à valider »
tant que l'équipe ne les a pas acceptés. Un changement incompatible crée une
nouvelle version. Détails : [`src/shared/schemas/README.md`](src/shared/schemas/README.md).

### Dépendances
- Le fichier [`requirements.txt`](requirements.txt) racine a une section par
  rôle. Chaque rôle n'édite que sa section, ce qui limite les conflits de
  merge.
- Un rôle peut aussi tenir son propre fichier et y renvoyer par `-r` depuis sa
  section ; c'est le cas de DS5.
- Les versions sont figées (`==`).

### Décisions
Toute décision technique non triviale est consignée dans
[`docs/DECISIONS.md`](docs/DECISIONS.md) (format : Décision · Alternatives
envisagées · Raison).

## Installation

```
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS : source .venv/bin/activate)
python -m pip install -r requirements.txt
```

Les tests de chaque rôle se lancent depuis la racine, par exemple :
`python -m pytest -q src/track_b_accounting/tests`.
