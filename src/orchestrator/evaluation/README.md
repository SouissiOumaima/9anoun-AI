# Évaluation — DS1 Orchestration & Context

Ce dossier contient les **golden sets et les métriques propres à DS1**.
L'évaluation n'est pas un rôle séparé : chaque rôle évalue son propre domaine.

## Golden Set v0

`golden_set.v0.json` contient 24 requêtes synthétiques FR/AR. Chaque cas fixe
l'intention, la langue, le type de carte éventuel, l'état final et l'agent
attendus. Les réponses des spécialistes sont des mocks: ce set mesure DS1
(compréhension, routage et abstention), pas l'exactitude juridique/comptable.

Lancer l'évaluation depuis la racine :

```text
python -m src.orchestrator.evaluation.run_golden
```

Métriques :

- **intent_accuracy** : intention extraite correcte ;
- **language_accuracy** : langue détectée correcte ;
- **flow_accuracy** : état final et agent routé corrects ;
- **passed** : vrai seulement si tous les cas sont conformes.

Le test automatisé bloque toute régression du set. Les cas seront enrichis et
validés avec les owners DS2 à DS5 quand leurs contrats réels seront livrés.

L'organisation des sous-dossiers est libre ; documentez-la ici. Les données
de test partagées avec d'autres rôles vont plutôt dans `data/mock_cards/`
(préfixe `orchestrator_`).
