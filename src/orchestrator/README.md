# DS1 — Orchestration & Context (`src/orchestrator/`)

- **Owner** : Achraf Chaabane
- **Catégorie** : Backbone
- **Branche** : `DS1_Orchestration_Track`

## Responsabilité

Orchestrator, planner, state machine, context/card resolver, intent & entity understanding.

## Étape 1 — Contexte sécurisé et contrat d'entrée

La première fondation DS1 est implémentée :

- `models.py` porte l'identité authentifiée, le type de carte et le contexte actif.
- `context.py` vérifie côté backend l'organisation et l'autorisation explicite de la carte. Une sortie de modèle ne peut donc pas élargir l'accès.
- `data/mock_cards/schemas/orchestrator_request.v0.schema.json` décrit le contrat d'entrée versionné, en français et arabe.
- `data/mock_cards/orchestrator_requests_demo.json` contient des requêtes fictives, dont une sans carte active.

Les tests se lancent avec :

```text
python -m pytest -q src/orchestrator/tests
```

## Étape 2 — Intentions et entités FR/AR

`intent.py` fournit un premier parser déterministe et sans dépendance externe.
Il route les demandes vers la recherche juridique, le calcul de paie,
l'analyse de document ou de dossier, et la génération d'un livrable. Il extrait
uniquement les dates, montants et articles explicitement écrits. En cas de
message ambigu ou inconnu, il retourne `clarification_required` : il ne choisit
pas un agent par défaut. Le parser ne fournit jamais de permissions ni de faits.

## Étape 3 — Database/Card Agent v1

`card_repository.py` expose un accès lecture seule aux cartes mockées. Il ne
permet de lire que la carte active, après les vérifications d'organisation et
d'autorisation déjà imposées par DS1. Il ne propose ni SQL brut, ni recherche
globale, ni jointure entre cartes. `orchestrator_cards_demo.json` contient des
données fictives Company, Client et Case pour les tests d'intégration.

## Étape 4 — Tool Contracts v0

`tool_contracts.py` est la frontière entre le planner et les agents DS2 à DS5.
Son registre fermé n'autorise que quatre opérations de lecture : recherche
juridique, extraction documentaire, analyse de dossier et calcul comptable.
Chaque appel reste rattaché à la carte active autorisée et est sérialisé dans
le contrat JSON `orchestrator.tool.v0`. Les schémas de requête et réponse,
ainsi que des appels de démonstration, sont dans `data/mock_cards/`.

## Étape 5 — State Machine et Planner v1

`state_machine.py` réalise le flux contrôlé de bout en bout : réception,
validation de contexte, compréhension, planification, exécution puis résultat.
Le planner ne produit qu'un appel présent dans le registre d'outils v0. Les
limites configurables portent sur le nombre d'étapes, le timeout d'un outil et
les retries. Une demande ambiguë est arrêtée pour clarification; une erreur,
un timeout ou un contexte incompatible termine en échec explicite.

## Étape 6 — Human Approval et Audit Trail

`approval.py` bloque toute action conséquente tant qu'elle n'est pas approuvée
par le même utilisateur authentifié, dans la même organisation. Les actions
utilisent une clé d'idempotence afin de ne pas être exécutées deux fois.
`audit.py` enregistre les états et métadonnées de flux sans conserver le texte
du message, les paramètres d'outil ou les données de cartes : seuls leurs
empreintes et métadonnées nécessaires sont journalisés.

## Démo locale

Pour essayer le flux sans dépendre des autres rôles, exécuter depuis la racine :

```text
python -m src.orchestrator.demo
```

La démo utilise seulement des cartes et réponses fictives. Elle affiche le
routage DS1, mais ne contacte pas les agents DS2 à DS5.

## Intégration Track B v0

`track_b_adapter.py` traduit une enveloppe DS1 autorisée vers le contrat réel
`track_b.v0` de DS5 et normalise sa réponse pour la state machine. Le premier
parcours supporté est le SMIG, seulement si le message donne explicitement le
mode (`mensuel` ou `horaire`), le régime (`40h` ou `48h`) et une date complète.
Les calculs de salaire de base et de prime attendent encore leurs paramètres
structurés; DS1 demande donc une clarification au lieu de les inventer.

## Mocks provisoires DS2 à DS5

`mock_specialists.py` et
`data/mock_cards/orchestrator_agent_responses_demo.json` exécutent les quatre
routes DS1 sans attendre les services réels. Les mocks DS2, DS3 et DS4 sont
des propositions DS1 à remplacer par les contrats de leurs owners. Aucun mock
ne constitue une réponse juridique ou comptable réelle.

## Intégration hybride réelle DS1 ↔ DS5

`hybrid_dispatcher.py` envoie maintenant toute route
`track_b_accounting.compute` vers le vrai `TrackBAdapter` et le handler DS5.
DS2 utilise son adaptateur réel (avec repli mock si le corpus local est absent).
DS4 utilise désormais son handler v1 pour les dossiers structurés, avec
compatibilité v0 dans l'adaptateur. DS3
v2 utilise le mock par défaut, mais peut appeler le service réel livré par DS3
en configurant explicitement le backend avec `DS3_HANDLER_MODE=live`. Dans ce
mode, `DocumentIntelligenceAdapter` appelle
`src.document_intelligence.service.handle_request` avec la même requête
`ds3.v2`; DS3 résout seul le `storage_ref` sous `DS3_STORAGE_ROOT`. En mode
live, DS1 n'accepte que la référence exacte
`tradrly://cards/<carte-active>/documents/<document-sélectionné>` : jamais un
chemin local, une autre carte, un autre document ou du contenu de fichier.
Sans cette
configuration explicite, la démo locale garde le mock et reste reproductible.
La démo locale utilise ce dispatcher : une demande SMIG complète retourne donc
un vrai montant et une vraie citation DS5, pas une réponse simulée.

## Extension Track B : salaire de base et prime

`track_b_requests.py` construit une requête `track_b.v0` seulement à partir de
paramètres explicites et la valide contre le schéma DS5 avant l'appel. Le
`StructuredTrackBPlanner` permet ainsi d'exécuter réellement `salaire_base` et
`prime`, sans que DS1 invente le secteur, la catégorie, l'ancienneté ou les
conditions. Essayer les deux parcours avec :

```text
python -m src.orchestrator.track_b_structured_demo
```

## Company Card vers Track B

`card_to_track_b.py` lit une carte active autorisée et prépare une opération
Track B révisable. Les champs présents dans la carte sont repris tels quels;
un champ absent (par exemple la date) donne une liste `missing` au lieu d'une
valeur par défaut. Essayer le chemin complet carte → salaire réel avec :

```text
python -m src.orchestrator.card_track_b_demo
```

## Interface/API locale Track B

Une interface locale permet de saisir les paramètres SMIG, salaire de base ou
prime sans JSON ni terminal. Elle appelle le même flux DS1 → DS5 réel et
affiche le montant, les citations et une réponse FR/AR. Démarrer :

```text
python -m src.orchestrator.web_app
```

Puis ouvrir `http://127.0.0.1:8765`. C'est une démo locale avec identité et
cartes fictives : elle ne doit pas être exposée sur un réseau ni publiée telle
quelle.

La zone **Poser une question** est le parcours principal : DS1 détecte
l'intention et route le prompt vers DS2 (recherche juridique mock), DS3
(analyse de document mock), DS4 (analyse de dossier mock) ou DS5 (calcul réel
si tous les paramètres SMIG sont explicitement fournis). Une ambiguïté ou un
paramètre de paie absent produit une demande de précision, jamais une valeur
inventée. Le formulaire structuré reste disponible pour les calculs de paie
qui exigent des champs exacts.

Chaque calcul de l'interface reçoit un `request_id` unique. La section
**Historique d'audit local** affiche seulement la date, l'opération, la Card,
l'état et le nombre de tentatives : ni message, ni paramètres, ni montant ne
sont conservés dans cette vue.

## Validation humaine (démo)

La section **Validation humaine** prépare les futures actions d'écriture :
`pending_approval` → `approved` ou `rejected` → `executed`. Elle propose un
rapport de paie simulé pour une Company Card, afin de démontrer le contrôle
d'accès, l'idempotence et l'audit sans appeler un service d'écriture réel.
Les calculs DS5 restent strictement en lecture seule.

## Golden Set et évaluation

Le golden set DS1 vérifie 24 demandes synthétiques FR/AR sur l'intention, la
langue, l'abstention et le routage. Lancer `python -m
src.orchestrator.evaluation.run_golden` depuis la racine pour produire les
métriques de non-régression.

## Réponses utilisateur FR/AR

`response_formatter.py` transforme les états internes en une enveloppe sûre
pour l'API ou l'interface : `status`, `code`, `message_fr`, `message_ar`,
`next_action` et `request_id`. Les exceptions brutes, données de carte et
paramètres d'outils ne sont jamais exposés. Les refus DS5 sont traduits en
messages explicites pour `HORS_SCOPE`, `SOURCE_MANQUANTE` et `PARAM_INVALIDE`.

## Structure

| Dossier | Contenu |
|---|---|
| `tools/` | Outils et scripts du rôle. |
| `tests/` | Tests automatiques du rôle (`python -m pytest -q src/orchestrator/tests`). |
| `evaluation/` | Golden sets et métriques propres à ce rôle (voir `evaluation/README.md`). |

## Intégration DS4 v1

Le planner transmet les données de la Case Card autorisée au handler DS4 v1.
L'adaptateur officiel accepte v0 et v1 ; seule la réponse v1 préparatoire peut
réussir sans citation finale, avec une conclusion juridique obligatoirement nulle.
La démo affiche cette limite et la nécessité d'une revue humaine en FR/AR.
Le parcours ne déclenche pas automatiquement les services DS2 et DS3.
Voir `docs/DS1_DS4_V1_INTEGRATION_2026_11_20.md` pour le périmètre et la validation.

Un parcours distinct « Scénario complet DS2 + DS3 → DS4 » exécute désormais
DS3 live sur une fiche fictive de la Case Card E2E, attend la confirmation
explicite des faits et de leur liaison documentaire, puis appelle DS2 live et
DS4 v1. Les réponses mock ne permettent pas de poursuivre. Les faits non
sélectionnés ne sont pas transmis à DS4. Les pages et dates juridiques
manquantes restent signalées, sans conclusion automatique.
Voir `docs/DS1_DS2_DS3_DS4_SCENARIO_2026_11_20.md` pour le scénario, les résultats
réels, les commandes et les demandes à DS2/DS4.

## Conventions communes (voir le README racine)

La préparation à la migration D21 des 56 secteurs, les contrôles de réception
et les demandes à DS2 sont décrits dans
`docs/DS1_SECTORS_MIGRATION_READINESS_2026_11_21.md`.
Le détecteur DS2 traite les correspondances multiples avant tout appel et
construit une clarification FR/AR à partir du vocabulaire. D30 reste séparée.

- Données de test dans `data/mock_cards/`, avec le préfixe `orchestrator_`.
- Messages échangés avec les autres rôles : JSON Schema versionnés (`src/shared/schemas/`).
- Dépendances : section **DS1** du `requirements.txt` racine.
- Règle « Citation ou Silence » : toute réponse factuelle est sourcée, sinon refus explicite.
