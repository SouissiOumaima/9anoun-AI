# Démonstration DS3 live : stockage de test pour l'intégration DS1 → DS3 live → DS5

Documents **fictifs** uniquement. Aucun document réel n'est envoyé à Gemini (règle NDA).

## Contenu

| storage_ref | Fichier | Ce que DS3 renvoie |
|---|---|---|
| `tradrly://cards/company_042/documents/doc_7f3a` | `ds3_stockage/cards/company_042/documents/doc_7f3a/paie_fictive_01_fr.pdf` | Cas normal : tous les champs lus et cités (base 424.100, brut 516.100, CNSS 47.378). |
| `tradrly://cards/company_042/documents/doc_8b21` | `ds3_stockage/cards/company_042/documents/doc_8b21/paie_fictive_04_pieges.pdf` | Cas avec pièges : date d'entrée « 01/09/19 », « CDD » et « 195 h » reviennent à `null` avec leur raison. Sert à tester l'étape de confirmation. |

Requêtes prêtes : `requete_doc_7f3a.json`, `requete_doc_8b21.json`. La carte active doit être `company_042` ;
avec une autre carte, DS3 répond `ACCES_REFUSE` (voulu).

## Variables d'environnement

```powershell
$env:DS3_HANDLER_MODE = "live"
$env:DS3_STORAGE_ROOT = "<racine du dépôt>\src\document_intelligence\evaluation\demo_live\ds3_stockage"
# GEMINI_API_KEY : dans le .env de chacun (clé donnée par l'encadrant), jamais dans le code ni dans un message.
```

## Vérifier DS3 seul (depuis la racine du dépôt)

```powershell
python -m src.document_intelligence.service src\document_intelligence\evaluation\demo_live\requete_doc_7f3a.json --root src\document_intelligence\evaluation\demo_live\ds3_stockage
```

Résultat attendu : `"status": "ok"`, `"mode": "live"`, et les valeurs du tableau.
Sans `DS3_STORAGE_ROOT` ni `--root` : `"status": "erreur"`, `INTERNAL_ERROR` (jamais d'exception).
Clé Gemini absente ou refusée : `"status": "erreur"`, réessayable.

Le test `test_document_intelligence_demo_storage.py` vérifie ces requêtes à chaque `pytest`, avec un faux Gemini.
